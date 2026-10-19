"""续写轮消息构造测试 —— 回归「要求 5000 字，连续写作时缩到 1000 字」。

根因：工具执行后的续写请求曾经只发 ``[assistant 工具调用, tool 结果]``，
第二轮起 AI 看不到用户那句「每章 5000 字」，也看不到前文，于是越写越短。
"""

import unittest

from src.editor.modules.ai_assistant.orchestrator import AIOrchestrator
from src.editor.modules.ai_assistant.providers import build_continuation_messages

USER_REQUEST = "帮我写第 1 到第 5 章，每章 5000 字，别偷懒"
TOOL_CALLS = [{
    "id": "call_abc",
    "type": "function",
    "function": {"name": "update_chapter",
                 "arguments": '{"chapter":"第1章","content":"..."}'},
}]


def _recent():
    return [
        {"role": "user", "content": USER_REQUEST},
        {"role": "assistant", "content": "好的，我先写第一章。"},
    ]


class ContinuationMessagesTest(unittest.TestCase):
    def test_user_request_is_carried_over(self):
        """核心回归：续写轮必须能看到原始的字数要求。"""
        msgs = build_continuation_messages(_recent(), "开始", TOOL_CALLS)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertIn("5000 字", msgs[0]["content"])

    def test_history_is_preserved_in_order(self):
        recent = _recent()
        msgs = build_continuation_messages(recent, "开始", TOOL_CALLS)
        self.assertEqual(msgs[:len(recent)], recent)

    def test_appends_assistant_tool_call_then_pending_tool(self):
        msgs = build_continuation_messages(_recent(), "开始", TOOL_CALLS)
        self.assertEqual(len(msgs), len(_recent()) + 2)
        assistant = msgs[-2]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(assistant["tool_calls"][0]["id"], "call_abc")
        self.assertEqual(assistant["tool_calls"][0]["function"]["name"],
                         "update_chapter")
        pending = msgs[-1]
        self.assertEqual(pending["role"], "tool")
        self.assertEqual(pending["tool_call_id"], "pending")

    def test_does_not_mutate_input(self):
        recent = _recent()
        build_continuation_messages(recent, "开始", TOOL_CALLS)
        self.assertEqual(len(recent), 2)

    def test_multiple_tool_calls_kept_in_order(self):
        two = TOOL_CALLS + [{
            "id": "call_def", "type": "function",
            "function": {"name": "create_character", "arguments": "{}"},
        }]
        msgs = build_continuation_messages(_recent(), "开始", two)
        ids = [tc["id"] for tc in msgs[-2]["tool_calls"]]
        self.assertEqual(ids, ["call_abc", "call_def"])

    def test_empty_history_still_works(self):
        msgs = build_continuation_messages([], "开始", TOOL_CALLS)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "assistant")


class PendingPlaceholderTest(unittest.TestCase):
    """占位 tool 消息必须在注入真实结果前被移除，否则 AI 会看到空的工具结果。"""

    def test_pending_placeholder_is_removed(self):
        msgs = build_continuation_messages(_recent(), "开始", TOOL_CALLS)
        cleaned = AIOrchestrator.prepare_after_messages(None, None, msgs)
        self.assertEqual(cleaned[-1]["role"], "assistant")
        self.assertNotIn("tool", [m["role"] for m in cleaned])

    def test_real_tool_results_survive(self):
        msgs = build_continuation_messages(_recent(), "开始", TOOL_CALLS)
        msgs[-1] = {"role": "tool", "tool_call_id": "call_abc", "content": "✅ 已写入"}
        cleaned = AIOrchestrator.prepare_after_messages(None, None, msgs)
        self.assertEqual(cleaned[-1]["role"], "tool")
        self.assertEqual(cleaned[-1]["content"], "✅ 已写入")


if __name__ == "__main__":
    unittest.main()
