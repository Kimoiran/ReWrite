"""模块基类——所有可选模块继承此接口。"""

from pathlib import Path
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDockWidget


class BaseModule(QObject):
    """模块基类，定义模块的标准接口。"""

    module_id = ""  # 子类重写，如 "characters"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(parent)
        self.work_path = work_path

    def create_dock_widget(self) -> QDockWidget:
        """创建该模块的 Dock 面板。返回 None 表示无面板。"""
        raise NotImplementedError

    def on_work_loaded(self):
        """作品加载完成时回调。"""
        pass

    def on_chapter_changed(self, chapter_path: str):
        """当前章节切换时回调。"""
        pass

    def search(self, query: str) -> list:
        """搜索该模块数据，返回 [(标题, 位置描述, 跳转数据), ...]。"""
        return []

    def save(self):
        """保存模块数据到磁盘。"""
        raise NotImplementedError

    def load(self):
        """从磁盘加载模块数据。"""
        pass
