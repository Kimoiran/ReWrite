"""大纲技能 — 读取/修改条目。"""

from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save, _fmt_nodes


def _find_entry(entries, name):
    for e in entries:
        if e.get("title") == name:
            return e
        if e.get("children"):
            f = _find_entry(e["children"], name)
            if f:
                return f
    return None


class GetOutlineSkill(Skill):
    @property
    def name(self) -> str: return "get_outline"
    @property
    def description(self) -> str: return "获取作品大纲"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        data = _load(_work_path(args.get("work", work_name)) / "outline.json")
        if not isinstance(data, dict):
            data = {"entries": data} if isinstance(data, list) else {"entries": []}
        return _fmt_nodes(data, {"content"})
    def summarize(self, result, args=None):
        entries = result.get("entries", [])
        def _count(ns):
            cnt = 0
            for e in ns:
                cnt += 1
                if e.get("children"):
                    cnt += _count(e["children"])
            return cnt
        total = _count(entries)
        if not entries:
            return "大纲为空"
        # 仅列出标题和状态
        lines = []
        def _walk(ns, depth):
            for e in ns:
                s = e.get("status", "待写")
                tag = "✔" if s == "已完成" else ">" if s == "写作中" else " "
                lines.append(f"  {'  ' * depth}[{tag}] {e.get('title', '')}")
                if e.get("children"):
                    _walk(e["children"], depth + 1)
        _walk(entries, 0)
        return f"大纲共 {total} 条：\n" + "\n".join(lines)


class UpdateOutlineEntrySkill(Skill):
    @property
    def name(self) -> str: return "update_outline_entry"
    @property
    def description(self) -> str: return "修改大纲条目的 title/content/status"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "条目名称"},
                "field": {"type": "string", "description": "title/content/status"},
                "value": {"type": "string", "description": "新值（status 可为: 待写/写作中/已完成）"},
            },
            "required": ["name", "field", "value"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "outline.json")
        entries = data.get("entries", [])
        entry = _find_entry(entries, args["name"])
        if not entry:
            return {"success": False, "error": f"未找到: {args['name']}"}
        if args["field"] not in ("title", "content", "status"):
            return {"success": False, "error": f"不支持字段: {args['field']}"}
        entry[args["field"]] = args["value"]
        _save(work / "outline.json", {"entries": entries})
        return {"success": True}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已将大纲条目「{(args or {}).get('name', '')}」的「{(args or {}).get('field', '')}」修改为「{(args or {}).get('value', '')}」"
        return f"❌ 修改失败: {result.get('error')}"


class DeleteOutlineEntrySkill(Skill):
    @property
    def name(self) -> str: return "delete_outline_entry"
    @property
    def description(self) -> str: return "删除指定大纲条目（含子条目）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "条目名称"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "outline.json")
        entries = data.get("entries", [])
        name = args["name"]
        def _delete(entries):
            for i, e in enumerate(entries):
                if e.get("title") == name:
                    entries.pop(i)
                    return True
                if e.get("children") and _delete(e["children"]):
                    return True
            return False
        if not _delete(entries):
            return {"success": False, "error": f"未找到: {name}"}
        _save(work / "outline.json", {"entries": entries})
        return {"success": True}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除大纲条目「{(args or {}).get('name', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
