"""Skill 注册表测试 —— 守住「32 个技能」这个对 AI 和 README 都成立的契约。

新增/删除技能时，这里的 EXPECTED 和 README 的「Skill 系统」表格要一起更新。
"""

import unittest

from src.editor.modules.ai_assistant.skills.registry import (
    execute_skill,
    get_all_skills,
    get_claude_tools,
    get_openai_tools,
    get_skill,
)

# 与 README「Skill 系统（共 32 个）」表格一一对应
EXPECTED_SKILLS = {
    # 人物卡 7
    "get_character_groups", "get_characters", "create_character",
    "update_character", "delete_character", "add_group", "delete_group",
    # 章节 6
    "get_chapters", "read_chapter", "create_chapter",
    "update_chapter", "rename_chapter", "delete_chapter",
    # 大纲 4
    "get_outline", "create_outline_entry",
    "update_outline_entry", "delete_outline_entry",
    # 时间线 4
    "create_timeline_event", "get_timeline",
    "update_timeline_event", "delete_timeline_event",
    # 世界观 4
    "get_worldview", "create_worldview_entry",
    "update_worldview_entry", "delete_worldview_entry",
    # 地图 6
    "get_map", "create_map_node", "update_map_node",
    "delete_map_node", "create_map_route", "delete_map_route",
    # 搜索 1
    "search_chapters",
}


class RegistryTest(unittest.TestCase):
    def test_registered_skills_match_expected_set(self):
        names = {s.name for s in get_all_skills()}
        self.assertEqual(names, EXPECTED_SKILLS)

    def test_skill_count(self):
        self.assertEqual(len(get_all_skills()), 32)

    def test_skill_names_are_unique(self):
        names = [s.name for s in get_all_skills()]
        self.assertEqual(len(names), len(set(names)))

    def test_every_skill_exposes_schema_and_description(self):
        for skill in get_all_skills():
            with self.subTest(skill=skill.name):
                self.assertTrue(skill.name)
                self.assertTrue(skill.description)
                schema = skill.input_schema
                self.assertIsInstance(schema, dict)
                self.assertEqual(schema.get("type"), "object")
                self.assertIn("properties", schema)


class LookupTest(unittest.TestCase):
    def test_lookup_by_exact_name(self):
        skill = get_skill("update_character")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "update_character")

    def test_lookup_tolerates_missing_underscores(self):
        """AI 偶尔会少写下划线，注册表要能容错匹配。"""
        self.assertIsNotNone(get_skill("updatecharacter"))
        self.assertIsNotNone(get_skill("create-outline-entry"))
        self.assertIsNotNone(get_skill("Get Characters"))

    def test_unknown_skill_returns_none(self):
        self.assertIsNone(get_skill("no_such_skill"))
        self.assertIsNone(get_skill(""))

    def test_execute_unknown_skill_returns_error_dict(self):
        result = execute_skill("no_such_skill", {})
        self.assertFalse(result["success"])
        self.assertIn("未知技能", result["error"])


class ToolSchemaTest(unittest.TestCase):
    def test_openai_tool_schema(self):
        tools = get_openai_tools()
        self.assertEqual(len(tools), 32)
        for tool in tools:
            self.assertEqual(tool["type"], "function")
            fn = tool["function"]
            self.assertIn(fn["name"], EXPECTED_SKILLS)
            self.assertIn("parameters", fn)

    def test_claude_tool_schema(self):
        tools = get_claude_tools()
        self.assertEqual(len(tools), 32)
        for tool in tools:
            self.assertIn(tool["name"], EXPECTED_SKILLS)
            self.assertIn("input_schema", tool)


if __name__ == "__main__":
    unittest.main()
