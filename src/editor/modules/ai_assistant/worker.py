"""AI 请求工作线程 — 支持流式推理。"""

from PySide6.QtCore import QThread, Signal


class ToolProposalWorker(QThread):
    """后台线程：第一轮 — 向 AI 获取工具调用提案（不执行工具）。"""

    proposals_ready = Signal(list, list, list, str)
    text_response = Signal(str)
    reasoning_ready = Signal(str)  # 推理内容
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
                # 纯文本回复（可能包含推理内容，由调用方处理）
                self.text_response.emit(result)
            else:
                tool_calls, before, after, system, reasoning = result
                if reasoning:
                    self.reasoning_ready.emit(reasoning)
                self.proposals_ready.emit(tool_calls, before, after, system)
        except Exception as e:
            self.api_error.emit(str(e))


class ToolExecuteWorker(QThread):
    """后台线程：第二轮 — 把工具执行结果发给 AI 生成最终回复。"""

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
    """流式推理线程 — 边接收边显示 AI 的思维过程。"""

    reasoning_chunk = Signal(str)  # 推理内容片段
    content_chunk = Signal(str)    # 回复内容片段
    finished = Signal(str)         # 完整回复
    error = Signal(str)

    def __init__(self, agent, message: str, context: str = ""):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context

    def run(self):
        try:
            from .prompt_templates import DEFAULT_SYSTEM_PROMPT

            # 构建消息
            system = self.agent.config.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
            if self.context:
                system += f"\n\n## 当前作品上下文\n{self.context}"

            self.agent.history.append({"role": "user", "content": self.message})
            recent = self.agent.history[-40:]

            from .providers import _make_streaming_request

            def on_reasoning(text):
                self.reasoning_chunk.emit(text)

            def on_content(text):
                self.content_chunk.emit(text)

            result = _make_streaming_request(
                self.agent, recent, system,
                on_reasoning=on_reasoning,
                on_content=on_content,
            )

            self.agent.history.append({"role": "assistant", "content": result})
            self.agent._persist()
            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))
