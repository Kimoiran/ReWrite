"""技能间共享工具函数。"""

import json
import re as _re
import unicodedata
from pathlib import Path

from .....utils.logging_setup import get_logger

log = get_logger(__name__)


def list_works() -> list:
    """列出所有作品（供 providers.py 使用）。"""
    wd = _works_dir()
    works = []
    for child in sorted(wd.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = child / "work.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                works.append({
                    "name": child.name,
                    "title": m.get("title", child.name),
                    "type": m.get("work_type", ""),
                    "modules": m.get("modules", []),
                    "updated": m.get("updated", ""),
                })
            except Exception:
                log.warning("读取作品元数据失败 %s", meta, exc_info=True)
    return works


def _works_dir() -> Path:
    import os
    env = os.environ.get("REWRITE_WORKS_DIR", "")
    if env:
        return Path(env)
    from .....storage.paths import get_works_dir
    return get_works_dir()


def _work_path(name: str) -> Path:
    wd = _works_dir()
    _INVALID = ".__invalid_work_name__"  # 必定不存在的点前缀名(匹配循环与 list_works 均跳过)
    # 安全:只允许纯目录名,拒绝路径分隔符/绝对路径/..(防路径穿越)
    if not name:
        return wd / _INVALID
    import os as _os
    import re as _re
    if _os.path.isabs(name) or _os.sep in name or (_os.altsep and _os.altsep in name) \
            or ".." in Path(name).parts or name in (".", "..") \
            or _re.match(r"^[A-Za-z]:", name):  # 防 Windows 盘符形式(C:foo)
        # 非法名称:回退到必定不存在的名字,技能会自然返回"未找到",不会误写 works 根
        return wd / _INVALID
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == name or child.name.endswith(f"-{name}"):
            return child
        meta = child / "work.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if data.get("title") == name:
                    return child
            except Exception:
                log.debug("读取作品元数据失败 %s", meta, exc_info=True)
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if name.lower() in child.name.lower():
            return child
    return wd / name


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("读取数据文件失败,按空数据处理 %s", path, exc_info=True)
            return {}
    return {}


def _save(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        log.error("写入数据文件失败 %s: %s", path, e)
        raise


def make_chapter_md(title: str, content: str = "") -> str:
    """生成标准化的章节 Markdown 文本。"""
    safe_title = _re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
    if content:
        return f"# {safe_title}\n\n{content}"
    return f"# {safe_title}\n\n"


def make_chapter_html(title: str, content: str = "") -> str:
    """生成标准化的章节 HTML（QTextEdit 兼容格式，统一 14pt 正文/17pt 标题）。

    与 QTextEdit 默认字号一致，避免 px/pt 混用导致的字体大小不一致。
    """
    safe_title = _re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
    lines = [
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
        '"http://www.w3.org/TR/REC-html40/strict.dtd">',
        '<html><head><meta name="qrichtext" content="1" />'
        '<meta charset="utf-8" />'
        '<style type="text/css">',
        "p, li { white-space: pre-wrap; }",
        "hr { height: 1px; border-width: 0; }",
        'li.unchecked::marker { content: "\\2610"; }',
        'li.checked::marker { content: "\\2612"; }',
        "</style></head>",
        '<body style="'
        "font-family:'Microsoft YaHei UI','Microsoft YaHei','Segoe UI','sans-serif';"
        " font-size:14pt; font-weight:400; font-style:normal;\">",
        # 标题行：17pt 加粗
        '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; '
        'margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
        '<span style=" font-size:17pt; font-weight:700;">'
        f'{safe_title}</span></p>',
    ]
    if content:
        lines.append(content)
    else:
        # 默认正文空段：显式 14pt，新文字从正确大小开始
        lines.append(
            '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; '
            'margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
            '<span style=" font-size:14pt;"> </span></p>'
        )
    lines.append("</body></html>")
    return "\n".join(lines)


def _date_sort_key(date_str: str, era: str = ""):
    """智能日期排序键，支持「{era}XXX年」「{era}前XXX年」「{era}元年」等格式。"""
    if not date_str:
        return (1, "", 0, 0)
    if era:
        if f"{era}元年" in date_str:
            return (0, "", 1, 1)
        m = _re.match(_re.escape(era) + r'前?\s*(\d+)', date_str)
        if m:
            year = int(m.group(1))
            is_before = "前" in date_str
            return (0, "", 0 if is_before else 1, year)
    if date_str.isdigit():
        return (0, "", 0, int(date_str))
    nums = _re.findall(r'\d+', date_str)
    if nums:
        return (0, "", 0, int(nums[0]))
    return (1, date_str, 0, 0)


_SENTENCE_BREAK = _re.compile(r'(。|！|？|；|……|——)')
"""在中文句末标点后自动断行。"""


def _fmt_text(text: str, max_len: int = 100) -> str:
    """长文本自动加换行：在句末标点后插入 \\n，使每行不超过 max_len 字。

    适用于人物卡/大纲/时间线中的长文本字段。
    已有换行或长度 ≤ max_len 的文本原样返回。
    """
    if not text or len(text) <= max_len or "\n" in text:
        return text
    # 在标点后断句，用零宽断言保留标点
    parts = _SENTENCE_BREAK.split(text)
    # parts = [text, punct, text, punct, ...]
    lines = []
    buf = ""
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if not chunk and not punct:
            continue
        segment = chunk + punct
        if len(buf) + len(segment) <= max_len:
            buf += segment
        else:
            if buf:
                lines.append(buf)
            buf = segment
    if buf:
        lines.append(buf)
    return "\n".join(lines) if len(lines) > 1 else text


def _fmt_nodes(obj, fields: set, max_len: int = 100):
    """递归遍历 JSON 结构，对指定字段名的字符串值应用 _fmt_text。

    用于在 skill execute() 中格式化返回给 AI 的数据。
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k in fields:
                obj[k] = _fmt_text(v, max_len)
            else:
                _fmt_nodes(v, fields, max_len)
    elif isinstance(obj, list):
        for item in obj:
            _fmt_nodes(item, fields, max_len)
    return obj


# ─────────────────────────────────────────────────────────────
# 章节文件解析
#
# 章节文件名是 ``NNNN_标题.md``。AI 几乎从不会完整复述标题：
# 它会说「第1章」「第一章」「第一章 在孤儿院的日子」甚至只给一个数字。
# 旧实现只做严格相等比较（display == 章节名），于是频繁「未找到章节」，
# AI 只能退回去用 search_chapters(RAG) 把正文「搜回来」。
# 下面这套解析让上述写法都能命中同一个文件。
# ─────────────────────────────────────────────────────────────

_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100}

_CHAPTER_CN_RE = _re.compile(r"第([零〇一二两三四五六七八九十百]+)([章节回卷篇部])")
_PUNCT_RE = _re.compile(
    r"[\s_\-—–…·、,，。.:：;；!！?？\"'“”‘’()（）\[\]【】《》<>|\\/]+")
_LEADING_DIGITS_RE = _re.compile(r"^(\d+)")
_ARABIC_CHAPTER_RE = _re.compile(r"第\s*([0-9]+)\s*[章节回卷篇部]")

_CHAPTER_SUFFIXES = (".md", ".html")


def cn_numeral_to_int(text: str) -> int:
    """中文数字转整数：「十二」→12、「二十三」→23、「一百零五」→105。

    无法解析时返回 0（调用方据此跳过）。
    """
    if not text:
        return 0
    total = 0
    current = 0
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            total += (current or 1) * _CN_UNITS[ch]
            current = 0
        else:
            return 0
    return total + current


def normalize_chapter_name(text: str) -> str:
    """归一化章节名，用于宽松比对。

    全角转半角 → 中文数字章节号转阿拉伯数字 → 转小写 → 去掉标点/空白/下划线。
    「第一章 在孤儿院的日子」与「0001_第1章在孤儿院的日子」都归一成
    ``第1章在孤儿院的日子``。
    """
    t = unicodedata.normalize("NFKC", (text or "").strip())
    # 去掉文件名里的「0001_」序号前缀，让文件名与显示名可比
    t = _re.sub(r"^\d+_", "", t)
    t = _CHAPTER_CN_RE.sub(
        lambda m: (f"第{cn_numeral_to_int(m.group(1))}{m.group(2)}"
                   if cn_numeral_to_int(m.group(1)) else m.group(0)),
        t)
    return _PUNCT_RE.sub("", t.lower())


def chapter_order(text: str) -> "int | None":
    """提取章节序号：「第12章 x」「0012_x」「十二」「第十二章」→ 12。"""
    t = (text or "").strip()
    if not t:
        return None
    m = _LEADING_DIGITS_RE.match(t)
    if m:
        return int(m.group(1))
    m = _ARABIC_CHAPTER_RE.search(t)
    if m:
        return int(m.group(1))
    m = _CHAPTER_CN_RE.search(t)
    if m:
        n = cn_numeral_to_int(m.group(1))
        if n:
            return n
    n = cn_numeral_to_int(t)
    return n or None


def list_chapter_files(chapters_dir: Path) -> list[Path]:
    """列出真正的章节文件（.md/.html，排除隐藏文件与 .bak/.tmp 残留）。"""
    try:
        if not Path(chapters_dir).is_dir():
            return []
        return [
            f for f in sorted(Path(chapters_dir).iterdir())
            if f.is_file() and not f.name.startswith(".")
            and f.suffix.lower() in _CHAPTER_SUFFIXES
        ]
    except OSError as e:
        log.warning("扫描章节目录失败 %s: %s", chapters_dir, e)
        return []


def chapter_display_name(path: Path) -> str:
    """章节显示名：去掉 ``NNNN_`` 序号前缀与扩展名。"""
    stem = Path(path).stem
    return stem.split("_", 1)[-1] if "_" in stem else stem


def list_chapter_names(chapters_dir: Path) -> list[str]:
    """所有章节的显示名（供「未找到章节」时回传给 AI 自修正）。"""
    return [chapter_display_name(f) for f in list_chapter_files(chapters_dir)]


def _chapter_match_score(stem: str, display: str, query: str) -> int:
    """章节匹配打分（0 = 不匹配，越大越可信）。"""
    q = (query or "").strip()
    q_norm = normalize_chapter_name(q)
    if not q_norm:
        return 0
    d_norm = normalize_chapter_name(display)
    s_norm = normalize_chapter_name(stem)

    if q == stem or q == display:
        return 100
    if q_norm in (d_norm, s_norm):
        return 95
    # 「第1章」⊂「第1章 在孤儿院的日子」（任一方向）
    if d_norm.startswith(q_norm) or q_norm.startswith(d_norm):
        return 85
    if q_norm in d_norm:
        return 75
    # 序号兜底：「第一章」↔「第1章 xxx」↔「0001_x」
    q_order = chapter_order(q)
    if q_order is not None and q_order == chapter_order(display):
        return 60
    return 0


def resolve_chapter_file(chapters_dir: Path, query: str) -> "Path | None":
    """把 AI 给的章节名宽松解析成实际文件；命中不了返回 None。"""
    if not (query or "").strip():
        return None
    best, best_score = None, 0
    for f in list_chapter_files(chapters_dir):
        score = _chapter_match_score(f.stem, chapter_display_name(f), query)
        if score > best_score:
            best, best_score = f, score
    return best

