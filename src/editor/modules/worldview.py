"""世界观模块——分章节式记录世界观设定。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton,
    QInputDialog, QMessageBox, QMenu, QTextEdit,
    QSplitter, QLabel,
)

from .base_module import BaseModule


@dataclass
class WorldEntry:
    """一条世界观条目。"""
    id: str = ""
    title: str = ""
    content: str = ""           # HTML 富文本内容
    children: List["WorldEntry"] = field(default_factory=list)
    order: int = 0


class WorldviewModule(BaseModule):
    """世界观数据管理。"""

    module_id = "worldview"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "worldview.json"
        self.entries: List[WorldEntry] = []

    def _to_dict(self, entry: WorldEntry) -> dict:
        d = asdict(entry)
        d["children"] = [self._to_dict(c) for c in entry.children]
        return d

    def _from_dict(self, d: dict) -> WorldEntry:
        children = [self._from_dict(c) for c in d.get("children", [])]
        return WorldEntry(
            id=d.get("id", uuid.uuid4().hex[:12]),
            title=d.get("title", ""),
            content=d.get("content", ""),
            children=children,
            order=d.get("order", 0),
        )

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.entries = [self._from_dict(e) for e in data.get("entries", [])]
            except Exception as e:
                print(f"加载世界观失败: {e}")
                self.entries = []
        if not self.entries:
            self.entries = []

    def save(self):
        try:
            data = {"entries": [self._to_dict(e) for e in self.entries]}
            self.data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return True
        except OSError as e:
            print(f"保存世界观失败: {e}")
            return False

    def _find_entry(self, entries, entry_id):
        for e in entries:
            if e.id == entry_id:
                return e
            found = self._find_entry(e.children, entry_id)
            if found:
                return found
        return None

    def add_entry(self, title: str, parent_id: str = "") -> Optional[WorldEntry]:
        entry = WorldEntry(id=uuid.uuid4().hex[:12], title=title,
                          content="<p></p>", order=0)
        if parent_id:
            parent = self._find_entry(self.entries, parent_id)
            if parent:
                parent.children.append(entry)
                return entry
        self.entries.append(entry)
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        def _remove(entries):
            for i, e in enumerate(entries):
                if e.id == entry_id:
                    entries.pop(i)
                    return True
                if e.children and _remove(e.children):
                    return True
            return False
        return _remove(self.entries)

    def update_entry(self, entry_id: str, **fields) -> bool:
        entry = self._find_entry(self.entries, entry_id)
        if not entry:
            return False
        for k, v in fields.items():
            if hasattr(entry, k):
                setattr(entry, k, v)
        return True

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        def _search(entries, depth):
            for e in entries:
                if q in e.title.lower() or q in e.content.lower():
                    results.append((e.title, f"世界观 (层级{depth})", e.id))
                _search(e.children, depth + 1)
        _search(self.entries, 0)
        return results

    def apply_edit(self, target_name: str, field: str, value: str) -> tuple[bool, str]:
        """AI 编辑世界观条目。"""
        VALID_FIELDS = {"title", "content"}
        if field not in VALID_FIELDS:
            return False, f"世界观不支持字段「{field}」"
        def _find(entries):
            for e in entries:
                if e.title == target_name:
                    return e
                found = _find(e.children)
                if found:
                    return found
            return None
        entry = _find(self.entries)
        if not entry:
            return False, f"未找到世界观条目「{target_name}」"
        setattr(entry, field, value)
        self.save()
        return True, f"已修改世界观 {target_name} 的 {field}"

    def to_text(self, max_len=3000) -> str:
        """将世界观渲染为纯文本供 AI 读取。"""
        lines = []
        def _to_text(entries, depth):
            indent = "  " * depth
            for e in entries:
                import re
                plain = re.sub(r"<[^>]+>", "", e.content)[:200]
                lines.append(f"{indent}# {'#' * depth} {e.title}")
                if plain.strip():
                    lines.append(f"{indent}  {plain.strip()}")
                _to_text(e.children, depth + 1)
        _to_text(self.entries, 0)
        result = "\n".join(lines)
        return result[:max_len]

    def create_dock_widget(self) -> QDockWidget:
        return WorldviewDock(self, None)


class WorldviewDock(QDockWidget):
    """世界观 UI 面板。"""

    def __init__(self, module: WorldviewModule, parent=None):
        super().__init__("🌍 世界观", parent)
        self.module = module
        self._current_id = None
        self._setup_ui()
        self._build_tree()

    def _setup_ui(self):
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(280)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 按钮行
        btn_row = QHBoxLayout()

        add_btn = QPushButton("+ 添加章节")
        add_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("删除选中项")
        delete_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        save_btn.clicked.connect(self._on_save_all)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # 左右分割：树 + 编辑器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 树形列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["世界观条目"])
        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.EditKeyPressed
        )
        self.tree.itemChanged.connect(self._on_item_edited)
        self.tree.currentItemChanged.connect(self._on_selection_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        splitter.addWidget(self.tree)

        # 内容编辑区
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(8, 0, 0, 0)

        self.editor_title = QLabel("选择条目编辑")
        self.editor_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a2332;")
        editor_layout.addWidget(self.editor_title)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("在此写世界观设定内容...\n\n支持富文本格式：加粗、标题、列表等。")
        self.editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e8f0; border-radius: 4px;
                padding: 8px; font-size: 14px; line-height: 1.8;
            }
        """)
        editor_layout.addWidget(self.editor, stretch=1)

        splitter.addWidget(editor_widget)
        splitter.setSizes([200, 400])

        layout.addWidget(splitter, stretch=1)
        self.setWidget(widget)

    def _build_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        def _add(entries, parent):
            for e in entries:
                item = QTreeWidgetItem(parent)
                item.setText(0, e.title)
                item.setData(0, Qt.ItemDataRole.UserRole, e.id)
                if e.children:
                    _add(e.children, item)
        for e in self.module.entries:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, e.title)
            item.setData(0, Qt.ItemDataRole.UserRole, e.id)
            if e.children:
                _add(e.children, item)
        self.tree.blockSignals(False)

    def _get_entry_id(self, item) -> str:
        return item.data(0, Qt.ItemDataRole.UserRole) or "" if item else ""

    def _on_add(self):
        item = self.tree.currentItem()
        parent_id = self._get_entry_id(item) if item else ""
        title, ok = QInputDialog.getText(self, "添加世界观条目", "条目名称:")
        if ok and title.strip():
            self.module.add_entry(title.strip(), parent_id)
            self.module.save()
            self._build_tree()

    def _on_delete(self):
        item = self.tree.currentItem()
        if not item:
            return
        eid = self._get_entry_id(item)
        if not eid:
            return
        reply = QMessageBox.question(self, "确认删除",
            "删除该条目及其所有子条目？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.module.delete_entry(eid)
            self.module.save()
            self._build_tree()

    def _on_selection_changed(self, current, previous):
        # 保存当前编辑
        self._on_save_current()
        eid = self._get_entry_id(current)
        entry = self.module._find_entry(self.module.entries, eid) if eid else None
        if entry:
            self._current_id = entry.id
            self.editor_title.setText(f"✏ {entry.title}")
            self.editor.setHtml(entry.content)
            self.editor.setEnabled(True)
        else:
            self._current_id = None
            self.editor_title.setText("选择条目编辑")
            self.editor.clear()
            self.editor.setEnabled(False)

    def _on_save_current(self):
        if self._current_id:
            content = self.editor.toHtml()
            self.module.update_entry(self._current_id, content=content)

    def _on_save_all(self):
        self._on_save_current()
        self.module.save()
        QMessageBox.information(self, "成功", "世界观已保存")

    def _on_item_edited(self, item, column):
        eid = self._get_entry_id(item)
        new_title = item.text(column).strip()
        if eid and new_title:
            self.module.update_entry(eid, title=new_title)
            self.module.save()

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        eid = self._get_entry_id(item)

        menu = QMenu(self)
        add_child = menu.addAction("添加子条目")
        menu.addSeparator()
        add_sibling = menu.addAction("添加同级")
        menu.addSeparator()
        rename_act = menu.addAction("重命名")
        delete_act = menu.addAction("删除")

        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == add_child:
            title, ok = QInputDialog.getText(self, "添加子条目", "条目名称:")
            if ok and title.strip():
                self.module.add_entry(title.strip(), eid)
                self.module.save()
                self._build_tree()
        elif action == add_sibling:
            title, ok = QInputDialog.getText(self, "添加同级条目", "条目名称:")
            if ok and title.strip():
                self.module.add_entry(title.strip())
                self.module.save()
                self._build_tree()
        elif action == rename_act:
            self.tree.editItem(item, 0)
        elif action == delete_act:
            self._on_delete()
