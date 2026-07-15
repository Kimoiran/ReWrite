"""RAG 技能 — 章节正文语义搜索。"""

from ..rag import RAGEngine
from .base_skill import Skill


class SearchChaptersSkill(Skill):
    """搜索章节正文，按语义相关性返回匹配段落。"""

    _engine: RAGEngine = None

    @classmethod
    def set_engine(cls, engine: RAGEngine):
        cls._engine = engine

    @property
    def name(self) -> str:
        return "search_chapters"

    @property
    def description(self) -> str:
        return "搜索章节正文内容，按语义相关性返回最匹配的段落（用于找某句话在哪、找相关描写等）"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或自然语言问题（如「克诺第一次见到塞拉丝」「所有描写下雨的段落」）"},
                "top_k": {"type": "integer", "description": "返回结果数量，默认 5"},
            },
            "required": ["query"],
        }

    def execute(self, args, work_name=""):
        engine = self._engine
        if not engine or not engine._ready:
            return {"success": False, "error": "RAG 引擎未初始化，请先打开作品加载章节"}
        query = args.get("query", "").strip()
        if not query:
            return {"success": False, "error": "搜索关键词不能为空"}
        top_k = min(args.get("top_k", 5), 20)
        results = engine.search(query, top_k)
        return {"success": True, "query": query, "results": results, "count": len(results)}

    def summarize(self, result, args=None):
        if not result.get("success"):
            return f"❌ 搜索失败: {result.get('error')}"
        q = (args or {}).get("query", "")
        cnt = result.get("count", 0)
        if cnt == 0:
            return f"🔍 未找到与「{q}」相关的段落"
        lines = [f"🔍 搜索「{q}」找到 {cnt} 条相关段落："]
        for i, r in enumerate(result.get("results", []), 1):
            text = r.get("text", "").replace("\n", " ")[:120]
            lines.append(f"  {i}. 📄 {r['chapter']}（相似度 {r.get('score', 0)}）「{text}...」")
        return "\n".join(lines)
