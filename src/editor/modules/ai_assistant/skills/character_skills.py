"""人物卡技能 — 创建/修改/分组。"""

import uuid
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save, _fmt_nodes


def _find_group(nodes, name):
    for n in nodes:
        if n.get("is_group") and n.get("name") == name:
            return n
        if n.get("children"):
            found = _find_group(n["children"], name)
            if found:
                return found
    return None


def _collect_char_names(nodes) -> list[str]:
    """收集所有角色名称（用于错误提示辅助 AI 自修正）。"""
    names = []
    def _walk(ns):
        for n in ns:
            if not n.get("is_group"):
                names.append(n.get("name", ""))
            if n.get("children"):
                _walk(n["children"])
    _walk(nodes)
    return names


class GetCharacterGroupsSkill(Skill):
    @property
    def name(self) -> str: return "get_character_groups"
    @property
    def description(self) -> str: return "获取人物分组列表（仅分组名和各组角色数，不含详细字段）"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        data = _load(_work_path(args.get("work", work_name)) / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        groups = []
        def _walk(ns, depth=0):
            for n in ns:
                if n.get("is_group"):
                    # 统计该分组下所有角色（含子分组递归）
                    def _count(nn):
                        c = 0
                        for x in nn:
                            if not x.get("is_group"):
                                c += 1
                            if x.get("children"):
                                c += _count(x["children"])
                        return c
                    groups.append({
                        "name": n.get("name", ""),
                        "count": _count(n.get("children", [])),
                        "depth": depth,
                    })
                    _walk(n.get("children", []), depth + 1)
        _walk(nodes)
        return {"groups": groups, "total_groups": len(groups)}
    def summarize(self, result, args=None):
        gs = result.get("groups", [])
        return f"共 {result.get('total_groups', 0)} 个分组：" + "、".join(f"{g['name']}({g['count']}人)" for g in gs)


class GetCharactersSkill(Skill):
    @property
    def name(self) -> str: return "get_characters"
    @property
    def description(self) -> str: return "获取人物设定卡（可指定分组过滤）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "group": {"type": "string", "description": "（可选）分组名称，仅返回该分组下的角色"},
            },
            "required": [],
        }
    def execute(self, args, work_name=""):
        data = _load(_work_path(args.get("work", work_name)) / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        group = args.get("group", "").strip()
        if group:
            parent = _find_group(nodes, group)
            if parent:
                result = {"nodes": _fmt_nodes(parent.get("children", []), {"appearance","personality","background","goals","notes"}), "group": group, "count": len(parent.get("children", []))}
                return result
            return {"nodes": [], "group": group, "count": 0, "warning": f"未找到分组: {group}"}
        return {"nodes": _fmt_nodes(nodes, {"appearance","personality","background","goals","notes"})}

    def summarize(self, result, args=None):
        g = args.get("group", "") if args else ""
        nodes = result.get("nodes", [])
        if g:
            return f"已读取分组「{g}」({result.get('count', 0)} 人)【完整数据】：\n" + self._compact(nodes, full=True)
        return "已读取人物设定卡（概览）：\n" + self._compact(nodes, full=False)

    @staticmethod
    def _compact(nodes, indent=0, full=False) -> str:
        """生成人物数据概览。

        full=True（指定分组时）：含所有字段的完整数据。
        full=False（全部角色时）：仅名称/年龄/身份概览。
        """
        lines = []
        prefix = "  " * indent
        for n in nodes:
            if n.get("is_group"):
                lines.append(f"{prefix}📁 {n['name']}")
                children = n.get("children", [])
                if children:
                    sub = GetCharactersSkill._compact(children, indent + 1, full)
                    lines.append(sub)
            else:
                name = n.get("name", "?")
                age = n.get("age", "")
                occ = n.get("occupation", "")
                tag = f" ({age}, {occ})" if age and occ else f" ({age or occ})" if (age or occ) else ""
                lines.append(f"{prefix}👤 {name}{tag}")
                if full:
                    flags = []
                    for f in ("appearance", "personality", "background", "goals", "notes"):
                        v = n.get(f, "")
                        if v:
                            short = v.replace("\n", " ").replace("|", "丨")
                            flags.append(f"【{f}】{short}")
                    if flags:
                        for flag in flags:
                            lines.append(f"{prefix}  {flag}")
        return "\n".join(lines)


class CreateCharacterSkill(Skill):
    """创建新角色。"""

    @property
    def name(self) -> str:
        return "create_character"

    @property
    def description(self) -> str:
        return "创建新角色，可指定所属分组"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "group": {"type": "string", "description": "所属分组名称（不存在会自动创建）"},
                "age": {"type": "string", "description": "年龄"},
                "gender": {"type": "string", "description": "性别"},
                "occupation": {"type": "string", "description": "职业/身份"},
                "appearance": {"type": "string", "description": "外貌描述"},
                "personality": {"type": "string", "description": "性格特征"},
                "background": {"type": "string", "description": "背景故事"},
                "goals": {"type": "string", "description": "动机/目标"},
                "notes": {"type": "string", "description": "备注"},
            },
            "required": ["name"],
        }

    def execute(self, args: dict[str, Any], work_name: str = "") -> dict:
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        new_id = uuid.uuid4().hex[:12]

        entry = {
            "id": new_id, "name": args["name"], "is_group": False,
            "aliases": args.get("aliases", ""), "age": args.get("age", ""),
            "gender": args.get("gender", ""), "occupation": args.get("occupation", ""),
            "appearance": args.get("appearance", ""), "personality": args.get("personality", ""),
            "background": args.get("background", ""), "goals": args.get("goals", ""),
            "notes": args.get("notes", ""), "relationships": [], "children": [],
        }

        group_name = args.get("group", "")
        if group_name:
            parent = _find_group(nodes, group_name)
            if parent:
                parent.setdefault("children", []).append(entry)
            else:
                gid = uuid.uuid4().hex[:12]
                nodes.append({"id": gid, "name": group_name, "is_group": True, "children": [entry]})
        else:
            nodes.append(entry)

        _save(work / "characters.json", {"nodes": nodes})
        return {"success": True, "id": new_id, "name": args["name"]}

    def summarize(self, result, args=None):
        n = (args or {}).get("name", "")
        g = (args or {}).get("group", "")
        if g:
            return f"✅ 已在「{g}」分组下创建角色「{n}」"
        return f"✅ 已创建角色「{n}」"


class UpdateCharacterSkill(Skill):
    """修改角色字段。"""

    @property
    def name(self) -> str:
        return "update_character"

    @property
    def description(self) -> str:
        return "修改角色字段值"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "field": {"type": "string", "description": "字段名: name/aliases/age/gender/occupation/appearance/personality/background/goals/notes"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],
        }

    def execute(self, args: dict[str, Any], work_name: str = "") -> dict:
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []

        name, field, value = args["name"], args["field"], args["value"]
        valid = {"name", "aliases", "age", "gender", "occupation", "appearance", "personality", "background", "goals", "notes"}
        if field not in valid:
            return {"success": False, "error": f"不支持字段: {field}"}

        def _find(nodes):
            for n in nodes:
                if n.get("name") == name and not n.get("is_group"):
                    return n
                if n.get("children"):
                    f = _find(n["children"])
                    if f:
                        return f
            return None

        node = _find(nodes)
        if not node:
            existing = _collect_char_names(nodes)
            return {"success": False, "error": f"未找到角色: {name}", "existing": existing}
        old = node.get(field, "")
        node[field] = value
        _save(work / "characters.json", {"nodes": nodes})
        return {"success": True, "old": old, "new": value}

    def summarize(self, result, args=None):
        n = (args or {}).get("name", "")
        f = (args or {}).get("field", "")
        v = (args or {}).get("value", "")
        if result.get("success"):
            return f"✅ 已将「{n}」的「{f}」修改为「{v}」"
        existing = result.get("existing", [])
        hint = f"。现有角色: {', '.join(existing)}" if existing else ""
        return f"❌ 修改失败: {result.get('error')}{hint}"


class AddGroupSkill(Skill):
    """创建分组。"""

    @property
    def name(self) -> str:
        return "add_group"

    @property
    def description(self) -> str:
        return "创建人物分组/文件夹"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "分组名称"},
            },
            "required": ["name"],
        }

    def execute(self, args: dict[str, Any], work_name: str = "") -> dict:
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        gid = uuid.uuid4().hex[:12]
        nodes.append({"id": gid, "name": args["name"], "is_group": True, "children": []})
        _save(work / "characters.json", {"nodes": nodes})
        return {"success": True, "id": gid, "name": args["name"]}

    def summarize(self, result, args=None):
        return f"✅ 已创建分组「{(args or {}).get('name', '')}」"


class DeleteCharacterSkill(Skill):
    @property
    def name(self) -> str: return "delete_character"
    @property
    def description(self) -> str: return "删除指定角色（含其所有数据）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        name = args["name"]
        def _delete(nodes):
            for i, n in enumerate(nodes):
                if not n.get("is_group") and n.get("name") == name:
                    nodes.pop(i)
                    return True
                if n.get("children") and _delete(n["children"]):
                    return True
            return False
        if not _delete(nodes):
            existing = _collect_char_names(nodes)
            return {"success": False, "error": f"未找到角色: {name}", "existing": existing}
        _save(work / "characters.json", {"nodes": nodes})
        return {"success": True, "name": name}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除角色「{(args or {}).get('name', '')}」"
        existing = result.get("existing", [])
        hint = f"。现有角色: {', '.join(existing)}" if existing else ""
        return f"❌ 删除失败: {result.get('error')}{hint}"


class DeleteGroupSkill(Skill):
    @property
    def name(self) -> str: return "delete_group"
    @property
    def description(self) -> str: return "删除指定分组（含其下所有子条目和角色）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "分组名称"},
            },
            "required": ["name"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []
        name = args["name"]
        def _delete(nodes):
            for i, n in enumerate(nodes):
                if n.get("is_group") and n.get("name") == name:
                    nodes.pop(i)
                    return True
                if n.get("children") and _delete(n["children"]):
                    return True
            return False
        if not _delete(nodes):
            return {"success": False, "error": f"未找到分组: {name}"}
        _save(work / "characters.json", {"nodes": nodes})
        return {"success": True, "name": name}
    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除分组「{(args or {}).get('name', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
