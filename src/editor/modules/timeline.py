"""时间线模块——按时间轴组织事件（树形结构，支持父子事件）。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List


def _date_sort_key(date_str: str, era: str = "") -> tuple:
    """智能日期排序键，支持「{era}XXX年」「{era}前XXX年」「{era}元年」等格式。

    era — 作品的纪元名（如「神启」「星历」），空则用纯数字排序。
    """
    if not date_str:
        return (1, "", 0, 0)
    import re
    if era:
        # {era}元年 → year=1, era=1
        if f"{era}元年" in date_str:
            return (0, "", 1, 1)
        # {era}前XXX年 → era=0（纪元前）, year=XXX
        m = re.match(re.escape(era) + r'前?\s*(\d+)', date_str)
        if m:
            year = int(m.group(1))
            is_before = "前" in date_str
            return (0, "", 0 if is_before else 1, year)
    if date_str.isdigit():
        return (0, "", 0, int(date_str))
    nums = re.findall(r'\d+', date_str)
    if nums:
        return (0, "", 0, int(nums[0]))
    return (1, date_str, 0, 0)

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QDialog, QFormLayout,
    QLineEdit, QTextEdit, QMessageBox, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QMenu,
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
    parent_id: str = ""        # 父事件 ID，空字符串 = 根事件
    children: List["TimelineEvent"] = field(default_factory=list)


class TimelineModule(BaseModule):
    """时间线数据管理（树形结构）。"""

    module_id = "timeline"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "timeline.json"
        self.events: List[TimelineEvent] = []
        self._era = ""  # 从 work.json 读取的纪元名

    def _load_era(self):
        """从 work.json 读取纪元名。"""
        meta_path = self.data_path.parent / "work.json"
        if meta_path.exists():
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
                self._era = m.get("date_era", "")
            except Exception:
                self._era = ""

    def _sort_key(self, date_str: str) -> tuple:
        return _date_sort_key(date_str, self._era)

    def load(self):
        self._load_era()
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                flat = [TimelineEvent(**e) for e in data.get("events", [])]
                # 重建树形结构
                id_map = {e.id: e for e in flat}
                self.events = []
                for e in flat:
                    e.children = []
                for e in flat:
                    if e.parent_id and e.parent_id in id_map:
                        id_map[e.parent_id].children.append(e)
                    else:
                        self.events.append(e)
                # 排序：根级按日期，子级也按日期
                self.events.sort(key=lambda e: self._sort_key(e.date))
                for e in flat:
                    e.children.sort(key=lambda c: self._sort_key(c.date))
            except (json.JSONDecodeError, TypeError) as e:
                print(f"加载时间线失败: {e}")
                self.events = []
        if not self.events:
            self.events = []

    def save(self):
        try:
            # 扁平化保存
            flat = []
            def _flatten(nodes):
                for e in nodes:
                    # children 存 ID 列表
                    child_ids = [c.id for c in e.children]
                    e_data = asdict(e)
                    e_data["children"] = child_ids
                    flat.append(e_data)
                    _flatten(e.children)
            _flatten(self.events)
            data = {"events": flat}
            self.data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return True
        except OSError as e:
            print(f"保存时间线失败: {e}")
            return False

    def add_event(self, date: str, title: str, description: str = "",
                  parent_id: str = "") -> TimelineEvent:
        event = TimelineEvent(
            id=uuid.uuid4().hex[:12],
            date=date,
            title=title,
            description=description,
            parent_id=parent_id,
        )
        if parent_id:
            parent = self._find_by_id(parent_id)
            if parent:
                parent.children.append(event)
                parent.children.sort(key=lambda e: self._sort_key(e.date))
                return event
        self.events.append(event)
        self.events.sort(key=lambda e: self._sort_key(e.date))
        return event

    def delete_event(self, event_id: str) -> bool:
        """删除事件（含所有子事件）。"""
        def _delete_from(nodes, eid):
            for i, e in enumerate(nodes):
                if e.id == eid:
                    nodes.pop(i)
                    return True
                if e.children and _delete_from(e.children, eid):
                    return True
            return False
        return _delete_from(self.events, event_id)

    def update_event(self, event_id: str, **fields) -> bool:
        def _find(nodes):
            for e in nodes:
                if e.id == event_id:
                    for k, v in fields.items():
                        if hasattr(e, k) and v is not None:
                            setattr(e, k, v)
                    # 更新后重排序
                    for n in nodes:
                        n.children.sort(key=lambda x: self._sort_key(x.date))
                    nodes.sort(key=lambda x: self._sort_key(x.date))
                    return True
                if e.children and _find(e.children):
                    return True
            return False
        return _find(self.events)

    def _find_by_id(self, event_id: str) -> Optional[TimelineEvent]:
        def _find(nodes):
            for e in nodes:
                if e.id == event_id:
                    return e
                if e.children:
                    f = _find(e.children)
                    if f:
                        return f
            return None
        return _find(self.events)

    def apply_edit(self, target_name: str, field: str, value: str) -> tuple[bool, str]:
        VALID_FIELDS = {"date", "title", "description"}
        if field not in VALID_FIELDS:
            return False, f"不支持字段「{field}」"
        def _find(nodes):
            for e in nodes:
                if e.title == target_name:
                    setattr(e, field, value)
                    return True
                if e.children:
                    f = _find(e.children)
                    if f:
                        return True
            return False
        if _find(self.events):
            self.save()
            return True, f"已修改时间线事件 {target_name} 的 {field}"
        return False, f"未找到时间线事件「{target_name}」"

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        def _search(nodes):
            for e in nodes:
                if q in e.title.lower() or q in e.description.lower() or q in e.date.lower():
                    results.append((e.title, f"时间线 ({e.date})", e.id))
                _search(e.children)
        _search(self.events)
        return results

    def create_dock_widget(self) -> QDockWidget:
        return TimelineDock(self, None)


class EventEditDialog(QDialog):
    """事件编辑对话框，支持指定父事件。"""

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
    """时间线 UI 面板（树形显示）。"""

    def __init__(self, module: TimelineModule, parent=None):
        super().__init__("📅 时间线", parent)
        self.module = module
        self._setup_ui()
        self._build_tree()

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

        # 树形事件列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["时间线事件"])
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_edit_item)
        self.tree.setStyleSheet("QTreeWidget::item { padding: 4px; }")
        layout.addWidget(self.tree, stretch=1)

        self.setWidget(widget)

    def _build_tree(self):
        """重建树形显示。"""
        self.tree.blockSignals(True)
        self.tree.clear()
        def _add(nodes, parent):
            for e in nodes:
                display = f"📌 {e.date}  {e.title}"
                item = QTreeWidgetItem([display])
                item.setData(0, Qt.ItemDataRole.UserRole, e.id)
                item.setToolTip(0, e.description[:200] if e.description else "")
                if parent:
                    parent.addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                if e.children:
                    _add(e.children, item)
        _add(self.module.events, None)
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def _refresh(self):
        """外部调用重建树。"""
        self._build_tree()

    def _on_add(self):
        dialog = EventEditDialog()
        if dialog.exec() == EventEditDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"] and data["date"]:
                self.module.add_event(data["date"], data["title"], data["description"])
                self.module.save()
                self._build_tree()

    def _on_add_child(self, parent_id: str):
        dialog = EventEditDialog()
        if dialog.exec() == EventEditDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"] and data["date"]:
                self.module.add_event(data["date"], data["title"], data["description"], parent_id=parent_id)
                self.module.save()
                self._build_tree()

    def _on_edit_item(self, item):
        event_id = item.data(0, Qt.ItemDataRole.UserRole)
        event = self.module._find_by_id(event_id)
        if event:
            dialog = EventEditDialog(event)
            if dialog.exec() == EventEditDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.module.update_event(event_id, **data)
                self.module.save()
                self._build_tree()

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item:
            event_id = item.data(0, Qt.ItemDataRole.UserRole)
            add_child_act = menu.addAction("添加子事件")
            edit_act = menu.addAction("编辑")
            delete_act = menu.addAction("删除（含子事件）")
        else:
            add_act = menu.addAction("添加根事件")

        action = menu.exec(self.tree.mapToGlobal(pos))

        if not item:
            if action and action.text() == "添加根事件":
                self._on_add()
            return

        if action == edit_act:
            self._on_edit_item(item)
        elif action == add_child_act:
            self._on_add_child(event_id)
        elif action == delete_act:
            reply = QMessageBox.question(
                self, "确认删除", "确定删除此事件及其所有子事件？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.module.delete_event(event_id)
                self.module.save()
                self._build_tree()
