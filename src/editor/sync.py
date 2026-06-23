"""多窗口文档同步 — 同一章节多开时实时同步。"""

from typing import Callable


class DocumentSync:
    """文档同步管理器。

    同一章节可以在多个窗口中同时打开编辑，
    修改自动同步到所有其他窗口。
    """

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = {}

    def register(self, chapter_path: str, callback: Callable[[str], None]):
        """注册一个章节的监听器。"""
        if chapter_path not in self._listeners:
            self._listeners[chapter_path] = []
        self._listeners[chapter_path].append(callback)

    def unregister(self, chapter_path: str, callback: Callable):
        """注销监听器。"""
        if chapter_path in self._listeners:
            self._listeners[chapter_path] = [
                cb for cb in self._listeners[chapter_path] if cb is not callback
            ]
            if not self._listeners[chapter_path]:
                del self._listeners[chapter_path]

    def broadcast(self, chapter_path: str, html: str, sender: Callable = None):
        """广播内容变化给该章节的所有其他监听器。"""
        if chapter_path not in self._listeners:
            return
        for callback in self._listeners[chapter_path]:
            if callback is not sender:
                try:
                    callback(html)
                except Exception as e:
                    print(f"同步广播异常: {e}")


# 全局单例
document_sync = DocumentSync()
