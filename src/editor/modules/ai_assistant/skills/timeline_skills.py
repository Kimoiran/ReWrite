"""时间线技能 — 读取/修改事件（树形结构）。"""

import uuid

from .base_skill import Skill
from ._shared import _work_path, _load, _save, _date_sort_key, _fmt_nodes


def _load_era(work_name: str) -> str:
    """从 work.json 读取纪元名。"""
    import json
    work = _work_path(work_name)
    meta_path = work / "work.json"
    if meta_path.exists():
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            return m.get("date_era", "")
        except Exception:
            pass
    return ""


def _rebuild_tree(data: dict, era: str = "") -> dict:
    """将扁平的 events（含 parent_id）重建为树形返回给 AI。"""
    raw = data.get("events", [])
    id_map = {}
    roots = []
    for e in raw:
        eid = e.get("id", "")
        e["children"] = []
        id_map[eid] = e
    for e in raw:
        pid = e.get("parent_id", "")
        if pid and pid in id_map:
            id_map[pid]["children"].append(e)
        else:
            roots.append(e)
    # 按日期排序
    sk = lambda x: _date_sort_key(x.get("date", ""), era)
    roots.sort(key=sk)
    for e in id_map.values():
        e["children"].sort(key=sk)
    data["events"] = roots
    return data


def _tree_text(nodes, depth=0) -> str:
    """树形事件 -> 纯文本概览。"""
    lines = []
    indent = "  " * depth
    for e in nodes:
        title = e.get("title", "")
        date = e.get("date", "")
        desc = e.get("description", "")
        d_short = desc[:60].replace("\n", " ") if desc else ""
        lines.append(f"{indent}📅 {date}  {title}" + (f" — {d_short}..." if d_short else ""))
        if e.get("children"):
            lines.append(_tree_text(e["children"], depth + 1))
    return "\n".join(lines)


class CreateTimelineEventSkill(Skill):
    @property
    def name(self) -> str: return "create_timeline_event"
    @property
    def description(self) -> str: return "创建时间线事件（可指定父事件）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "事件标题"},
                "date": {"type": "string", "description": "日期，使用作品的纪元名+年号格式（如「神启1017年」「星历2371年」），元年=1年，纪元前用「前」字"},
                "description": {"type": "string", "description": "事件描述"},
                "parent_title": {"type": "string", "description": "（可选）父事件标题，不填则创建为根级事件"},
            },
            "required": ["title", "date"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "timeline.json")
        events = data.get("events", [])
        title = args["title"]
        date = args["date"]

        # 检查是否有同名事件（同级不重复）
        parent_title = args.get("parent_title", "").strip()
        new_id = uuid.uuid4().hex[:12]
        entry = {"id": new_id, "date": date, "title": title,
                 "description": args.get("description", ""),
                 "parent_id": "", "children": [],
                 "characters": [], "chapter_ref": ""}

        if parent_title:
            parent = None
            for e in events:
                if e.get("title") == parent_title:
                    parent = e
                    break
            if not parent:
                return {"success": False, "error": f"未找到父事件: {parent_title}"}
            entry["parent_id"] = parent["id"]
            parent.setdefault("children", []).append(new_id)

        events.append(entry)
        _save(work / "timeline.json", {"events": events})
        return {"success": True, "id": new_id, "title": title, "date": date}
    def summarize(self, result, args=None):
        if result.get("success"):
            t = (args or {}).get("title", "")
            d = (args or {}).get("date", "")
            p = (args or {}).get("parent_title", "")
            if p:
                return f"✅ 已创建时间线事件「{t}」（{d}），在「{p}」下"
            return f"✅ 已创建时间线事件「{t}」（{d}）"
        return f"❌ 创建失败: {result.get('error')}"


class GetTimelineSkill(Skill):
    @property
    def name(self) -> str: return "get_timeline"
    @property
    def description(self) -> str: return "获取作品时间线（树形结构，含父/子事件）"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        era = _load_era(args.get("work", work_name))
        data = _load(_work_path(args.get("work", work_name)) / "timeline.json")
        data = _rebuild_tree(data, era)
        return _fmt_nodes(data, {"description"})
    def summarize(self, result, args=None):
        events = result.get("events", [])
        total = 0
        def _count(ns):
            c = 0
            for e in ns:
                c += 1
                if e.get("children"):
                    c += _count(e["children"])
            return c
        total = _count(events)
        if not events:
            return "时间线为空"
        return f"时间线共 {total} 个事件（树形结构）：\n" + _tree_text(events)


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
                _save(work / "timeline.json", {"events": events})
                return {"success": True}
        return {"success": False, "error": f"未找到: {args['title']}"}
    def summarize(self, result, args=None):
        if result.get("success"):
            n = (args or {}).get("title", "")
            f = (args or {}).get("field", "")
            v = (args or {}).get("value", "")
            return f"✅ 已将时间线事件「{n}」的「{f}」更新为「{v[:200]}」"
        return f"❌ 更新失败: {result.get('error')}"


class DeleteTimelineEventSkill(Skill):
    @property
    def name(self) -> str: return "delete_timeline_event"
    @property
    def description(self) -> str: return "删除指定时间线事件（含其所有子事件）"
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

        # 扁平存储：children 是 ID 列表 ["abc", "def"]，先构建 ID→事件 映射
        id_map = {e.get("id", ""): e for e in events if e.get("id")}

        # 查找目标事件
        target = None
        for e in events:
            if e.get("title") == title:
                target = e
                break
        if not target:
            return {"success": False, "error": f"未找到: {title}"}

        # 递归收集所有后代 ID（children 字段存的是 ID 字符串）
        to_delete = set()
        def _collect_ids(eid):
            to_delete.add(eid)
            for child_id in id_map.get(eid, {}).get("children", []):
                _collect_ids(child_id)
        _collect_ids(target["id"])

        # 过滤掉要删除的 ID
        events[:] = [e for e in events if e.get("id") not in to_delete]
        _save(work / "timeline.json", {"events": events})
        return {"success": True, "deleted_count": len(to_delete)}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除时间线事件「{(args or {}).get('title', '')}」（含子事件）"
        return f"❌ 删除失败: {result.get('error')}"
