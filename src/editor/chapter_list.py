"""章节列表面板——QDockWidget 展示和管理章节。"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QInputDialog, QMessageBox, QMenu,
    QAbstractItemView,
)

from .modules.chapters import ChapterModule, ChapterInfo


class ChapterListPanel(QDockWidget):
    """章节列表面板，展示章节列表并支持管理操作。"""

    chapter_selected = Signal(str)  # 章节路径
    chapter_created = Signal(str)  # 章节路径
    chapter_deleted = Signal(str)  # 章节路径
    chapter_renamed = Signal(str, str)  # 旧路径, 新路径

    def __init__(self, chapter_module: ChapterModule, parent=None):
        super().__init__("📖 章节", parent)
        self.chapter_module = chapter_module
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(200)
        self.setStyleSheet("QDockWidget::title { padding: 6px; }")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 新建章节按钮
        add_btn = QPushButton("+ 新建章节")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
        """)
        add_btn.clicked.connect(self._on_new_chapter)
        layout.addWidget(add_btn)

        # 章节列表
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
                font-size: 13px;
                color: #333333;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #f0f0f0;
                color: #333333;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #333333;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        layout.addWidget(self.list_widget, stretch=1)

        # 底部信息
        self.info_label = QPushButton()
        self.info_label.setEnabled(False)
        self.info_label.setStyleSheet(
            "text-align: left; color: #888888; font-size: 11px; "
            "border: none; padding: 2px;"
        )
        layout.addWidget(self.info_label)

        self.setWidget(widget)

    def _refresh(self):
        """刷新章节列表。"""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        chapters = self.chapter_module.list_chapters()
        for chap in chapters:
            item = QListWidgetItem()
            fwc = f"{chap.word_count:,}"
            display = f"{chap.title}  ({fwc}字)"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, str(chap.path))
            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)

        count = len(chapters)
        total_words = sum(c.word_count for c in chapters)
        from ..utils.stats import format_word_count
        self.info_label.setText(
            f"  共 {count} 章，{format_word_count(total_words)} 字"
        )

    def _on_new_chapter(self):
        """新建章节。"""
        title, ok = QInputDialog.getText(
            self, "新建章节", "章节名称:",
            text=f"第{len(self.chapter_module.list_chapters()) + 1}章"
        )
        if ok and title.strip():
            info = self.chapter_module.create_chapter(title.strip())
            if info:
                self._refresh()
                self.chapter_created.emit(str(info.path))
                # 选中新建的章节
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == str(info.path):
                        self.list_widget.setCurrentRow(i)
                        break

    def _on_selection_changed(self, row: int):
        """选中章节时发射信号。"""
        if row < 0:
            return
        item = self.list_widget.item(row)
        if item:
            path = item.data(Qt.ItemDataRole.UserRole)
            self.chapter_selected.emit(path)

    def _on_context_menu(self, pos):
        """右键菜单。"""
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        path_str = item.data(Qt.ItemDataRole.UserRole)
        path = Path(path_str)

        menu = QMenu(self)
        rename_act = menu.addAction("重命名")
        delete_act = menu.addAction("删除章节")
        menu.addSeparator()
        float_act = menu.addAction("在新窗口中打开")

        action = menu.exec(self.list_widget.mapToGlobal(pos))

        if action == rename_act:
            self._on_rename(path)
        elif action == delete_act:
            self._on_delete(path)
        elif action == float_act:
            self._on_open_floating(path)

    def _on_rename(self, path: Path):
        """重命名章节。"""
        # 提取当前标题
        chapters = self.chapter_module.list_chapters()
        current_title = ""
        for c in chapters:
            if c.path == path:
                current_title = c.title
                break

        title, ok = QInputDialog.getText(
            self, "重命名章节", "新名称:",
            text=current_title
        )
        if ok and title.strip():
            new_path = self.chapter_module.rename_chapter(path, title.strip())
            if new_path:
                self._refresh()
                self.chapter_renamed.emit(str(path), str(new_path))

    def _on_delete(self, path: Path):
        """删除章节。"""
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除该章节吗？\n删除后不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.chapter_module.delete_chapter(path):
                self._refresh()
                self.chapter_deleted.emit(str(path))

    def _on_open_floating(self, path: Path):
        """在新浮动窗口中打开章节（支持多窗口同步编辑）。"""
        from .editor_widget import EditorWidget
        from .sync import document_sync
        from PySide6.QtWidgets import QDockWidget, QVBoxLayout

        html = self.chapter_module.read_chapter(path)

        dock = QDockWidget(f"章节: {path.stem.split('_', 1)[-1]}")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        dock.setMinimumSize(400, 300)

        editor = EditorWidget()
        editor.load_html(html)
        editor.set_current_chapter(str(path))

        dock.setWidget(editor)
        dock.setFloating(True)
        dock.show()

        # 注册同步
        chapter_path = str(path)
        def on_content_changed(cp, h):
            if cp == chapter_path:
                document_sync.broadcast(chapter_path, h, sender=on_content_changed)

        editor.content_synced.connect(on_content_changed)
        document_sync.register(chapter_path, editor.apply_sync)

        # 清理
        def on_dock_closed(evt):
            document_sync.unregister(chapter_path, editor.apply_sync)
            super(editor.__class__, editor).closeEvent(evt) if hasattr(editor, 'closeEvent') else None

        editor.closeEvent = on_dock_closed

    def select_chapter(self, path: str):
        """按路径选中章节。"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.list_widget.setCurrentRow(i)
                break

    def update_item_display(self, path_str: str):
        """原地更新指定章节的显示文本（不清空重建，不弹窗口）。"""
        from ..utils.stats import format_word_count
        chapters = self.chapter_module.list_chapters()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == path_str:
                for c in chapters:
                    if str(c.path) == path_str:
                        item.setText(f"{c.title}  ({format_word_count(c.word_count)}字)")
                        break
                break
        # 更新底部统计
        total = sum(c.word_count for c in chapters)
        from ..utils.stats import format_word_count as _fw
        self.info_label.setText(
            f"  共 {len(chapters)} 章，{_fw(total)} 字"
        )
