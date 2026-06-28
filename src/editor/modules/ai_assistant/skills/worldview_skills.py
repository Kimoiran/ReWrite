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
        parent_title = args.get("parent_title", "")
        if parent_title:
            parent = _find_entry(entries, parent_title)
            (parent.setdefault("children", []) if parent else entries).append(entry)
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
