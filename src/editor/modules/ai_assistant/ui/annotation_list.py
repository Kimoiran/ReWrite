"""批注列表面板 — 跨模块查看和管理 AI 批注。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QMenu,
)

from ..annotation_manager import AnnotationManager


class AnnotationListPanel(QDockWidget):
    """批注列表面板，支持正文/人物/大纲/时间线等多模块批注。"""

    annotation_accepted = Signal(str)
    annotation_ignored = Signal(str)
    annotation_clicked = Signal(str)  # annotation_id

    def __init__(self, annotation_manager: AnnotationManager, parent=None):
        super().__init__("批注", parent)
        self.annotation_manager = annotation_manager
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(260)
        self._setup_ui()

    def _setup_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self.count_label = QLabel("待处理: 0")
        self.count_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""QListWidget::item { padding: 8px; }""")
        self.list_widget.itemDoubleClicked.connect(self._on_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget, stretch=1)

        self.setWidget(widget)

    def refresh(self):
        self.list_widget.clear()
        pending = 0
        for ann in self.annotation_manager.get_sorted():
            icon = ann.type_icon
            type_tag = ann.type_label
            title = ann.target_title or type_tag
            display = f"{icon} {title}: {ann.suggestion[:50]}"
            if len(ann.suggestion) > 50:
                display += "…"
            status_icon = {"pending": "🟡", "accepted": "🟢", "ignored": "⚪"}.get(ann.status, "🟡")
            item = QListWidgetItem(f"{status_icon} {display}")
            item.setData(Qt.ItemDataRole.UserRole, ann.id)
            item.setToolTip(f"[{type_tag}] {title}\n{ann.suggestion}")
            self.list_widget.addItem(item)
            if ann.status == "pending":
                pending += 1
        self.count_label.setText(f"待处理: {pending}")

    def _on_item_clicked(self, item):
        ann_id = item.data(Qt.ItemDataRole.UserRole)
        self.annotation_clicked.emit(ann_id)

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        ann_id = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        accept_act = menu.addAction("采纳")
        ignore_act = menu.addAction("忽略")
        menu.addSeparator()
        delete_act = menu.addAction("删除")

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == accept_act:
            self.annotation_manager.update_status(ann_id, "accepted")
            self.annotation_accepted.emit(ann_id)
            self.refresh()
        elif action == ignore_act:
            self.annotation_manager.update_status(ann_id, "ignored")
            self.annotation_ignored.emit(ann_id)
            self.refresh()
        elif action == delete_act:
            self.annotation_manager.delete_annotation(ann_id)
            self.refresh()
