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
    """服务端会拒绝「tool_calls 没有对应回执」的请求，这里必须提前兜住。"""

    def _assistant(self, call_id, content=""):
        return {"role": "assistant", "content": content,
                "tool_calls": [{"id": call_id, "type": "function",
                                "function": {"name": "update_chapter",
                                             "arguments": "{}"}}]}

    def test_complete_last_group_is_preserved(self):
        msgs = [{"role": "user", "content": "写"},
                self._assistant("c1"),
                {"role": "tool", "tool_call_id": "c1", "content": "ok"}]
        cleaned = sanitize_messages(msgs)
        self.assertIn("tool_calls", cleaned[1])

    def test_unanswered_last_group_is_collapsed(self):
        """当前轮回执缺失（写操作被跳过等）→ 折叠，避免整个请求 400。"""
        msgs = [{"role": "user", "content": "写"}, self._assistant("c1")]
        cleaned = sanitize_messages(msgs)
        self.assertNotIn("tool_calls", cleaned[1])
        self.assertIn("[工具记录]", cleaned[1]["content"])

    def test_empty_call_id_is_collapsed(self):
        """id 为空串的 tool_call 同样会让服务端报序列不合法。"""
        msgs = [{"role": "user", "content": "写"},
                self._assistant(""),
                {"role": "tool", "tool_call_id": "", "content": "ok"}]
        cleaned = sanitize_messages(msgs)
        self.assertNotIn("tool_calls", cleaned[1])

    def test_partially_answered_group_is_collapsed(self):
        assistant = {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "read_chapter", "arguments": "{}"}},
            {"id": "c2", "type": "function", "function": {"name": "get_outline", "arguments": "{}"}},
        ]}
        msgs = [{"role": "user", "content": "写"}, assistant,
                {"role": "tool", "tool_call_id": "c1", "content": "ok"}]
        cleaned = sanitize_messages(msgs)
        self.assertNotIn("tool_calls", cleaned[1])
        # 孤立回执也要一起去掉
        self.assertNotIn("tool", [m["role"] for m in cleaned])

    def test_no_orphan_tool_messages_after_collapse(self):
        msgs = [
            {"role": "user", "content": "写"},
            self._assistant("c1"),
            {"role": "tool", "tool_call_id": "c1", "content": "旧回执"},
            self._assistant("c2"),
            {"role": "tool", "tool_call_id": "c2", "content": "新回执"},
        ]
        cleaned = sanitize_messages(msgs)
        tool_ids = {m.get("tool_call_id") for m in cleaned if m["role"] == "tool"}
        call_ids = {tc["id"] for m in cleaned if m.get("tool_calls") for tc in m["tool_calls"]}
        self.assertEqual(tool_ids, call_ids)   # 严格配对，没有孤儿

    def test_serializable(self):
        msgs = [{"role": "user", "content": "写"}, self._assistant("c1")]
        json.dumps(sanitize_messages(msgs), ensure_ascii=False)   # 不应抛异常


if __name__ == "__main__":
    unittest.main()
