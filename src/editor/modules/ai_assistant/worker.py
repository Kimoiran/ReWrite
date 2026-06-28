"""AI 请求工作线程 — 双模式：普通响应 / 工具提案 + 确认。"""

from PySide6.QtCore import QThread, Signal


class ToolProposalWorker(QThread):
    """后台线程：第一轮 — 向 AI 获取工具调用提案（不执行工具）。"""

    proposals_ready = Signal(list, list, list, str)  # tool_calls, before, after, system
    text_response = Signal(str)  # 没有工具调用，直接返回文本
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
                # 纯文本回复
                self.text_response.emit(result)
            else:
                tool_calls, before, after, system = result
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
