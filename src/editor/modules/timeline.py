"""时间线模块——按时间轴组织事件。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List


def _date_sort_key(date_str: str) -> tuple:
    """智能日期排序键，支持数字和常见日期格式。"""
    if not date_str:
        return (1, "", 0)
    # 纯数字（如 "1000"）→ 按数字比
    if date_str.isdigit():
        return (0, "", int(date_str))
    # 中文数字前缀如 "星历2371-03-15" → 提取数字部分
    import re
    nums = re.findall(r'\d+', date_str)
    if nums:
        return (0, "", int(nums[0]))
    # 其他字符串
    return (1, date_str, 0)

from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QDialog, QFormLayout,
    QLineEdit, QTextEdit, QMessageBox, QDialogButtonBox,
    QListWidget, QListWidgetItem, QComboBox, QMenu,
)

from .base_module import BaseModule


@dataclass
class TimelineEvent:
    id: str = ""
    date: str = ""
    title: str = ""
    description: str = ""
    characters: List[str] = field(default_factory=list)
    chapter_ref: str = ""


class TimelineModule(BaseModule):
    """时间线数据管理。"""

    module_id = "timeline"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "timeline.json"
        self.events: List[TimelineEvent] = []

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.events = [TimelineEvent(**e) for e in data.get("events", [])]
                self.events.sort(key=lambda e: _date_sort_key(e.date))
            except (json.JSONDecodeError, TypeError) as e:
                print(f"加载时间线失败: {e}")
                self.events = []
        if not self.events:
            self.events = []

    def save(self):
        try:
            data = {"events": [asdict(e) for e in self.events]}
            self.data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return True
        except OSError as e:
            print(f"保存时间线失败: {e}")
            return False

    def add_event(self, date: str, title: str, description: str = "") -> TimelineEvent:
        event = TimelineEvent(
            id=uuid.uuid4().hex[:12],
            date=date,
            title=title,
            description=description,
        )
        self.events.append(event)
        self.events.sort(key=lambda e: _date_sort_key(e.date))
        return event

    def delete_event(self, event_id: str) -> bool:
        self.events = [e for e in self.events if e.id != event_id]
        return True

    def update_event(self, event_id: str, **fields) -> bool:
        for e in self.events:
            if e.id == event_id:
                for k, v in fields.items():
                    if hasattr(e, k):
                        setattr(e, k, v)
                self.events.sort(key=lambda e: _date_sort_key(e.date))
                return True
        return False

    def apply_edit(self, target_name: str, field: str, value: str) -> tuple[bool, str]:
        """AI 编辑时间线事件。"""
        VALID_FIELDS = {"date", "title", "description"}
        if field not in VALID_FIELDS:
            return False, f"不支持修改字段「{field}」, 支持: {', '.join(sorted(VALID_FIELDS))}"
        for e in self.events:
            if e.title == target_name:
                setattr(e, field, value)
                self.events.sort(key=lambda e: _date_sort_key(e.date))
                self.save()
                return True, f"已修改时间线事件 {target_name} 的 {field}"
        return False, f"未找到时间线事件「{target_name}」"

    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        for e in self.events:
            if e.id == event_id:
                return e
        return None

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        for e in self.events:
            if q in e.title.lower() or q in e.description.lower() or q in e.date.lower():
                results.append((e.title, f"时间线 ({e.date})", e.id))
        return results

    def create_dock_widget(self) -> QDockWidget:
        return TimelineDock(self, None)


class EventEditDialog(QDialog):
    """事件编辑对话框。"""

    def __init__(self, timeline_event: Optional[TimelineEvent] = None, parent=None):
        super().__init__(parent)
        self._event = timeline_event
        self.setWindowTitle("编辑事件" if self._event else "添加事件")
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("例如: 星历2371-03-15 或 2024年春")
        if self._event:
            self.date_edit.setText(self._event.date)
        layout.addRow("日期:", self.date_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("事件标题")
        if self._event:
            self.title_edit.setText(self._event.title)
        layout.addRow("标题:", self.title_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(120)
        self.desc_edit.setPlaceholderText("事件描述...")
        if self._event:
            self.desc_edit.setPlainText(self._event.description)
        layout.addRow("描述:", self.desc_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "date": self.date_edit.text().strip(),
            "title": self.title_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
        }


class TimelineDock(QDockWidget):
    """时间线 UI 面板。"""

    def __init__(self, module: TimelineModule, parent=None):
        super().__init__("📅 时间线", parent)
        self.module = module
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
        self.setMinimumWidth(260)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 按钮行
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加事件")
        add_btn.setStyleSheet("""
            QPushButton { background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 4px 10px; font-size: 12px; }
            QPushButton:hover { background-color: #3a7bc8; }
        """)
        add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(add_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 事件列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""QListWidget::item { padding: 8px; }""")
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._on_edit_item)
        layout.addWidget(self.list_widget, stretch=1)

        self.setWidget(widget)

    def _refresh(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for event in self.module.events:
            display = f"📌 {event.date}  {event.title}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, event.id)
            item.setToolTip(event.description[:100] if event.description else "")
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    def _on_add(self):
        dialog = EventEditDialog()
        if dialog.exec() == EventEditDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"] and data["date"]:
                self.module.add_event(data["date"], data["title"], data["description"])
                self.module.save()
                self._refresh()

    def _on_edit_item(self, item):
        event_id = item.data(Qt.ItemDataRole.UserRole)
        event = self.module.get_event(event_id)
        if event:
            dialog = EventEditDialog(event)
            if dialog.exec() == EventEditDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.module.update_event(event_id, **data)
                self.module.save()
                self._refresh()

    def _on_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        event_id = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)
        edit_act = menu.addAction("编辑")
        delete_act = menu.addAction("删除")

        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == edit_act:
            self._on_edit_item(item)
        elif action == delete_act:
            reply = QMessageBox.question(
                self, "确认删除", "确定删除此事件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.module.delete_event(event_id)
                self.module.save()
                self._refresh()
