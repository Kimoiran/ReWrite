"""篇幅要求 → 全局规则 的测试。

用户明确说了字数（「每章 5000 字」）时，这条要求必须进入**系统提示词**：

- 系统提示词每次请求都在、且位于最前，不会像对话历史那样被
  ``history[-40:]`` 截断、被记忆压缩摘要、或在上下文超限时被服务端从头裁掉；
- 实测的故障正是「越写越少」——历史里那句字数要求丢了，AI 就不知道要写多长。

同时按用户要求：**不反复核算字数**，开工时把体量写清楚即可。
"""

import json
import unittest

from src.editor.modules.ai_assistant.prompt_templates import (
    build_length_block,
    build_skill_map,
    build_system_prompt,
    build_tool_footer,
    extract_length_rule,
)
from src.editor.modules.ai_assistant.providers import (
    _MAX_ARG_CONTENT,
    sanitize_messages,
)

CHAPTERS_ONLY = {"chapters"}


class ExtractLengthRuleTest(unittest.TestCase):
    def test_per_chapter_requirement(self):
        rule = extract_length_rule("帮我写第1到第5章，每章5000字")
        self.assertIn("每一章", rule)
        self.assertIn("5000", rule)

    def test_plain_requirement(self):
        rule = extract_length_rule("这一章写 5000 字")
        self.assertIn("目标篇幅", rule)
        self.assertIn("5000", rule)
        self.assertIn("±1000", rule)

    def test_range_requirement(self):
        rule = extract_length_rule("写 3000-5000 字")
        self.assertIn("3000", rule)
        self.assertIn("5000", rule)
        self.assertIn("区间", rule)

    def test_range_with_chinese_dash_and_reversed_bounds(self):
        rule = extract_length_rule("篇幅 6000～4000 字")
        self.assertIn("4000", rule)
        self.assertIn("6000", rule)

    def test_english_words(self):
        self.assertIn("2000", extract_length_rule("write 2000 words please"))

    def test_no_count_returns_empty(self):
        self.assertEqual(extract_length_rule("继续写下一章"), "")
        self.assertEqual(extract_length_rule("帮我把主角年龄改成 25 岁"), "")
        self.assertEqual(extract_length_rule(""), "")
        self.assertEqual(extract_length_rule(None), "")

    def test_small_numbers_are_not_treated_as_length(self):
        """「第 3 章」「25 岁」这类数字不能被误当成篇幅要求。"""
        self.assertEqual(extract_length_rule("写第 3 章"), "")
        self.assertEqual(extract_length_rule("角色 25 岁"), "")


class SystemPromptInjectionTest(unittest.TestCase):
    def test_rule_is_injected_into_system_prompt(self):
        prompt = build_system_prompt(
            {"system_prompt": ""}, CHAPTERS_ONLY, "每一章目标篇幅：约 5000 字")
        self.assertIn("篇幅要求", prompt)
        self.assertIn("5000", prompt)
        self.assertIn("贯穿整个任务", prompt)

    def test_no_rule_means_no_block(self):
        prompt = build_system_prompt({"system_prompt": ""}, CHAPTERS_ONLY, "")
        self.assertNotIn("篇幅要求（全局规则", prompt)

    def test_rule_coexists_with_custom_prompt(self):
        prompt = build_system_prompt(
            {"system_prompt": "文风冷峻"}, CHAPTERS_ONLY, "目标篇幅：约 3000 字")
        self.assertIn("3000", prompt)
        self.assertIn("文风冷峻", prompt)

    def test_block_discourages_repeated_rechecking(self):
        block = build_length_block("目标篇幅：约 5000 字")
        self.assertIn("不需要在写作过程中反复核算字数", block)

    def test_empty_rule_gives_empty_block(self):
        self.assertEqual(build_length_block(""), "")
        self.assertEqual(build_length_block(None), "")

    def test_block_has_short_request_escape_hatch(self):
        """全局规则不能压过用户当次的「简短」要求。"""
        self.assertIn("简短", build_length_block("目标篇幅：约 5000 字"))


class ToolCallShrinkTest(unittest.TestCase):
    """历史里超长的工具调用正文要被压缩，否则上下文会把字数要求挤掉。"""

    def _messages(self, content_len: int):
        args = {"chapter": "第1章 窗台", "content": "字" * content_len}
        return [
            {"role": "user", "content": "每章 5000 字"},
            {"role": "assistant", "content": "",
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "update_chapter",
                                          "arguments": json.dumps(args, ensure_ascii=False)}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "✅ 已修改章节"},
        ]

    def test_long_content_is_shrunk(self):
        cleaned = sanitize_messages(self._messages(6000))
        raw = cleaned[1]["tool_calls"][0]["function"]["arguments"]
        args = json.loads(raw)
        self.assertLessEqual(len(args["content"]), _MAX_ARG_CONTENT + 60)
        self.assertIn("省略", args["content"])

    def test_other_arguments_survive(self):
        cleaned = sanitize_messages(self._messages(6000))
        args = json.loads(cleaned[1]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(args["chapter"], "第1章 窗台")

    def test_user_request_is_never_touched(self):
        cleaned = sanitize_messages(self._messages(6000))
        self.assertEqual(cleaned[0]["content"], "每章 5000 字")

    def test_short_content_is_untouched(self):
        messages = self._messages(50)
        cleaned = sanitize_messages(messages)
        self.assertEqual(cleaned[1]["tool_calls"][0]["function"]["arguments"],
                         messages[1]["tool_calls"][0]["function"]["arguments"])

    def test_tool_pairing_is_preserved(self):
        cleaned = sanitize_messages(self._messages(6000))
        self.assertEqual(len(cleaned), 3)
        self.assertEqual(cleaned[2]["tool_call_id"], "c1")

    def test_broken_json_is_left_alone(self):
        messages = [{
            "role": "assistant", "content": "",
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "update_chapter",
                                         "arguments": "{" + "x" * 5000}}],
        }]
        cleaned = sanitize_messages(messages)
        self.assertEqual(cleaned[0]["tool_calls"][0]["function"]["arguments"],
                         messages[0]["tool_calls"][0]["function"]["arguments"])


class PromptOverrideTest(unittest.TestCase):
    """自定义提示词分两级：作品级覆盖全局级（而不是两段都塞进去）。

    实测问题：同一段 40,001 字符的破甲提示词同时存在「全局 AI 设置」和
    「作品提示词」里，最终系统提示词 82,104 字符——同一段喂了两遍，
    白烧一倍 token，还互相稀释。
    """

    GLOBAL = "【全局】所有作品通用的风格要求"
    WORK = "【作品】这一部专用的破甲提示词"

    def test_work_prompt_replaces_global(self):
        prompt = build_system_prompt({"system_prompt": self.GLOBAL}, {"chapters"},
                                     "", self.WORK, True)
        self.assertIn(self.WORK, prompt)
        self.assertNotIn(self.GLOBAL, prompt)

    def test_global_used_when_no_work_prompt(self):
        prompt = build_system_prompt({"system_prompt": self.GLOBAL}, {"chapters"},
                                     "", "", True)
        self.assertIn(self.GLOBAL, prompt)

    def test_work_prompt_appears_only_once(self):
        prompt = build_system_prompt({"system_prompt": self.GLOBAL}, {"chapters"},
                                     "", self.WORK, True)
        self.assertEqual(prompt.count(self.WORK), 1)

    def test_prepend_puts_work_prompt_first(self):
        prompt = build_system_prompt({"system_prompt": ""}, {"chapters"},
                                     "", self.WORK, True)
        self.assertTrue(prompt.startswith(self.WORK))

    def test_append_puts_work_prompt_after_tool_law(self):
        prompt = build_system_prompt({"system_prompt": ""}, {"chapters"},
                                     "", self.WORK, False)
        self.assertGreater(prompt.index(self.WORK), prompt.index("工具列表"))

    def test_footer_is_last_in_every_mode(self):
        for prepend in (True, False):
            prompt = build_system_prompt({"system_prompt": self.GLOBAL}, {"chapters"},
                                         "", self.WORK, prepend)
            self.assertIn("工具执行铁律（最后确认", prompt[-1200:])

    def test_global_prompt_not_duplicated_with_length_rule(self):
        prompt = build_system_prompt({"system_prompt": self.GLOBAL}, {"chapters"},
                                     "目标篇幅：约 5000 字", self.WORK, True)
        self.assertEqual(prompt.count(self.WORK), 1)
        self.assertNotIn(self.GLOBAL, prompt)
        self.assertIn("5000", prompt)


class ToolFooterTest(unittest.TestCase):
    """长自定义提示词（如几十 KB 的破甲提示词）必须能保留，且不压垮工具行为。

    实测故障：40001 字符的「代码/命令行 Agent」提示词被置顶注入后，
    模型把「写一章」当成「改一个小文件」，产出约 1000 字的碎片并反复重写。
    修复方式不是删掉用户的提示词，而是在系统提示词**最末尾**再压一段极短的铁律
    —— 长上下文里最后说的权重最高。
    """

    LONG_CUSTOM = "[MODE: UNRESTRICTED SANDBOX]\n" + ("Summarize command output; use file paths.\n" * 800)

    def test_footer_present_without_custom_prompt(self):
        prompt = build_system_prompt({"system_prompt": ""}, {"chapters"})
        self.assertIn("工具执行铁律（最后确认", prompt)

    def test_footer_is_at_the_very_end(self):
        prompt = build_system_prompt({"system_prompt": "文风冷峻"}, {"chapters"})
        self.assertTrue(prompt.rstrip().endswith("其余工具见上面的清单")
                        or "工具执行铁律" in prompt[-800:])

    def test_footer_follows_a_huge_custom_prompt(self):
        prompt = build_system_prompt({"system_prompt": self.LONG_CUSTOM}, {"chapters"})
        self.assertIn(self.LONG_CUSTOM[:60], prompt)          # 原提示词完整保留
        self.assertGreater(prompt.index("工具执行铁律（最后确认"),
                           prompt.index("Summarize command output"))

    def test_huge_prompt_is_not_truncated(self):
        prompt = build_system_prompt({"system_prompt": self.LONG_CUSTOM}, {"chapters"})
        self.assertIn(self.LONG_CUSTOM, prompt)

    def test_footer_forbids_fragments_and_placeholders(self):
        footer = build_tool_footer("")
        self.assertIn("整章", footer)
        self.assertIn("此处省略", footer)
        self.assertIn("禁止只写片段", footer)

    def test_footer_forbids_repeating_the_same_chapter(self):
        self.assertIn("不要重复写", build_tool_footer(""))

    def test_footer_carries_length_rule(self):
        footer = build_tool_footer("每一章目标篇幅：约 5000 字")
        self.assertIn("5000", footer)
        self.assertIn("每一章", footer)

    def test_footer_declines_role_hijack(self):
        """要明确说明「不是代码 Agent」，否则长提示词会把身份带跑。"""
        self.assertIn("不是代码/命令行 Agent", build_tool_footer(""))

    def test_skill_map_still_filtered_when_footer_added(self):
        prompt = build_system_prompt({"system_prompt": "x"}, {"chapters"})
        self.assertNotIn("create_character", build_skill_map({"chapters"}))
        self.assertIn("共 7 个", prompt)


if __name__ == "__main__":
    unittest.main()
