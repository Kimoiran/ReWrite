"""思考过程与记忆测试。

规则（本次修复后固化）：

1. 思考过程**保留显示**（可回看），但**绝不发回模型**；
2. 流式拼接只在标题上出现一次 🧠，不会堆成一片大脑；
3. 压缩记忆时先剥离思考过程，并保住「任务最开始的要求」。
"""

import unittest

from src.editor.modules.ai_assistant.agent import AIAgent
from src.editor.modules.ai_assistant.orchestrator import AIOrchestrator
from src.editor.modules.ai_assistant.providers import (
    sanitize_messages,
    strip_reasoning,
)
from src.editor.modules.ai_assistant.ui.chat_panel import (
    ChatPanel,
    merge_reasoning_text,
)

MARKED = "<!--REASONING-->\n我先想想怎么开头\n<!--/REASONING-->\n\n正文第一段"


class MergeReasoningTest(unittest.TestCase):
    def test_repeated_chunks_do_not_pile_up_brain_icons(self):
        """回归：旧实现每个片段都重拼「🧠 + 全文」，屏幕上全是大脑。"""
        text = ""
        for chunk in ["想", "一", "下", "剧", "情"]:
            text = merge_reasoning_text(text, chunk)
        self.assertEqual(text, "想一下剧情")
        self.assertEqual(text.count("🧠"), 0)

    def test_empty_chunk_keeps_current(self):
        self.assertEqual(merge_reasoning_text("已有", ""), "已有")
        self.assertEqual(merge_reasoning_text("", ""), "")

    def test_none_current_is_tolerated(self):
        self.assertEqual(merge_reasoning_text(None, "新"), "新")

    def test_limit_keeps_tail_with_marker(self):
        out = merge_reasoning_text("啊" * 50, "尾", limit=10)
        self.assertTrue(out.startswith("…（前段略）\n"))
        self.assertTrue(out.endswith("尾"))
        self.assertLessEqual(len(out), 10 + len("…（前段略）\n"))


class StripReasoningTest(unittest.TestCase):
    def test_removes_block_keeps_body(self):
        self.assertEqual(strip_reasoning(MARKED), "正文第一段")

    def test_text_without_marker_unchanged(self):
        self.assertEqual(strip_reasoning("普通回复"), "普通回复")

    def test_non_string_unchanged(self):
        self.assertIsNone(strip_reasoning(None))
        self.assertEqual(strip_reasoning(123), 123)

    def test_only_reasoning_leaves_empty(self):
        self.assertEqual(
            strip_reasoning("<!--REASONING-->\n只有推理\n<!--/REASONING-->"), "")


class SanitizeMessagesTest(unittest.TestCase):
    def test_reasoning_stripped_from_every_message(self):
        msgs = [
            {"role": "user", "content": "写 5000 字"},
            {"role": "assistant", "content": MARKED},
        ]
        cleaned = sanitize_messages(msgs)
        self.assertEqual(cleaned[0]["content"], "写 5000 字")
        self.assertEqual(cleaned[1]["content"], "正文第一段")
        self.assertNotIn("REASONING", str(cleaned))

    def test_assistant_message_with_only_reasoning_is_dropped(self):
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "<!--REASONING-->\n纯推理\n<!--/REASONING-->"},
        ]
        self.assertEqual(len(sanitize_messages(msgs)), 1)

    def test_tool_call_message_is_kept_even_if_content_empty(self):
        """assistant/tool 必须成对，不能为了省 token 把工具调用消息删掉。"""
        msgs = [
            {"role": "assistant", "content": "<!--REASONING-->\n纯推理\n<!--/REASONING-->",
             "tool_calls": [{"id": "1", "type": "function",
                             "function": {"name": "get_chapters", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "1", "content": "ok"},
        ]
        cleaned = sanitize_messages(msgs)
        self.assertEqual(len(cleaned), 2)
        self.assertEqual(cleaned[0]["content"], "")
        self.assertIn("tool_calls", cleaned[0])

    def test_system_message_preserved(self):
        msgs = [{"role": "system", "content": "你是助手"}]
        self.assertEqual(sanitize_messages(msgs)[0]["content"], "你是助手")

    def test_claude_content_blocks_untouched(self):
        """Claude 的 content 是 block 列表，不能按字符串处理。"""
        blocks = [{"type": "text", "text": "hi"}]
        msgs = [{"role": "user", "content": blocks}]
        self.assertIs(sanitize_messages(msgs)[0]["content"], blocks)

    def test_original_list_not_mutated(self):
        msgs = [{"role": "assistant", "content": MARKED}]
        sanitize_messages(msgs)
        self.assertIn("REASONING", msgs[0]["content"])

    def test_empty_input(self):
        self.assertEqual(sanitize_messages([]), [])


class SplitReasoningTest(unittest.TestCase):
    def test_splits_marker(self):
        reasoning, body = AIOrchestrator.split_reasoning(MARKED)
        self.assertEqual(reasoning, "我先想想怎么开头")
        self.assertEqual(body, "正文第一段")

    def test_without_marker(self):
        self.assertEqual(AIOrchestrator.split_reasoning("正文"), ("", "正文"))

    def test_empty(self):
        self.assertEqual(AIOrchestrator.split_reasoning(""), ("", ""))

    def test_fallback_render_keeps_reasoning_visible(self):
        html = AIOrchestrator.render_message(MARKED)
        self.assertIn("思考过程", html)
        self.assertIn("我先想想怎么开头", html)
        self.assertIn("正文第一段", html)


class ReasoningBlockHtmlTest(unittest.TestCase):
    def test_escapes_html_injection(self):
        html = ChatPanel._reasoning_block_html("<img src=x onerror=alert(1)>")
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_newlines_become_breaks(self):
        html = ChatPanel._reasoning_block_html("第一行\n第二行")
        self.assertIn("第一行<br>第二行", html)

    def test_label_present(self):
        self.assertIn("🧠 思考过程", ChatPanel._reasoning_block_html("x"))


class CompressMemoryTest(unittest.TestCase):
    def _agent_with_history(self):
        agent = AIAgent({}, work_name="")     # work_name 为空 → 不落盘
        agent.history = [{"role": "user",
                          "content": "帮我写 10 章，每章 5000 字"}]
        for i in range(60):
            agent.history.append({"role": "assistant", "content": MARKED})
            agent.history.append({"role": "user", "content": f"继续写第 {i} 章"})
        return agent

    def test_reasoning_never_reaches_the_model(self):
        """不变量：发给模型的消息里永远没有思考过程。

        注意 history 本身**保留**思考过程（用于界面回看/历史回放），
        剥离发生在构造请求时（sanitize_messages），这是有意为之。
        """
        agent = self._agent_with_history()
        agent._compress()
        sent = sanitize_messages(agent.history)
        joined = "\n".join(str(m.get("content", "")) for m in sent)
        self.assertNotIn("REASONING", joined)
        self.assertNotIn("我先想想怎么开头", joined)

    def test_reasoning_not_in_summary(self):
        """摘要块里不能混入思考过程（否则记忆会被推理噪声挤占）。"""
        agent = self._agent_with_history()
        agent._compress()
        self.assertNotIn("REASONING", str(agent.history[0]["content"]))

    def test_origin_requirement_is_kept(self):
        """「每章 5000 字」这类任务原点不能被摘要吞掉。"""
        agent = self._agent_with_history()
        agent._compress()
        joined = "\n".join(str(m.get("content", "")) for m in agent.history)
        self.assertIn("5000 字", joined)
        self.assertIn("原始要求", joined)

    def test_history_is_shrunk(self):
        agent = self._agent_with_history()
        before = len(agent.history)
        agent._compress()
        self.assertLess(len(agent.history), before)
        self.assertLessEqual(len(agent.history), 40)

    def test_summary_block_present(self):
        agent = self._agent_with_history()
        agent._compress()
        self.assertTrue(str(agent.history[0]["content"]).startswith("--- 历史对话摘要 ---"))


if __name__ == "__main__":
    unittest.main()
