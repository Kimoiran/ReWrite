"""世界观技能 — 读取/创建条目。"""

import uuid
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save


def _find_entry(entries, title):
    for e in entries:
        if e.get("title") == title:
            return e
        if e.get("children"):
            f = _find_entry(e["children"], title)
            if f:
                return f
    return None


class GetWorldviewSkill(Skill):
    @property
    def name(self) -> str: return "get_worldview"
    @property
    def description(self) -> str: return "获取世界观"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        return _load(_work_path(args.get("work", work_name)) / "worldview.json")
    def summarize(self, result, args=None):
        return "已读取世界观"


class UpdateWorldviewEntrySkill(Skill):
    @property
    def name(self) -> str: return "update_worldview_entry"
    @property
    def description(self) -> str: return "修改世界观(worldview)条目的 title/content"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "条目标题"},
                "field": {"type": "string", "description": "title/content"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        path = work / "worldview.json"
        if not path.exists():
            _save(path, {"entries": []})
        data = _load(path)
        entries = data.get("entries", [])
        entry = _find_entry(entries, args["name"])
        if not entry:
            return {"success": False, "error": f"未找到世界观条目: {args['name']}"}
        if args["field"] not in ("title", "content"):
            return {"success": False, "error": f"不支持字段: {args['field']}"}
        entry[args["field"]] = args["value"]
        _save(path, {"entries": entries})
        return {"success": True}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已将世界观条目「{(args or {}).get('name', '')}」的「{(args or {}).get('field', '')}」更新"
        return f"❌ 更新失败: {result.get('error')}"


class CreateWorldviewEntrySkill(Skill):
    @property
    def name(self) -> str: return "create_worldview_entry"
    @property
    def description(self) -> str: return "创建世界观条目"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "条目标题"},
                "content": {"type": "string", "description": "内容（HTML）"},
                "parent_title": {"type": "string", "description": "父条目标题（可选，不填则创建在根级别）"},
            },
            "required": ["title"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "worldview.json")
        entries = data.get("entries", [])
        entry = {"id": uuid.uuid4().hex[:12], "title": args["title"],
                 "content": args.get("content", "<p></p>"), "children": [],
                 "order": len(entries)}
        # 检查同级下是否有同名条目，防止重复创建
        parent_title = args.get("parent_title", "")
        siblings = entries
        if parent_title:
            parent = _find_entry(entries, parent_title)
            if parent:
                siblings = parent.get("children", [])
        for s in siblings:
            if s.get("title") == args["title"]:
                return {"success": True, "id": s["id"], "title": args["title"],
                        "_notice": "条目已存在，跳过创建"}

        if parent_title:
            if parent:
                parent.setdefault("children", []).append(entry)
        else:
            entries.append(entry)
        _save(work / "worldview.json", {"entries": entries})
        return {"success": True, "id": entry["id"], "title": args["title"]}
    def summarize(self, result, args=None):
        n = (args or {}).get("title", "")
        p = (args or {}).get("parent_title", "")
        if p:
            return f"✅ 已在「{p}」下创建世界观条目「{n}」"
        return f"✅ 已创建世界观条目「{n}」"


class DeleteWorldviewEntrySkill(Skill):
    @property
    def name(self) -> str: return "delete_worldview_entry"
    @property
    def description(self) -> str: return "删除指定世界观条目（含子条目）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "条目标题"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "worldview.json")
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
        _save(work / "worldview.json", {"entries": entries})
        return {"success": True}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除世界观条目「{(args or {}).get('name', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
