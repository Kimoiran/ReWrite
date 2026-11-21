"""API 错误可见性 + 消息序列合法性测试。

真实故障：`update_chapter` 成功之后，续写请求返回 `HTTP Error 400: Bad Request`，
界面和日志里都只有这一句——服务端响应体被 `friendly_api_error` 丢掉了，
既看不出原因，也没留下任何可排查的痕迹。
"""

import json
import unittest

from src.editor.modules.ai_assistant.providers import (
    ApiStatusError,
    _describe_messages,
    _looks_like_context_error,
    friendly_api_error,
    sanitize_messages,
)


class ApiErrorVisibilityTest(unittest.TestCase):
    def test_status_error_carries_server_body(self):
        err = ApiStatusError(400, '{"error":{"message":"invalid tool_call_id"}}')
        self.assertIn("400", str(err))
        self.assertIn("invalid tool_call_id", str(err))

    def test_status_error_without_body(self):
        err = ApiStatusError(400, "")
        self.assertIn("服务端未返回内容", str(err))

    def test_friendly_maps_400_with_body(self):
        msg = friendly_api_error(str(ApiStatusError(
            400, '{"error":{"message":"This model\'s maximum context length is 65536 tokens"}}')))
        self.assertIn("400", msg)
        self.assertIn("maximum context length", msg)
        self.assertIn("上下文超长", msg)

    def test_friendly_maps_401(self):
        msg = friendly_api_error(str(ApiStatusError(401, "invalid api key")))
        self.assertIn("API Key", msg)

    def test_friendly_maps_404(self):
        msg = friendly_api_error(str(ApiStatusError(404, "model not found")))
        self.assertIn("模型", msg)

    def test_network_error_unchanged(self):
        self.assertIn("10054", friendly_api_error("WinError 10054"))


class MessageShapeLogTest(unittest.TestCase):
    """400 时把消息骨架打进日志，否则只看「HTTP 400」永远猜不出原因。"""

    def test_reports_orphan_and_unanswered(self):
        msgs = [
            {"role": "user", "content": "写"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "a", "arguments": "{}"}},
                {"id": "c2", "type": "function", "function": {"name": "b", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c2", "content": "ok"},
            {"role": "tool", "tool_call_id": "zz", "content": "orphan"},
        ]
        desc = _describe_messages(msgs)
        self.assertIn("c1", desc)
        self.assertIn("未回执调用", desc)
        self.assertIn("孤儿回执", desc)

    def test_clean_sequence(self):
        msgs = [
            {"role": "user", "content": "写"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "a", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        ]
        desc = _describe_messages(msgs)
        self.assertIn("无", desc)

    def test_context_error_detection(self):
        self.assertTrue(_looks_like_context_error("max_tokens is too large"))
        self.assertTrue(_looks_like_context_error("maximum context length is 65536"))
        self.assertFalse(_looks_like_context_error("invalid tool_call_id"))
        self.assertFalse(_looks_like_context_error(""))


class MessageSequenceTest(unittest.TestCase):
    """请求里**不出现任何工具调用结构**——这是绕开 thinking 模式
    「必须回传 reasoning_content」要求的关键。"""

    def _assistant(self, call_id, content=""):
        return {"role": "assistant", "content": content,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": "update_chapter",
                                             "arguments": "{}"}}]}

    def test_tool_structure_never_survives(self):
        msgs = [{"role": "user", "content": "写"},
                self._assistant("c1"),
                {"role": "tool", "tool_call_id": "c1", "content": "ok"}]
        cleaned = sanitize_messages(msgs)
        blob = json.dumps(cleaned, ensure_ascii=False)
        self.assertNotIn("tool_calls", blob)
        self.assertNotIn('"role": "tool"', blob)
        self.assertNotIn("reasoning_content", blob)
        self.assertIn("[工具记录]", blob)

    def test_tool_result_merged_into_log(self):
        msgs = [{"role": "user", "content": "写"},
                self._assistant("c1"),
                {"role": "tool", "tool_call_id": "c1", "content": "✅ 已修改章节"}]
        cleaned = sanitize_messages(msgs)
        self.assertIn("✅ 已修改章节", cleaned[1]["content"])

    def test_unanswered_group_still_flattened(self):
        msgs = [{"role": "user", "content": "写"}, self._assistant("c1")]
        cleaned = sanitize_messages(msgs)
        self.assertIn("[工具记录]", cleaned[1]["content"])
        self.assertNotIn("tool_calls", cleaned[1])

    def test_continuation_nudge_appended(self):
        """扁平化后若以 assistant 结尾，要补一句「继续」。"""
        msgs = [{"role": "user", "content": "写"},
                self._assistant("c1"),
                {"role": "tool", "tool_call_id": "c1", "content": "ok"}]
        cleaned = sanitize_messages(msgs)
        self.assertEqual(cleaned[-1]["role"], "user")
        self.assertIn("继续", cleaned[-1]["content"])

    def test_no_nudge_without_tools(self):
        cleaned = sanitize_messages([{"role": "user", "content": "写"},
                                     {"role": "assistant", "content": "好的"}])
        self.assertEqual(cleaned[-1]["role"], "assistant")

    def test_user_message_untouched(self):
        msgs = [{"role": "user", "content": "每章 5000 字"}, self._assistant("c1")]
        self.assertEqual(sanitize_messages(msgs)[0]["content"], "每章 5000 字")

    def test_multiple_rounds_become_log_lines(self):
        msgs = [
            {"role": "user", "content": "写"},
            self._assistant("c1"),
            {"role": "tool", "tool_call_id": "c1", "content": "旧回执"},
            self._assistant("c2"),
            {"role": "tool", "tool_call_id": "c2", "content": "新回执"},
        ]
        cleaned = sanitize_messages(msgs)
        logs = [m for m in cleaned if "[工具记录]" in (m.get("content") or "")]
        self.assertEqual(len(logs), 2)
        self.assertIn("旧回执", logs[0]["content"])
        self.assertIn("新回执", logs[1]["content"])

    def test_serializable(self):
        msgs = [{"role": "user", "content": "写"}, self._assistant("c1")]
        json.dumps(sanitize_messages(msgs), ensure_ascii=False)   # 不应抛异常


if __name__ == "__main__":
    unittest.main()
