"""AI 请求工作线程 — 防止 UI 卡死。"""

from PySide6.QtCore import QThread, Signal


class AIWorker(QThread):
    """在后台线程中发送 AI 请求，不阻塞 UI。"""

    finished = Signal(str)  # response text
    error = Signal(str)     # error message

    def __init__(self, agent, message: str, context: str = "", enable_tools: bool = False):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context = context
        self.enable_tools = enable_tools

    def run(self):
        try:
            response = self.agent.send_message(
                self.message,
                current_context=self.context,
                enable_tools=self.enable_tools,
            )
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))
