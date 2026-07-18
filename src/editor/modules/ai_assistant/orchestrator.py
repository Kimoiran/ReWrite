"""AI 流程控制器（零 Qt 依赖）。管理工具解析、执行、循环。"""

import json
import logging
import re as _re
from pathlib import Path

logger = logging.getLogger("rewrite.ai")


class AIOrchestrator:
    """AI 对话流程控制。不 import 任何 PySide6。

    调用方式：
    - Qt 层创建 QThread，在线程中调用 run_proposal / run_tool_loop
    - 返回结果通过回调通知 Qt 层（Qt 层负责主线程安全）
    """

    def __init__(self, agent, get_context_fn, execute_skill_fn, get_skill_fn,
                 ensure_work_args_fn, describe_tool_fn, make_chat_request_fn,
                 get_tools_fn, save_history_fn, get_reasoning_fn=None):
        self.agent = agent
        self._get_context = get_context_fn
        self._execute = execute_skill_fn
        self._get_skill = get_skill_fn
        self._ensure_work_args = ensure_work_args_fn
        self._describe_tool = describe_tool_fn
        self._make_chat = make_chat_request_fn
        self._get_tools = get_tools_fn
        self._save_history = save_history_fn

    def set_work_name(self, name: str):
        import os
        os.environ["REWRITE_CURRENT_WORK"] = name

    def run_proposal(self, message: str, context: str):
        """发起第一轮请求（在后台线程中调用）。返回 (result_type, data)。"""
        from .providers import get_proposals_only
        try:
            result = get_proposals_only(self.agent, message, context)
        except Exception as e:
            return ("error", str(e))

        if isinstance(result, str):
            return ("text", result)
        else:
            tool_calls, before, after, system, reasoning = result
            return ("proposal", (tool_calls, before, after, system, reasoning))

    def resolve_proposals(self, raw_tool_calls):
        """解析工具调用列表，返回 [(name, args, description), ...]。"""
        descs = []
        for tc in raw_tool_calls:
            name = tc["function"]["name"]
            try:
                a = json.loads(tc.get("function", {}).get("arguments", "{}"))
            except Exception:
                a = {}
            self._ensure_work_args(name, a)
            skill = self._get_skill(name)
            desc = skill.summarize({"success": True}, a) if skill and hasattr(skill, "summarize") else name
            descs.append((name, a, desc))
        return descs

    def execute_single(self, name: str, args: dict):
        """执行单个工具调用。返回 (result_dict, description)。"""
        result = self._execute(name, args)
        # 章节 diff: result 如果是特殊标记，调用方需要额外处理
        desc = self._describe_tool(name, args, result)
        return result, desc

    def run_tool_loop(self, messages: list, system: str):
        """工具结果发回 AI，继续循环（在后台线程中调用）。返回 (result_type, data)。"""
        try:
            data = self._make_chat(self.agent, messages, system, self._get_tools())
        except Exception as e:
            return ("error", str(e))

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        tcs = msg.get("tool_calls", [])

        if not tcs:
            self.agent.history.append({"role": "assistant", "content": content})
            self._save_history(self.agent.work_name, self.agent.history)
            return ("text", content)

        # 有新的工具调用
        msgs_updated = list(messages)
        msgs_updated.append({"role": "assistant", "content": content,
            "tool_calls": [{"id": tc["id"], "type": "function",
                            "function": {"name": tc["function"]["name"],
                                        "arguments": tc["function"]["arguments"]}}
                           for tc in tcs]})
        return ("proposal", (tcs, msgs_updated, system))

    def prepare_after_messages(self, tool_calls, after):
        """准备工具执行后的消息列表。返回清理后的 messages list。"""
        msgs = list(after)
        if msgs and msgs[-1].get("role") == "tool" and msgs[-1].get("tool_call_id") == "pending":
            msgs.pop()
        return msgs

    def append_tool_results(self, messages, tool_calls, results):
        """将工具执行结果追加到消息列表。返回更新后的 messages。"""
        for tc, (name, result) in zip(tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                            "content": self._describe_tool(name, result[1], result[0])})
        return messages

    @staticmethod
    def render_message(text: str) -> str:
        """渲染消息 HTML：提取推理标记 → markdown 渲染正文 → 拼接推理块。"""
        from .markdown_render import markdown_to_html
        reasoning_html = ""
        m = _re.search(r'<!--REASONING-->\n(.*?)\n<!--/REASONING-->\n\n', text, _re.DOTALL)
        if m:
            reasoning_text = m.group(1)
            text = text[:m.start()] + text[m.end():]
            reasoning_html = (f"<div style='font-size:12px;color:#999;line-height:1.3;"
                            f"padding:4px 8px;background:#fafafa;border-left:2px solid #ddd;"
                            f"margin-bottom:8px;'><b>思考过程</b><br>"
                            f"{reasoning_text.replace(chr(10), '<br>')}</div>")
        html = markdown_to_html(text)
        return reasoning_html + html if reasoning_html else html
