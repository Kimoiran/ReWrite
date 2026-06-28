"""大纲技能 — 读取/修改条目。"""

from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save


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
        return _load(_work_path(args.get("work", work_name)) / "outline.json")
    def summarize(self, result, args=None):
        return "已读取大纲"


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
