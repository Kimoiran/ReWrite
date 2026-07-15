"""RAG 引擎 — 章节正文语义搜索（零外部依赖，纯 Python TF-IDF）。"""

import re
import math
from collections import Counter
from pathlib import Path
from typing import Optional


# ── 中文停用词（常见无意义词，过滤后索引更精准）──
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "这个", "那个", "什么", "怎么", "为什么", "因为",
    "所以", "但是", "如果", "虽然", "然后", "而且", "或者", "不过",
    "就是", "还是", "只是", "不是", "但是", "可以", "这样", "那样",
    "把", "被", "让", "给", "对", "从", "以", "与", "为", "而",
    "又", "再", "才", "刚", "已经", "正在", "将", "没", "还",
    "啊", "吧", "吗", "呢", "哦", "嗯", "哈", "呀", "嘛",
    "个", "种", "些", "点", "下", "里", "中", "前", "后",
    "做", "能", "来", "去", "出", "进", "过", "起", "开",
    "之", "其", "某", "该", "各", "每", "几", "多", "少",
    "大", "小", "长", "高", "新", "老", "好", "坏", "美",
    "时", "年", "月", "日", "天", "地", "间", "候",
    "像", "如", "似", "仿", "若",
}

# ── 中英文混合分词辅助 ──
_CHINESE_CHAR = re.compile(r'[一-鿿]')
_WORD_BOUNDARY = re.compile(r'([一-鿿]+|[a-zA-Z0-9]+)')


def _tokenize(text: str) -> list[str]:
    """将文本拆分为 token 序列（中文单字 + 英文单词）。"""
    tokens = []
    for part in _WORD_BOUNDARY.findall(text.lower()):
        if _CHINESE_CHAR.match(part):
            # 中文：按字切分（中文单字本身就有语义）
            for char in part:
                if char not in _STOP_WORDS:
                    tokens.append(char)
        else:
            # 英文/数字：整体作为 token
            if part not in _STOP_WORDS and len(part) > 1:
                tokens.append(part)
    return tokens


def _strip_html(html: str) -> str:
    """去除 HTML 标签，保留文本。"""
    text = re.sub(r'<[^>]+>', '', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _split_paragraphs(text: str, min_len: int = 20) -> list[str]:
    """将文本按段落拆分，过滤过短的片段。"""
    # 先按双换行或 HTML 段落标记拆
    raw = re.split(r'\n\s*\n|</p>\s*<p>', text)
    paragraphs = []
    for p in raw:
        p = p.strip()
        # 去掉纯空白/纯标点的段落
        p_clean = re.sub('[，。！？、；：""''「」【】（）《》 \t\n\r]', '', p)
        if len(p_clean) >= min_len:
            paragraphs.append(p)
    return paragraphs


class RAGEngine:
    """轻量级 RAG 引擎。

    工作原理：
    1. 扫描所有章节 HTML → 提取纯文本 → 按段落切块
    2. 对每个段落建立 TF-IDF 向量（纯 Python 实现）
    3. 搜索时计算查询与每个段落的余弦相似度
    4. 返回最相关的 N 个段落及其来源章节

    零外部依赖：不使用任何第三方库（chromadb / sentence-transformers 等）。
    """

    def __init__(self, chapter_module=None):
        self.chapter_module = chapter_module
        self._chunks: list[dict] = []       # [{chap, para, idx}, ...]
        self._tfidf_vectors: list[dict] = []  # [{token: weight}, ...]
        self._idf: dict[str, float] = {}     # {token: idf}
        self._ready = False

    def build_index(self, chapter_module=None):
        """扫描所有章节，分块并建立 TF-IDF 索引。

        每次章节内容变化后需要重新调用（由 _refresh_panels 触发）。
        """
        if chapter_module:
            self.chapter_module = chapter_module
        if not self.chapter_module:
            return

        self._chunks = []
        chapters = self.chapter_module.list_chapters()
        for chap in chapters:
            html = self.chapter_module.read_chapter(chap.path)
            text = _strip_html(html)
            paras = _split_paragraphs(text)
            for i, para in enumerate(paras):
                self._chunks.append({
                    "chapter": chap.title,
                    "chapter_path": str(chap.path),
                    "text": para,
                    "index": i,
                })

        self._build_tfidf()
        self._ready = True

    def _build_tfidf(self):
        """构建 TF-IDF 索引。"""
        n = len(self._chunks)
        if n == 0:
            return

        # 1. 计算所有 token 的 DF（文档频率）
        df: dict[str, int] = {}
        all_tokenized = []
        for chunk in self._chunks:
            tokens = _tokenize(chunk["text"])
            all_tokenized.append(tokens)
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        # 2. 计算 IDF
        for token, doc_count in df.items():
            self._idf[token] = math.log((n + 1) / (doc_count + 1)) + 1

        # 3. 计算每段的 TF-IDF 向量
        self._tfidf_vectors = []
        for tokens in all_tokenized:
            tf = Counter(tokens)
            max_tf = max(tf.values()) if tf else 1
            vec = {}
            for token, freq in tf.items():
                tf_value = freq / max_tf
                vec[token] = tf_value * self._idf.get(token, 1)
            self._tfidf_vectors.append(vec)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """搜索最相关的段落。

        参数：
            query: 搜索关键词或自然语言问题
            top_k: 返回结果数量

        返回：
            [{chapter, chapter_path, text, score}, ...]
            按相似度降序排列。
        """
        if not self._ready or not self._chunks:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # 计算查询向量
        q_tf = Counter(query_tokens)
        q_max = max(q_tf.values())
        q_vec = {}
        for token, freq in q_tf.items():
            q_vec[token] = (freq / q_max) * self._idf.get(token, 1)

        # 计算余弦相似度
        q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
        if q_norm == 0:
            return []

        scored = []
        for idx, vec in enumerate(self._tfidf_vectors):
            # 点积
            dot = 0
            for token, qw in q_vec.items():
                if token in vec:
                    dot += qw * vec[token]
            v_norm = math.sqrt(sum(v * v for v in vec.values()))
            if v_norm == 0:
                continue
            score = dot / (q_norm * v_norm)
            if score > 0:
                scored.append((score, idx))

        scored.sort(reverse=True)
        results = []
        for score, idx in scored[:top_k]:
            chunk = self._chunks[idx]
            results.append({
                "chapter": chunk["chapter"],
                "chapter_path": chunk["chapter_path"],
                "text": chunk["text"][:300],  # 只返回片段
                "score": round(score, 3),
            })
        return results

    def search_formatted(self, query: str, top_k: int = 5) -> str:
        """搜索并返回格式化文本（供 AI 上下文和 Skill 使用）。"""
        results = self.search(query, top_k)
        if not results:
            return "未找到匹配内容"

        lines = [f"🔍 搜索「{query}」找到 {len(results)} 条相关段落：\n"]
        for i, r in enumerate(results, 1):
            text_short = r["text"].replace("\n", " ")[:200]
            lines.append(f"{i}. 📄 {r['chapter']}（相似度 {r['score']}）")
            lines.append(f"   「{text_short}...」\n")
        return "\n".join(lines)
