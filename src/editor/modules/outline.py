"""大纲模块 — 文档视图 + 树形视图（可下拉展开编辑长内容）。"""

import json
import uuid
import re as re_mod
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton,
    QInputDialog, QMessageBox, QMenu, QTextEdit,
    QHeaderView, QLabel,
)

from .base_module import BaseModule


@dataclass
class OutlineEntry:
    id: str = ""
    title: str = ""
    content: str = ""
    children: List["OutlineEntry"] = field(default_factory=list)
    chapter_ref: str = ""
    status: str = "待写"
    order: int = 0


class OutlineModule(BaseModule):
    """大纲数据管理。"""

    module_id = "outline"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "outline.json"
        self.entries: List[OutlineEntry] = []

    def _to_dict(self, entry):
        d = asdict(entry)
        d["children"] = [self._to_dict(c) for c in entry.children]
        return d

    def _from_dict(self, d):
        children = [self._from_dict(c) for c in d.get("children", [])]
        return OutlineEntry(
            id=d.get("id", uuid.uuid4().hex[:12]),
            title=d.get("title", ""),
            content=d.get("content", ""),
            children=children,
            chapter_ref=d.get("chapter_ref", ""),
            status=d.get("status", "待写"),
            order=d.get("order", 0),
        )

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.entries = [self._from_dict(e) for e in data.get("entries", [])]
            except (json.JSONDecodeError, TypeError) as e:
                print(f"加载大纲失败: {e}")
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
            print(f"保存大纲失败: {e}")
            return False

    def _find_entry(self, entries, entry_id):
        for e in entries:
            if e.id == entry_id:
                return e
            found = self._find_entry(e.children, entry_id)
            if found:
                return found
        return None

    def _find_parent(self, entries, entry_id):
        for i, e in enumerate(entries):
            if e.id == entry_id:
                return entries
            parent = self._find_parent(e.children, entry_id)
            if parent is not None:
                return parent
        return None

    def add_entry(self, title: str, parent_id: str = "") -> Optional[OutlineEntry]:
        entry = OutlineEntry(id=uuid.uuid4().hex[:12], title=title, order=0)
        if parent_id:
            parent = self._find_entry(self.entries, parent_id)
            if parent:
                parent.children.append(entry)
                return entry
        self.entries.append(entry)
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        parent_list = self._find_parent(self.entries, entry_id)
        if parent_list is None:
            return False
        for i, e in enumerate(parent_list):
            if e.id == entry_id:
                parent_list.pop(i)
                return True
        return False

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
                    results.append((e.title, f"大纲 (层级{depth})", e.id))
                _search(e.children, depth + 1)
        _search(self.entries, 0)
        return results

    def to_text(self) -> str:
        """渲染为纯文本。"""
        lines = []
        def _to_text(entries, level):
            indent = "  " * level
            for e in entries:
                prefix = '#' * (level + 1)
                lines.append(f"{indent}{prefix} [{'x' if e.status=='已完成' else ('>' if e.status=='写作中' else ' ')}] {e.title}")
                if e.content:
                    for line in e.content.split("\n"):
                        lines.append(f"{indent}  {line}")
                _to_text(e.children, level + 1)
        _to_text(self.entries, 0)
        return "\n".join(lines)

    def from_text(self, text: str):
        new_entries = []
        stack = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            m = re_mod.match(r"^(\s*)(#+)\s+(\[.\])?\s*(.*)$", stripped)
            if m:
                level = len(m.group(2))
                status_chars = m.group(3) or "[ ]"
                title = m.group(4).strip()
                status = "已完成" if "[x]" in status_chars else ("写作中" if "[>]" in status_chars else "待写")
                entry = OutlineEntry(id=uuid.uuid4().hex[:12], title=title, status=status)
                while stack and stack[-1][1] >= level:
                    stack.pop()
                if not stack:
                    new_entries.append(entry)
                else:
                    stack[-1][0].children.append(entry)
                stack.append((entry, level))
        if new_entries:
            self.entries = new_entries

    def create_dock_widget(self) -> QDockWidget:
        return OutlineDock(self, None)


class ContentEditWrapper(QWidget):
    """内嵌内容编辑器，放在树条目下方。"""

    def __init__(self, entry_id: str, content: str, save_callback, parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.save_callback = save_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 2, 4, 4)
        self.editor = QTextEdit()
        self.editor.setPlainText(content)
        self.editor.setPlaceholderText("在此输入详细内容…")
        self.editor.setFixedHeight(80)
        self.editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e8f0; border-radius: 4px;
                padding: 4px; font-size: 12px; background: #fafbfc;
            }
        """)
        layout.addWidget(self.editor)

    def get_content(self) -> str:
        return self.editor.toPlainText()


class OutlineDock(QDockWidget):
    """大纲 UI — 文档视图 + 树形视图（可下拉展开写长内容）。"""

    _EXPAND_MARKER = "▶ "
    _COLLAPSE_MARKER = "▼ "

    def __init__(self, module: OutlineModule, parent=None):
        super().__init__("大纲", parent)
        self.module = module
        self._editor_widgets: dict[str, ContentEditWrapper] = {}
        self._setup_ui()
        self._build_tree()
        # 默认选中第一个条目，让详情编辑器显示
        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

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

        # 操作行
        btn_row = QHBoxLayout()
        self.view_toggle = QPushButton("文档视图")
        self.view_toggle.setCheckable(True)
        self.view_toggle.setStyleSheet("""
            QPushButton { font-size: 11px; padding: 4px 8px; border: 1px solid #e0e8f0;
                border-radius: 4px; background: #f5f5f5; }
            QPushButton:checked { background: #2196F3; color: white; border-color: #2196F3; }
        """)
        self.view_toggle.toggled.connect(self._on_view_toggle)
        btn_row.addWidget(self.view_toggle)

        add_btn = QPushButton("+ 添加")
        add_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        add_btn.clicked.connect(self._on_add_root)
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

        # ── 详情编辑区（树形模式：选中条目后显示和编辑详细内容） ──
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(4)

        self.detail_title = QLabel("选中条目查看详情")
        self.detail_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a2332; padding: 0 4px;")
        detail_layout.addWidget(self.detail_title)

        self.detail_edit = QTextEdit()
        self.detail_edit.setPlaceholderText("在此编辑详细内容…")
        self.detail_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e8f0; border-radius: 4px;
                padding: 6px; font-size: 13px; line-height: 1.6;
                background: #fafbfc;
            }
        """)
        detail_layout.addWidget(self.detail_edit, stretch=1)

        self.detail_status_label = QLabel("")
        self.detail_status_label.setStyleSheet("font-size: 10px; color: #8a9aaa; padding: 0 4px;")
        detail_layout.addWidget(self.detail_status_label)

        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)

        # 树形视图（默认显示）
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["大纲条目"])
        self.tree.header().setStretchLastSection(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.EditKeyPressed
        )
        self.tree.itemChanged.connect(self._on_item_edited)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)
        layout.addWidget(self.tree, stretch=1)

        # 文档视图（默认隐藏）
        self.doc_edit = QTextEdit()
        self.doc_edit.setPlaceholderText(
            "在这里直接写大纲…\n\n"
            "# [ ] 第一部\n"
            "## [x] 第一章 已完成\n"
            "   第一章的内容描述\n"
            "## [>] 第二章 写作中\n\n"
            "[ ] 待写  [>] 写作中  [x] 已完成\n"
        )
        self.doc_edit.setStyleSheet("border: none; padding: 8px; font-size: 14px; line-height: 1.8;")
        self.doc_edit.setAcceptRichText(False)
        existing = self.module.to_text()
        if existing.strip():
            self.doc_edit.setPlainText(existing)
        self.doc_edit.setVisible(False)
        layout.addWidget(self.doc_edit, stretch=1)

        self.setWidget(widget)
        self._current_detail_id = None

    def _on_view_toggle(self, doc_mode: bool):
        self.tree.setVisible(not doc_mode)
        self.doc_edit.setVisible(doc_mode)
        if doc_mode:
            self._save_tree_content()
            self._on_save_detail()
            self.doc_edit.setPlainText(self.module.to_text())
            self.view_toggle.setText("树形视图")
            self.detail_widget.setVisible(False)
        else:
            text = self.doc_edit.toPlainText()
            self.module.from_text(text)
            self.module.save()
            self._build_tree()
            self.view_toggle.setText("文档视图")
            # 自动选中第一个条目
            if self.tree.topLevelItemCount() > 0:
                self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _on_tree_selection_changed(self, current, previous):
        """点击树条目时显示详情编辑器。"""
        # 先保存上一个
        self._on_save_detail()
        self.detail_widget.setVisible(current is not None)
        if current is None:
            self._current_detail_id = None
            return
        entry_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            self.detail_widget.setVisible(False)
            self._current_detail_id = None
            return
        entry = self.module._find_entry(self.module.entries, entry_id)
        if not entry:
            self.detail_widget.setVisible(False)
            self._current_detail_id = None
            return
        self._current_detail_id = entry_id
        self.detail_title.setText(f"✏ {entry.title}")
        self.detail_edit.setPlainText(entry.content)
        self.detail_status_label.setText(f"状态: {entry.status}")

    def _on_save_detail(self):
        """保存详情编辑器的内容。"""
        if self._current_detail_id:
            content = self.detail_edit.toPlainText()
            self.module.update_entry(self._current_detail_id, content=content)
            self.module.save()

    def _build_tree(self):
        self._editor_widgets.clear()
        self.tree.blockSignals(True)
        self.tree.clear()

        def _add(entries, parent):
            for e in entries:
                item = QTreeWidgetItem(parent)
                icon = {"待写": "○", "写作中": "◐", "已完成": "●"}.get(e.status, "○")
                has_children = bool(e.children)
                has_content = bool(e.content and e.content.strip())
                # 有子条目 → 自带展开箭头；有内容但无子条目 → 加占位符制造箭头
                if has_children:
                    item.setText(0, f"{self._EXPAND_MARKER}{icon} {e.title}")
                elif has_content:
                    item.setText(0, f"{self._EXPAND_MARKER}{icon} {e.title}")
                    ph = QTreeWidgetItem(item)
                    ph.setFlags(Qt.ItemFlag.NoItemFlags)
                else:
                    item.setText(0, f"  {icon} {e.title}")
                item.setData(0, Qt.ItemDataRole.UserRole, e.id)
                tip = e.content[:300] if e.content else ""
                item.setToolTip(0, f"状态: {e.status}\n{tip}" if tip else f"状态: {e.status}")
                _add(e.children, item)

        for e in self.module.entries:
            item = QTreeWidgetItem(self.tree)
            icon = {"待写": "○", "写作中": "◐", "已完成": "●"}.get(e.status, "○")
            has_children = bool(e.children)
            has_content = bool(e.content and e.content.strip())
            if has_children:
                item.setText(0, f"{self._EXPAND_MARKER}{icon} {e.title}")
            elif has_content:
                item.setText(0, f"{self._EXPAND_MARKER}{icon} {e.title}")
                ph = QTreeWidgetItem(item)
                ph.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                item.setText(0, f"  {icon} {e.title}")
            item.setData(0, Qt.ItemDataRole.UserRole, e.id)
            tip = e.content[:300] if e.content else ""
            item.setToolTip(0, f"状态: {e.status}\n{tip}" if tip else f"状态: {e.status}")
            _add(e.children, item)
        self.tree.blockSignals(False)

    def _on_item_expanded(self, item):
        """展开条目时加载内容编辑器。"""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            return
        # 更新标记
        text = item.text(0)
        if text.startswith(self._EXPAND_MARKER):
            item.setText(0, self._COLLAPSE_MARKER + text[len(self._EXPAND_MARKER):])

        entry = self.module._find_entry(self.module.entries, entry_id)
        if not entry or not entry.content:
            return

        # 移除旧 placeholder，插入编辑器
        if entry_id in self._editor_widgets:
            return  # 已经展开了

        wrapper = ContentEditWrapper(entry_id, entry.content, self.module.save)
        self._editor_widgets[entry_id] = wrapper
        self.tree.blockSignals(True)
        # 找到占位子项替换为编辑器
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() == Qt.ItemFlag.NoItemFlags:
                self.tree.setItemWidget(child, 0, wrapper)
                child.setSizeHint(0, QSize(200, 90))
                break
        self.tree.blockSignals(False)

    def _on_item_collapsed(self, item):
        """折叠条目时保存内容并移除编辑器。"""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            return
        # 更新标记
        text = item.text(0)
        if text.startswith(self._COLLAPSE_MARKER):
            item.setText(0, self._EXPAND_MARKER + text[len(self._COLLAPSE_MARKER):])

        # 保存内容
        if entry_id in self._editor_widgets:
            wrapper = self._editor_widgets.pop(entry_id)
            content = wrapper.get_content()
            self.module.update_entry(entry_id, content=content)
            self.module.save()

        # 清理 item widget
        self.tree.blockSignals(True)
        for i in range(item.childCount()):
            child = item.child(i)
            self.tree.removeItemWidget(child, 0)
        self.tree.blockSignals(False)

    def _save_tree_content(self):
        """保存树形视图下所有展开的内容。"""
        for entry_id, wrapper in list(self._editor_widgets.items()):
            content = wrapper.get_content()
            self.module.update_entry(entry_id, content=content)
        self._editor_widgets.clear()

    def _on_save_all(self):
        if self.doc_edit.isVisible():
            text = self.doc_edit.toPlainText()
            self.module.from_text(text)
        else:
            # 保存展开编辑器和详情编辑器
            self._save_tree_content()
            self._on_save_detail()
        self.module.save()
        QMessageBox.information(self, "成功", "大纲已保存")

    def _get_entry_id(self, item):
        return item.data(0, Qt.ItemDataRole.UserRole) or ""

    def _on_add_root(self):
        if self.doc_edit.isVisible():
            current = self.doc_edit.toPlainText()
            if current and not current.endswith("\n"):
                current += "\n"
            self.doc_edit.setPlainText(current + "# [ ] 新条目")
        else:
            title, ok = QInputDialog.getText(self, "添加大纲条目", "条目名称:")
            if ok and title.strip():
                self.module.add_entry(title.strip())
                self._build_tree()

    def _on_delete(self):
        item = self.tree.currentItem()
        if not item:
            return
        entry_id = self._get_entry_id(item)
        if not entry_id:
            return
        reply = QMessageBox.question(self, "确认删除", "删除该条目？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.module.delete_entry(entry_id)
            self._build_tree()

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        entry_id = self._get_entry_id(item)
        if not entry_id:
            return
        menu = QMenu(self)
        add_child = menu.addAction("添加子条目")
        menu.addSeparator()
        rename_act = menu.addAction("重命名")
        status_menu = menu.addMenu("设置状态")
        status_act1 = status_menu.addAction("○ 待写")
        status_act2 = status_menu.addAction("◐ 写作中")
        status_act3 = status_menu.addAction("● 已完成")
        menu.addSeparator()
        delete_act = menu.addAction("删除")

        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == add_child:
            title, ok = QInputDialog.getText(self, "添加子条目", "子条目名称:")
            if ok and title.strip():
                self.module.add_entry(title.strip(), entry_id)
                self._build_tree()
        elif action == rename_act:
            entry = self.module._find_entry(self.module.entries, entry_id)
            if entry:
                title, ok = QInputDialog.getText(self, "重命名", "新名称:", text=entry.title)
                if ok and title.strip():
                    self.module.update_entry(entry_id, title=title.strip())
                    self._build_tree()
        elif action == delete_act:
            self._on_delete()
        elif action == status_act1:
            self.module.update_entry(entry_id, status="待写"); self._build_tree()
        elif action == status_act2:
            self.module.update_entry(entry_id, status="写作中"); self._build_tree()
        elif action == status_act3:
            self.module.update_entry(entry_id, status="已完成"); self._build_tree()
        if action in (status_act1, status_act2, status_act3, rename_act):
            self.module.save()

    def _on_item_edited(self, item, column):
        entry_id = self._get_entry_id(item)
        text = item.text(column).strip()
        if entry_id and text:
            # 去掉标记符号
            clean = text
            for prefix in (self._EXPAND_MARKER, self._COLLAPSE_MARKER, "  "):
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
            icons = {"○", "◐", "●"}
            if len(clean) > 1 and clean[0] in icons:
                clean = clean[2:].strip()
            self.module.update_entry(entry_id, title=clean)
            self.module.save()
