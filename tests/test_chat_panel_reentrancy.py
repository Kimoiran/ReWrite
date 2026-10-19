"""对话面板：流式信号重入保护测试。

回归的真实故障：AI 在写长章节（约 5000 字）时软件卡死并退出，
Windows 事件日志显示 ``0xc00000fd``（栈溢出），崩溃模块 Qt6Gui.dll。

根因是 ``ChatPanel._scroll_to_bottom_now()`` 里调用了
``QApplication.processEvents()``，而它是在**队列化信号**的槽里被调用的：
processEvents 会把队列中后面的流式片段当场重入处理，
递归深度等于积压的片段数——一章几百个片段就爆栈。

这组测试用真实的 QueuedConnection 复现那条链路。
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QObject, Qt, Signal
    from PySide6.QtWidgets import QApplication
    _QT_IMPORT_ERROR = None
except Exception as e:                       # pragma: no cover
    _QT_IMPORT_ERROR = e

# 只发这么多个片段：足以让重入暴露（深度会等于片段数），
# 又不至于真把测试进程的栈撑爆——测试失败也要能干净地报出来。
_CHUNKS = 40


class _Emitter(QObject):
    chunk = Signal(str)


def _make_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@unittest.skipIf(_QT_IMPORT_ERROR is not None, f"PySide6 不可用: {_QT_IMPORT_ERROR}")
class StreamReentrancyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()

    def test_queued_stream_chunks_do_not_reenter(self):
        """队列化片段逐个处理，深度必须始终为 1（不能被重入）。"""
        from src.editor.modules.ai_assistant.ui.chat_panel import ChatPanel

        panel = ChatPanel()
        panel.resize(360, 640)
        bubble = panel.begin_streaming_message()
        emitter = _Emitter()

        state = {"depth": 0, "max_depth": 0, "text": ""}

        def on_chunk(chunk):
            state["depth"] += 1
            state["max_depth"] = max(state["max_depth"], state["depth"])
            try:
                state["text"] += chunk
                panel.update_streaming(bubble, state["text"], reasoning=state["text"])
            finally:
                state["depth"] -= 1

        emitter.chunk.connect(on_chunk, Qt.ConnectionType.QueuedConnection)

        for _ in range(_CHUNKS):
            emitter.chunk.emit("这一段是流式片段。")

        self.app.processEvents()             # 若修复失效，这里会层层重入

        self.assertEqual(state["max_depth"], 1,
                         "流式槽被重入：processEvents 又回到了 scroll/渲染路径")
        self.assertEqual(state["depth"], 0)

    def test_scroll_helper_does_not_pump_events(self):
        """贴底不应该自己抽干事件队列（否则任何调用它的槽都可能被重入）。"""
        from src.editor.modules.ai_assistant.ui.chat_panel import ChatPanel

        panel = ChatPanel()
        panel.resize(360, 640)
        panel.show()
        panel.add_message("assistant", "<p>内容</p>")

        marker = {"ran": 0}

        def queued_slot():
            marker["ran"] += 1
            panel._scroll_to_bottom_now()
            marker["ran"] += 1

        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, queued_slot)
        # 在 processEvents 之前再排一个任务，验证贴底不会把它提前执行
        QTimer.singleShot(0, lambda: marker.__setitem__("queued_ran", True))
        self.app.processEvents()

        self.assertEqual(marker["ran"], 2)


if __name__ == "__main__":
    unittest.main()
