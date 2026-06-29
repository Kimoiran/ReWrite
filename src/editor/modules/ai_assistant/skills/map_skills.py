"""地图技能 — 节点和路线的 CRUD。"""

import uuid
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save


def _rebuild_tree(data: dict) -> dict:
    """将扁平的 nodes 重建为树形。"""
    raw = data.get("nodes", [])
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
    data["nodes"] = roots
    return data


def _tree_text(nodes, depth=0) -> str:
    """树形节点 -> 纯文本概览。"""
    lines = []
    indent = "  " * depth
    for n in nodes:
        nt = n.get("node_type", "?")
        name = n.get("name", "?")
        desc = n.get("description", "")
        d_short = desc[:50].replace("\n", " ") if desc else ""
        lines.append(f"{indent}📍 {name} ({nt})" + (f" — {d_short}..." if d_short else ""))
        if n.get("children"):
            lines.append(_tree_text(n["children"], depth + 1))
    return "\n".join(lines)


class GetMapSkill(Skill):
    @property
    def name(self) -> str: return "get_map"
    @property
    def description(self) -> str: return "获取作品地图（所有节点和路线）"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        data = _load(_work_path(args.get("work", work_name)) / "map.json")
        data = _rebuild_tree(data)
        return data
    def summarize(self, result, args=None):
        nodes = result.get("nodes", [])
        routes = result.get("routes", [])
        def _count(ns):
            c = 0
            for n in ns:
                c += 1
                if n.get("children"):
                    c += _count(n["children"])
            return c
        total = _count(nodes)
        parts = [f"地图共 {total} 个节点，{len(routes)} 条路线"]
        if total:
            parts.append(_tree_text(nodes))
        return "\n".join(parts)


class CreateMapNodeSkill(Skill):
    @property
    def name(self) -> str: return "create_map_node"
    @property
    def description(self) -> str: return "创建地图节点（国家/地区/城市/街区/地标）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "节点名称"},
                "node_type": {"type": "string", "description": "类型: country/region/city/district/poi"},
                "parent_name": {"type": "string", "description": "（可选）父节点名称"},
                "x": {"type": "number", "description": "（可选）X 坐标 0-1000，默认 500"},
                "y": {"type": "number", "description": "（可选）Y 坐标 0-1000，默认 500"},
                "description": {"type": "string", "description": "（可选）描述"},
            },
            "required": ["name", "node_type"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "map.json")
        nodes = data.get("nodes", [])
        parent_id = ""
        parent_name = args.get("parent_name", "").strip()
        if parent_name:
            for n in nodes:
                if n.get("name") == parent_name:
                    parent_id = n["id"]
                    break
            if not parent_id:
                return {"success": False, "error": f"未找到父节点: {parent_name}"}
        new_id = uuid.uuid4().hex[:12]
        entry = {
            "id": new_id,
            "name": args["name"],
            "node_type": args["node_type"],
            "x": args.get("x", 500.0),
            "y": args.get("y", 500.0),
            "parent_id": parent_id,
            "children": [],
            "description": args.get("description", ""),
            "tags": [],
            "color": "",
            "boundary": [],
        }
        nodes.append(entry)
        _save(work / "map.json", {"nodes": nodes, "routes": data.get("routes", [])})
        return {"success": True, "id": new_id, "name": args["name"]}
    def summarize(self, result, args=None):
        if result.get("success"):
            n = (args or {}).get("name", "")
            t = (args or {}).get("node_type", "")
            p = (args or {}).get("parent_name", "")
            if p:
                return f"✅ 已创建地图节点「{n}」({t})，在「{p}」下"
            return f"✅ 已创建地图节点「{n}」({t})"
        return f"❌ 创建失败: {result.get('error')}"


class UpdateMapNodeSkill(Skill):
    @property
    def name(self) -> str: return "update_map_node"
    @property
    def description(self) -> str: return "修改地图节点的 name/node_type/x/y/description"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "节点名称"},
                "field": {"type": "string", "description": "name/node_type/x/y/description"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "map.json")
        nodes = data.get("nodes", [])
        for n in nodes:
            if n.get("name") == args["name"]:
                field = args["field"]
                if field in ("x", "y"):
                    n[field] = float(args["value"])
                else:
                    n[field] = args["value"]
                _save(work / "map.json", {"nodes": nodes, "routes": data.get("routes", [])})
                return {"success": True}
        return {"success": False, "error": f"未找到节点: {args['name']}"}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已将节点「{(args or {}).get('name', '')}」的「{(args or {}).get('field', '')}」更新为「{(args or {}).get('value', '')}」"
        return f"❌ 更新失败: {result.get('error')}"


class DeleteMapNodeSkill(Skill):
    @property
    def name(self) -> str: return "delete_map_node"
    @property
    def description(self) -> str: return "删除地图节点（含其所有子节点和关联路线引用）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "节点名称"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "map.json")
        nodes = data.get("nodes", [])
        routes = data.get("routes", [])

        # 找到目标节点
        target = None
        for n in nodes:
            if n.get("name") == args["name"]:
                target = n
                break
        if not target:
            return {"success": False, "error": f"未找到节点: {args['name']}"}

        # 收集所有后代 ID
        to_delete = set()
        id_map = {n["id"]: n for n in nodes}
        def _collect(nid):
            to_delete.add(nid)
            for n in nodes:
                if n.get("parent_id") == nid:
                    _collect(n["id"])
        _collect(target["id"])

        nodes[:] = [n for n in nodes if n["id"] not in to_delete]
        # 清理路线引用
        for r in routes:
            r["nodes"] = [nid for nid in r.get("nodes", []) if nid not in to_delete]
        _save(work / "map.json", {"nodes": nodes, "routes": routes})
        return {"success": True, "deleted": len(to_delete)}
    def summarize(self, result, args=None):
        if result.get("success"):
            d = result.get("deleted", 1)
            return f"✅ 已删除节点「{(args or {}).get('name', '')}」（含 {d} 个子节点）"
        return f"❌ 删除失败: {result.get('error')}"


class CreateMapRouteSkill(Skill):
    @property
    def name(self) -> str: return "create_map_route"
    @property
    def description(self) -> str: return "创建地图路线（经过一系列节点的路径）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "路线名称"},
                "node_names": {"type": "string", "description": "经过的节点名，用 > 分隔（如「特因城 > 王城」）"},
                "color": {"type": "string", "description": "（可选）颜色，如 #e91e63"},
                "description": {"type": "string", "description": "（可选）路线描述"},
            },
            "required": ["name", "node_names"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "map.json")
        nodes = data.get("nodes", [])
        routes = data.get("routes", [])

        name = args["name"]
        parts = [p.strip() for p in args["node_names"].split(">")]
        node_ids = []
        for p in parts:
            found = None
            for n in nodes:
                if n.get("name") == p:
                    found = n["id"]
                    break
            if found:
                node_ids.append(found)
        if not node_ids:
            return {"success": False, "error": "未找到路径中的任何节点"}

        new_id = uuid.uuid4().hex[:12]
        waypoints = []
        for n in nodes:
            if n.get("id") in node_ids:
                waypoints.append([n.get("x", 500.0), n.get("y", 500.0)])
        entry = {
            "id": new_id,
            "name": name,
            "color": args.get("color", "#4a90d9"),
            "waypoints": waypoints,
            "description": args.get("description", ""),
        }
        routes.append(entry)
        _save(work / "map.json", {"nodes": nodes, "routes": routes})
        return {"success": True, "id": new_id, "name": name}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已创建路线「{(args or {}).get('name', '')}」"
        return f"❌ 创建失败: {result.get('error')}"


class DeleteMapRouteSkill(Skill):
    @property
    def name(self) -> str: return "delete_map_route"
    @property
    def description(self) -> str: return "删除地图路线"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "路线名称"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "map.json")
        routes = data.get("routes", [])
        old_len = len(routes)
        routes[:] = [r for r in routes if r.get("name") != args["name"]]
        if len(routes) == old_len:
            return {"success": False, "error": f"未找到路线: {args['name']}"}
        _save(work / "map.json", {"nodes": data.get("nodes", []), "routes": routes})
        return {"success": True}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除路线「{(args or {}).get('name', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
