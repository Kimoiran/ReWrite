"""AI 请求工作线程 — 支持流式推理和工具调用。"""

from PySide6.QtCore import QThread, Signal


class ToolProposalWorker(QThread):
    """后台线程（兼容保留）：第一轮 — 向 AI 获取工具调用提案（非流式）。"""

    proposals_ready = Signal(list, list, list, str)
    text_response = Signal(str)
    reasoning_ready = Signal(str)
    api_error = Signal(str)

    def __init__(self, agent, message: str, context: str = ""):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context

    def run(self):
        try:
            from .providers import get_proposals_only
            result = get_proposals_only(self.agent, self.message, self.context)
            if isinstance(result, str):
                self.text_response.emit(result)
            else:
                tool_calls, before, after, system, reasoning = result
                if reasoning:
                    self.reasoning_ready.emit(reasoning)
                self.proposals_ready.emit(tool_calls, before, after, system)
        except Exception as e:
            self.api_error.emit(str(e))


class StreamingProposalWorker(QThread):
    """后台线程：流式请求 + 工具调用检测。

    文本内容通过 text_chunk 逐块推送到 UI 实现打字机效果，
    同时收集完整的 tool_calls。返回时走 proposals_ready 或 text_response。
    """

    text_chunk = Signal(str)               # 正文片段 → UI 实时显示
    reasoning_chunk = Signal(str)          # 推理片段 → loading 气泡
    proposals_ready = Signal(list, list, list, str)  # 有工具调用
    text_response = Signal(str)            # 纯文本回复（含 reasoning 标记）
    api_error = Signal(str)

    def __init__(self, agent, message: str, context: str = ""):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context

    def run(self):
        try:
            from .providers import _make_streaming_request
            from .prompt_templates import DEFAULT_SYSTEM_PROMPT
            from .skills.registry import get_openai_tools

            system = self.agent.config.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
            if self.context:
                system += f"\n\n## 当前作品上下文\n{self.context}"

            self.agent.history.append({"role": "user", "content": self.message})
            recent = self.agent.history[-40:]

            full_text, tool_calls, reasoning = _make_streaming_request(
                self.agent, recent, system,
                on_reasoning=lambda t: self.reasoning_chunk.emit(t),
                on_content=lambda t: self.text_chunk.emit(t),
                tools=get_openai_tools(),
            )

            if tool_calls:
                # 构造 before/after 消息（与 get_proposals_only 格式一致）
                full = [{"role": "system", "content": system}]
                full.extend(recent)
                before = list(full)
                after = [{"role": "assistant", "content": full_text,
                    "tool_calls": [{"id": tc["id"], "type": "function",
                                    "function": {"name": tc["function"]["name"],
                                                 "arguments": tc["function"]["arguments"]}}
                                   for tc in tool_calls]}]
                after.append({"role": "tool", "tool_call_id": "pending", "content": ""})

                if reasoning:
                    self.reasoning_chunk.emit(reasoning)
                self.proposals_ready.emit(tool_calls, before, after, system)
            else:
                # 纯文本回复
                self.agent.history.append({"role": "assistant", "content": full_text})
                self.agent._persist()
                if reasoning:
                    full_text = f"<!--REASONING-->\n{reasoning}\n<!--/REASONING-->\n\n{full_text}"
                self.text_response.emit(full_text)

        except Exception as e:
            self.api_error.emit(str(e))


class StreamingLoopWorker(QThread):
    """后台线程：工具执行后的续写循环（流式）。

    将工具执行结果发回 AI，流式接收回复，同时检测是否有新的工具调用。
    """

    finished = Signal(dict)      # 模拟的非流式响应 dict（复用 on_data 解析逻辑）
    text_chunk = Signal(str)     # 正文片段 → UI 实时显示
    error = Signal(str)

    def __init__(self, agent, messages: list, system: str = ""):
        super().__init__()
        self.agent = agent
        self.messages = messages
        self.system = system

    def run(self):
        try:
            from .providers import _make_streaming_request, get_openai_tools

            full_text, tool_calls, _ = _make_streaming_request(
                self.agent, self.messages, self.system,
                on_content=lambda t: self.text_chunk.emit(t),
                tools=get_openai_tools(),
            )

            # 构造一个模拟的非流式响应 dict，让 module 层现有解析逻辑复用
            fake_data = {
                "choices": [{
                    "message": {
                        "content": full_text,
                        "tool_calls": [{
                            "id": tc["id"], "type": "function",
                            "function": {"name": tc["function"]["name"],
                                         "arguments": tc["function"]["arguments"]}
                        } for tc in tool_calls]
                    }
                }]
            }
            self.finished.emit(fake_data)

        except Exception as e:
            self.error.emit(str(e))


class ToolExecuteWorker(QThread):
    """后台线程（兼容保留）：非流式续写。"""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, agent, messages: list, system_prompt: str = ""):
        super().__init__()
        self.agent = agent
        self.messages = messages
        self.system_prompt = system_prompt

    def run(self):
        try:
            from .providers import get_final_response
            response = get_final_response(self.agent, self.messages, self.system_prompt)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class ReasoningWorker(QThread):
    """流式推理线程（无工具调用）— 边接收边显示 AI 的思维过程。"""

    reasoning_chunk = Signal(str)
    content_chunk = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, agent, message: str, context: str = ""):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context

    def run(self):
        try:
            from .prompt_templates import DEFAULT_SYSTEM_PROMPT

            system = self.agent.config.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
            if self.context:
                system += f"\n\n## 当前作品上下文\n{self.context}"

            self.agent.history.append({"role": "user", "content": self.message})
            recent = self.agent.history[-40:]

            from .providers import _make_streaming_request

            full_text, _, reasoning = _make_streaming_request(
                self.agent, recent, system,
                on_reasoning=lambda t: self.reasoning_chunk.emit(t),
                on_content=lambda t: self.content_chunk.emit(t),
            )

            self.agent.history.append({"role": "assistant", "content": full_text})
            self.agent._persist()
            self.finished.emit(full_text)

        except Exception as e:
            self.error.emit(str(e))
