"""时间线技能 — 读取/修改事件。"""

import json
from pathlib import Path
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save, _date_sort_key


class GetTimelineSkill(Skill):
    @property
    def name(self) -> str: return "get_timeline"
    @property
    def description(self) -> str: return "获取作品时间线"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        return _load(_work_path(args.get("work", work_name)) / "timeline.json")
    def summarize(self, result, args=None):
        return "已读取时间线"


class UpdateTimelineEventSkill(Skill):
    @property
    def name(self) -> str: return "update_timeline_event"
    @property
    def description(self) -> str: return "修改时间线事件的 date/title/description"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "事件标题"},
                "field": {"type": "string", "description": "date/title/description"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["title", "field", "value"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "timeline.json")
        events = data.get("events", [])
        for e in events:
            if e.get("title") == args["title"]:
                e[args["field"]] = args["value"]
                events.sort(key=lambda x: _date_sort_key(x.get("date", "")))
                _save(work / "timeline.json", {"events": events})
                return {"success": True}
        return {"success": False, "error": f"未找到: {args['title']}"}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已将时间线事件「{(args or {}).get('title', '')}」的「{(args or {}).get('field', '')}」更新"
        return f"❌ 更新失败: {result.get('error')}"


class DeleteTimelineEventSkill(Skill):
    @property
    def name(self) -> str: return "delete_timeline_event"
    @property
    def description(self) -> str: return "删除指定时间线事件"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "事件标题"},
            },
            "required": ["title"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "timeline.json")
        events = data.get("events", [])
        title = args["title"]
        for i, e in enumerate(events):
            if e.get("title") == title:
                events.pop(i)
                _save(work / "timeline.json", {"events": events})
                return {"success": True}
        return {"success": False, "error": f"未找到: {title}"}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除时间线事件「{(args or {}).get('title', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
