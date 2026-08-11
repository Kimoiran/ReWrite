"""大纲模块 — 文档视图 + 树形视图（可下拉展开编辑长内容）。"""

import json
import uuid
import re as re_mod
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton,
    QInputDialog, QMessageBox, QMenu, QTextEdit,
    QHeaderView, QLabel, QSplitter, QRadioButton,
)

from src.ui.theme import Color

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
            # 原子写:先写临时文件再替换,避免崩溃截断损坏 outline.json
            tmp = self.data_path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            import os as _os
            _os.replace(str(tmp), str(self.data_path))
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

    def apply_edit(self, target_name: str, field: str, value: str) -> tuple[bool, str]:
        """AI 编辑大纲条目内容。"""
        VALID_FIELDS = {"title", "content", "status"}
        if field not in VALID_FIELDS:
            return False, f"不支持修改字段「{field}」, 支持: {', '.join(sorted(VALID_FIELDS))}"
        if field == "status" and value not in ("待写", "写作中", "已完成"):
            return False, f"状态值必须是: 待写/写作中/已完成"
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
            return False, f"未找到大纲条目「{target_name}」"
        setattr(entry, field, value)
        self.save()
        return True, f"已修改大纲条目 {target_name} 的 {field}"

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
        """解析文档视图文本。支持内容行(无 # 前缀的缩进行)归入最近条目。

        安全:标题行必须带 # 前缀;解析结果为空时不动现有数据(防止清空)。
        """
        new_entries = []
        stack = []
        current = None  # 最近解析的条目,内容行归入它
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
                current = entry
            elif current is not None:
                # 内容行(无 # 前缀):归入最近解析的条目,保留原有换行
                if current.content:
                    current.content += "\n"
                current.content += stripped
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
        self._dirty = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 2, 4, 4)
        self.editor = QTextEdit()
        self.editor.setPlainText(content)
        # 初始填充不算编辑;此后用户输入才置 dirty
        self.editor.textChanged.connect(self._on_changed)
        self.editor.setPlaceholderText("在此输入详细内容…")
        self.editor.setFixedHeight(80)
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Color.BORDER}; border-radius: 4px;
                padding: 4px; font-size: 12px; background: {Color.SURFACE};
            }}
            QTextEdit:focus {{ border-color: {Color.PRIMARY}; }}
        """)
        layout.addWidget(self.editor)

    def _on_changed(self):
        self._dirty = True

    def is_dirty(self) -> bool:
        """是否被用户实际编辑过(用于决定是否写回,避免旧快照覆盖新内容)。"""
        return self._dirty

    def get_content(self) -> str:
        return self.editor.toPlainText()


class OutlineDock(QDockWidget):
    """大纲 UI — 文档视图 + 树形视图（可下拉展开写长内容）。"""

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
        btn_row.setSpacing(4)
        self.view_toggle = QPushButton("文档视图")
        self.view_toggle.setCheckable(True)
        self.view_toggle.setToolTip("切换到大纲文档编辑模式(文本语法)")
        self.view_toggle.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 8px; border: 1px solid {Color.BORDER};
                border-radius: 4px; background: {Color.SURFACE}; color: {Color.TEXT_SECONDARY}; }}
            QPushButton:hover {{ border-color: {Color.PRIMARY}; }}
            QPushButton:checked {{ background: {Color.PRIMARY}; color: white; border-color: {Color.PRIMARY}; }}
        """)
        self.view_toggle.toggled.connect(self._on_view_toggle)
        btn_row.addWidget(self.view_toggle)

        add_btn = QPushButton("+ 添加")
        add_btn.setToolTip("添加顶层条目")
        add_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 10px; border: 1px solid {Color.PRIMARY};
                border-radius: 4px; background: {Color.SURFACE}; color: {Color.PRIMARY_DARK}; }}
            QPushButton:hover {{ background: {Color.PRIMARY_LIGHT}; }}
        """)
        add_btn.clicked.connect(self._on_add_root)
        btn_row.addWidget(add_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("删除选中项")
        delete_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 8px; border: 1px solid {Color.ERROR_BORDER};
                border-radius: 4px; background: {Color.SURFACE}; color: {Color.ERROR_TEXT}; }}
            QPushButton:hover {{ background: {Color.ERROR_BG}; }}
        """)
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 12px; border: none; border-radius: 4px;
                background: {Color.SUCCESS}; color: white; font-weight: 600; }}
            QPushButton:hover {{ background: {Color.SUCCESS_TEXT}; }}
        """)
        save_btn.clicked.connect(self._on_save_all)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # ── 详情编辑区(树形模式:选中条目后显示和编辑详细内容) ──
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(4)

        self.detail_title = QLabel("选中条目查看详情")
        self.detail_title.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {Color.TEXT}; padding: 0 4px;")
        detail_layout.addWidget(self.detail_title)

        # 状态行:标题 + 状态徽章 + 状态切换
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addStretch()
        self.status_radios = {}
        for st in ("待写", "写作中", "已完成"):
            rb = QRadioButton(st)
            rb.setStyleSheet(f"font-size: 11px; color: {Color.TEXT_SECONDARY}; spacing: 4px;")
            rb.toggled.connect(lambda checked, s=st: self._on_status_changed(s) if checked else None)
            self.status_radios[st] = rb
            status_row.addWidget(rb)
        detail_layout.addLayout(status_row)

        self.detail_edit = QTextEdit()
        self.detail_edit.setPlaceholderText("在此编辑详细内容…")
        self.detail_edit.setMinimumHeight(120)
        self.detail_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Color.BORDER}; border-radius: 6px;
                padding: 8px; font-size: 13px; line-height: 1.6;
                background: {Color.SURFACE};
            }}
            QTextEdit:focus {{ border-color: {Color.PRIMARY}; }}
        """)
        # 脏标记:仅用户实际编辑过详情区才写回,避免旧快照覆盖展开编辑器的新内容
        self._detail_dirty = False
        self.detail_edit.textChanged.connect(self._on_detail_changed)
        detail_layout.addWidget(self.detail_edit, stretch=1)

        self.detail_status_label = QLabel("")
        self.detail_status_label.setStyleSheet(
            f"font-size: 10px; color: {Color.TEXT_HINT}; padding: 0 4px;")
        detail_layout.addWidget(self.detail_status_label)

        self.detail_widget.setVisible(False)

        # 树形视图
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(["大纲条目"])
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setVisible(False)  # 单列不需要表头,更简洁
        self.tree.setIndentation(16)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                border: 1px solid {Color.BORDER}; border-radius: 6px;
                background: {Color.SURFACE}; padding: 2px;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 4px 6px; border-radius: 4px; color: {Color.TEXT};
            }}
            QTreeWidget::item:selected {{
                background: {Color.PRIMARY_LIGHT}; color: {Color.PRIMARY_DARK};
            }}
            QTreeWidget::item:hover {{
                background: {Color.BG_ALT};
            }}
            QTreeWidget::item:selected:hover {{
                background: {Color.PRIMARY_LIGHT};
            }}
        """)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.EditKeyPressed
        )
        self.tree.itemChanged.connect(self._on_item_edited)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)

        # 用 QSplitter 让树和详情编辑区都可以自由缩放
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.detail_widget)
        splitter.setStretchFactor(0, 2)  # 树占 2/3
        splitter.setStretchFactor(1, 1)  # 详情占 1/3
        layout.addWidget(splitter, stretch=1)

        # 文档视图（默认隐藏）
        self.doc_edit = QTextEdit()
        self.doc_edit.setPlaceholderText(
            "# [ ] 第一部\n"
            "## [x] 第一章 已完成\n"
            "    第一章的内容描述\n"
            "## [>] 第二章 写作中\n\n"
            "[ ] 待写  [>] 写作中  [x] 已完成\n"
        )
        self.doc_edit.setStyleSheet(
            f"border: 1px solid {Color.BORDER}; border-radius: 6px; padding: 8px; "
            f"font-size: 14px; line-height: 1.8; background: {Color.SURFACE};")
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
            snapshot = self.module.to_text()
            self.doc_edit.setPlainText(snapshot)
            self._doc_snapshot = snapshot  # 保存快照，切回时比对
            self.view_toggle.setText("树形视图")
            self.detail_widget.setVisible(False)
        else:
            text = self.doc_edit.toPlainText()
            # 只有用户确实编辑了文档才重新解析；未改动则直接从内存重建树
            if text.strip() and text != getattr(self, '_doc_snapshot', ''):
                self.module.from_text(text)
                self.module.save()
            self._build_tree()
            self.view_toggle.setText("文档视图")
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
        self._detail_dirty = False  # 填充是程序行为,不算用户编辑
        self.detail_status_label.setText(f"状态: {entry.status}")
        # 同步状态单选按钮(blockSignals 防递归触发保存)
        for st, rb in self.status_radios.items():
            rb.blockSignals(True)
            rb.setChecked(st == entry.status)
            rb.blockSignals(False)

    def _on_status_changed(self, status: str):
        """详情区状态切换:立即保存并刷新树。"""
        if not self._current_detail_id:
            return
        # 顺序关键:① 展开的内嵌编辑器写回 ② 详情编辑器写回(当前操作区优先) ③ 更新状态 ④ 落盘。
        # 重建树后 setCurrentItem 触发的 _on_save_detail 保存的是最新内容,不会互相覆盖。
        self._save_tree_content()
        self._on_save_detail()
        self.module.update_entry(self._current_detail_id, status=status)
        self.module.save()
        self.detail_status_label.setText(f"状态: {status}")
        # 刷新树以更新图标与颜色
        self._build_tree()
        # 恢复选中
        def _find_item(parent_item=None):
            for i in range(parent_item.childCount() if parent_item else self.tree.topLevelItemCount()):
                item = parent_item.child(i) if parent_item else self.tree.topLevelItem(i)
                if item.data(0, Qt.ItemDataRole.UserRole) == self._current_detail_id:
                    return item
                found = _find_item(item)
                if found:
                    return found
            return None
        target = _find_item()
        if target:
            self.tree.setCurrentItem(target)

    def _on_detail_changed(self):
        """详情编辑器内容变化(用户编辑)时置脏标记。"""
        self._detail_dirty = True

    def _on_save_detail(self):
        """保存详情编辑器的内容(仅用户实际编辑过且内容有变化,避免旧快照覆盖其他来源的新内容)。"""
        if self._current_detail_id and self._detail_dirty:
            content = self.detail_edit.toPlainText()
            entry = self.module._find_entry(self.module.entries, self._current_detail_id)
            if entry and content != entry.content:
                self.module.update_entry(self._current_detail_id, content=content)
                self.module.save()
            self._detail_dirty = False

    _STATUS_ICONS = {"待写": "○", "写作中": "◐", "已完成": "●"}

    @staticmethod
    def _status_color(status: str) -> str:
        """状态色(运行时取当前主题,主题切换自动跟随)。"""
        return {"待写": Color.TEXT_SECONDARY, "写作中": Color.PRIMARY_DARK,
                "已完成": Color.SUCCESS_TEXT}.get(status, Color.TEXT)

    def _build_tree(self):
        # 重建前:① 保存展开编辑器的脏内容(避免重建丢失) ② 收集展开状态(重建后恢复)
        self._save_tree_content()
        expanded_ids = self._collect_expanded_ids()
        self._editor_widgets.clear()
        self.tree.blockSignals(True)
        self.tree.clear()

        def _make_item(e, parent) -> QTreeWidgetItem:
            item = QTreeWidgetItem(parent)
            icon = self._STATUS_ICONS.get(e.status, "○")
            has_children = bool(e.children)
            has_content = bool(e.content and e.content.strip())
            # 文本只含 状态图标 + 标题(无 ▶/▼ 前缀,展开状态由箭头本身指示)
            item.setText(0, f"{icon} {e.title}")
            item.setForeground(0, QColor(self._status_color(e.status)))
            item.setData(0, Qt.ItemDataRole.UserRole, e.id)
            tip = e.content[:300] if e.content else ""
            item.setToolTip(0, f"状态: {e.status}\n{tip}" if tip else f"状态: {e.status}")
            # 有内容但无子条目 → 放一个隐藏占位子项制造展开箭头(折叠时不可见,不再有空白行)
            if not has_children and has_content:
                ph = QTreeWidgetItem(item)
                ph.setFlags(Qt.ItemFlag.NoItemFlags)
                ph.setHidden(True)
            for c in e.children:
                _make_item(c, item)
            return item

        for e in self.module.entries:
            _make_item(e, self.tree)
        self.tree.blockSignals(False)
        # 恢复之前的展开状态(更改条目后子条目不再自动收起)
        self._restore_expanded(expanded_ids)

    def _collect_expanded_ids(self) -> set:
        """收集当前展开的条目 id(重建后用于恢复)。"""
        ids = set()

        def _walk(parent):
            n = parent.childCount() if parent else self.tree.topLevelItemCount()
            for i in range(n):
                item = parent.child(i) if parent else self.tree.topLevelItem(i)
                eid = item.data(0, Qt.ItemDataRole.UserRole)
                if eid and item.isExpanded():
                    ids.add(eid)
                _walk(item)

        _walk(None)
        return ids

    def _restore_expanded(self, ids: set):
        """重建后恢复展开状态(触发 itemExpanded → 重新挂载内容编辑器)。"""
        if not ids:
            return

        def _walk(parent):
            n = parent.childCount() if parent else self.tree.topLevelItemCount()
            for i in range(n):
                item = parent.child(i) if parent else self.tree.topLevelItem(i)
                eid = item.data(0, Qt.ItemDataRole.UserRole)
                if eid and eid in ids:
                    item.setExpanded(True)
                _walk(item)

        _walk(None)

    def _on_item_expanded(self, item):
        """展开条目时加载内容编辑器。"""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            return

        entry = self.module._find_entry(self.module.entries, entry_id)
        if not entry or not entry.content:
            return

        # 移除旧 placeholder，插入编辑器
        if entry_id in self._editor_widgets:
            return  # 已经展开了

        wrapper = ContentEditWrapper(entry_id, entry.content, self.module.save)
        self._editor_widgets[entry_id] = wrapper
        self.tree.blockSignals(True)
        # 找到隐藏的占位子项,显示并替换为编辑器
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() == Qt.ItemFlag.NoItemFlags:
                child.setHidden(False)
                self.tree.setItemWidget(child, 0, wrapper)
                child.setSizeHint(0, QSize(200, 90))
                break
        self.tree.blockSignals(False)

    def _on_item_collapsed(self, item):
        """折叠条目时保存内容并移除编辑器。"""
        entry_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not entry_id:
            return

        # 保存内容(仅用户实际编辑过才写回,避免旧快照覆盖其他来源的新内容)
        if entry_id in self._editor_widgets:
            wrapper = self._editor_widgets.pop(entry_id)
            if wrapper.is_dirty():
                content = wrapper.get_content()
                self.module.update_entry(entry_id, content=content)
                self.module.save()

        # 清理 item widget 并重新隐藏占位子项(避免折叠后出现空白行)
        self.tree.blockSignals(True)
        for i in range(item.childCount()):
            child = item.child(i)
            self.tree.removeItemWidget(child, 0)
            if child.flags() == Qt.ItemFlag.NoItemFlags:
                child.setHidden(True)
        self.tree.blockSignals(False)

    def _save_tree_content(self):
        """保存树形视图下所有展开的内容(仅用户实际编辑过且内容有变化的,避免旧快照覆盖新内容)。"""
        changed = False
        for entry_id, wrapper in list(self._editor_widgets.items()):
            if wrapper.is_dirty():
                content = wrapper.get_content()
                entry = self.module._find_entry(self.module.entries, entry_id)
                if entry and content != entry.content:
                    self.module.update_entry(entry_id, content=content)
                    changed = True
        if changed:
            # 立即落盘,防止"展开编辑后直接关闭"丢失内容
            self.module.save()
        self._editor_widgets.clear()

    def _on_save_all(self):
        if self.doc_edit.isVisible():
            text = self.doc_edit.toPlainText().strip()
            if text:
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
                self.module.save()
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
            self.module.save()
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
                self.module.save()
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
            # 去掉状态图标前缀(图标 + 空格 + 标题),仅当格式匹配时剥离,避免误伤以图标开头的标题
            clean = text
            if (len(clean) > 2 and clean[0] in self._STATUS_ICONS.values()
                    and clean[1] == " "):
                clean = clean[2:].strip()
            self.module.update_entry(entry_id, title=clean)
            self.module.save()
