"""模块门控测试 —— 回归「关闭的功能 AI 还在写」。

根因：``get_openai_tools()`` 无条件返回全部 32 个工具，从不检查
work.json 的 ``modules``，于是关掉人物卡后 AI 照样调用 create_character。
"""

import unittest

from src.editor.modules.ai_assistant.prompt_templates import (
    build_skill_map,
    build_system_prompt,
    build_tool_law,
)
from src.editor.modules.ai_assistant.skills.registry import (
    SKILL_MODULES,
    TOOL_MODULE,
    allowed_modules,
    get_all_skills,
    get_claude_tools,
    get_openai_tools,
    get_skills_for_modules,
    skill_module,
    tool_enabled,
)

CHAPTER_ONLY = {"chapters"}
CHAPTERS_AND_CHARACTERS = {"chapters", "characters"}


class ModuleMappingTest(unittest.TestCase):
    def test_every_skill_has_a_module(self):
        """新增技能必须同时在 SKILL_MODULES 里登记，否则门控会漏掉它。"""
        registered = {s.name for s in get_all_skills()}
        self.assertEqual(registered, set(TOOL_MODULE))

    def test_skill_module_lookup(self):
        self.assertEqual(skill_module("update_chapter"), "chapters")
        self.assertEqual(skill_module("create_character"), "characters")
        self.assertEqual(skill_module("create_map_node"), "map")
        self.assertIsNone(skill_module("no_such_skill"))

    def test_search_chapters_belongs_to_chapters(self):
        self.assertEqual(skill_module("search_chapters"), "chapters")


class ToolFilteringTest(unittest.TestCase):
    def test_no_modules_means_everything(self):
        self.assertEqual(len(get_openai_tools()), 32)
        self.assertEqual(len(get_openai_tools(None)), 32)

    def test_chapters_only_keeps_seven_tools(self):
        tools = get_openai_tools(CHAPTER_ONLY)
        names = {t["function"]["name"] for t in tools}
        self.assertEqual(len(tools), 7)
        self.assertIn("update_chapter", names)
        self.assertIn("search_chapters", names)
        self.assertNotIn("create_character", names)
        self.assertNotIn("create_map_node", names)

    def test_two_modules(self):
        tools = get_openai_tools(CHAPTERS_AND_CHARACTERS)
        self.assertEqual(len(tools), 7 + 7)

    def test_claude_tools_filtered_too(self):
        tools = get_claude_tools(CHAPTER_ONLY)
        self.assertEqual(len(tools), 7)
        self.assertNotIn("create_map_node", {t["name"] for t in tools})

    def test_skills_for_modules(self):
        names = {s.name for s in get_skills_for_modules(CHAPTER_ONLY)}
        self.assertEqual(names, set(SKILL_MODULES["chapters"]))


class ToolEnabledTest(unittest.TestCase):
    def test_disabled_module_blocks_write_tool(self):
        self.assertFalse(tool_enabled("create_character", CHAPTER_ONLY))
        self.assertFalse(tool_enabled("delete_character", CHAPTER_ONLY))
        self.assertFalse(tool_enabled("create_map_node", CHAPTER_ONLY))

    def test_enabled_module_allows(self):
        self.assertTrue(tool_enabled("create_character", CHAPTERS_AND_CHARACTERS))

    def test_chapters_always_available(self):
        """章节是必选模块：即使 work.json 里漏了也要能用。"""
        self.assertTrue(tool_enabled("update_chapter", {"map"}))
        self.assertIn("chapters", allowed_modules({"map"}))

    def test_none_means_unrestricted(self):
        self.assertTrue(tool_enabled("create_character", None))

    def test_unknown_tool_not_blocked(self):
        """未知工具交给注册表报「未知技能」，不在这里拦截。"""
        self.assertTrue(tool_enabled("no_such_skill", CHAPTER_ONLY))


class PromptFilteringTest(unittest.TestCase):
    def test_skill_map_lists_only_enabled_tools(self):
        text = build_skill_map(CHAPTER_ONLY)
        self.assertIn("update_chapter", text)
        self.assertNotIn("create_character", text)
        self.assertNotIn("人物卡", text)

    def test_skill_map_reports_correct_total(self):
        self.assertIn("共 7 个", build_skill_map(CHAPTER_ONLY))
        self.assertIn("共 14 个", build_skill_map(CHAPTERS_AND_CHARACTERS))
        self.assertIn("共 32 个", build_skill_map(None))

    def test_system_prompt_excludes_disabled_modules(self):
        prompt = build_system_prompt({"system_prompt": ""}, CHAPTER_ONLY)
        self.assertIn("update_chapter", prompt)
        self.assertNotIn("create_character", prompt)

    def test_system_prompt_keeps_custom_text(self):
        prompt = build_system_prompt({"system_prompt": "文风冷峻"}, CHAPTER_ONLY)
        self.assertIn("文风冷峻", prompt)

    def test_tool_law_mentions_unavailable_modules(self):
        self.assertIn("未列出的功能本作品未启用", build_tool_law(CHAPTER_ONLY))


class LengthRuleTest(unittest.TestCase):
    """篇幅规则必须写进硬编码铁律，避免被自定义提示词覆盖掉。

    语义是「开工就按目标体量写，不必反复核算」——不要求 AI 写完再回头量字数。
    """

    def test_length_rule_is_global(self):
        law = build_tool_law(CHAPTER_ONLY)
        self.assertIn("5000 字", law)
        self.assertIn("贯穿整个任务的全局规则", law)

    def test_tolerance_is_stated(self):
        self.assertIn("±1000 字", build_tool_law(CHAPTER_ONLY))

    def test_no_repeated_rechecking(self):
        """明确要求：不反复检查字数。"""
        self.assertIn("反复核算字数", build_tool_law(CHAPTER_ONLY))

    def test_multi_chapter_consistency_rule(self):
        self.assertIn("各章体量保持一致", build_tool_law(CHAPTER_ONLY))

    def test_padding_is_discouraged(self):
        self.assertIn("注水", build_tool_law(CHAPTER_ONLY))

    def test_existing_chapters_guidance_present(self):
        law = build_tool_law(CHAPTER_ONLY)
        self.assertIn("existing_chapters", law)


if __name__ == "__main__":
    unittest.main()
