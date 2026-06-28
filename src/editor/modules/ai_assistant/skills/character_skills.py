"""人物卡技能 — 创建/修改/分组。"""

import uuid
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save


def _find_group(nodes, name):
    for n in nodes:
        if n.get("is_group") and n.get("name") == name:
            return n
        if n.get("children"):
            found = _find_group(n["children"], name)
            if found:
                return found
    return None


class GetCharactersSkill(Skill):
    @property
    def name(self) -> str: return "get_characters"
    @property
    def description(self) -> str: return "获取人物设定卡（所有角色和分组）"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        return _load(_work_path(args.get("work", work_name)) / "characters.json")

    def summarize(self, result, args=None):
        return "已读取人物设定卡"


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
            return {"success": False, "error": f"未找到角色: {name}"}
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
        return f"❌ 修改失败: {result.get('error')}"


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
