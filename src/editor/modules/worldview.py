"""世界观模块——分章节式记录世界观设定。"""

import json
import os as _os
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import shutil as _su

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton,
    QInputDialog, QMessageBox, QMenu, QTextEdit,
    QSplitter, QLabel,
)

from src.ui.theme import Color

from .base_module import BaseModule


def _rotate_backup(file_path: str, max_keep: int = 20):
    """滚动备份文件，保留最近 max_keep 份(按编号数字排序)。"""
    p = Path(file_path)
    if not p.exists():
        return
    existing = sorted(
        (f for f in p.parent.glob(p.name + ".bak.*")
         if f.name.rsplit(".", 1)[-1].isdigit()),
        key=lambda f: int(f.name.rsplit(".", 1)[-1]),
    )
    while len(existing) >= max_keep:
        existing.pop(0).unlink(missing_ok=True)
    next_num = (int(existing[-1].name.rsplit(".", 1)[-1]) + 1) if existing else 1
    _su.copy2(p, p.parent / f"{p.name}.bak.{next_num}")


def _looks_like_html(text: str) -> bool:
    """判断内容是否为 QTextEdit 产出的 HTML。

    采用开头特征判定(QTextEdit 的 toHtml 输出以 <!DOCTYPE/<html/<body 开头),
    避免把含 <b>/<br 字面量的普通 Markdown 文本误判为 HTML 而破坏数据。
    """
    low = (text or "").lstrip().lower()
    return low.startswith(("<!doctype", "<html", "<body", "<p", "<div",
                           "<table", "<ul", "<ol"))


@dataclass
class WorldEntry:
    """一条世界观条目。"""
    id: str = ""
    title: str = ""
    content: str = ""           # Markdown 纯文本内容(统一格式,零转换)
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
        # 旧数据迁移:HTML 富文本内容一次性转为纯文本(统一 Markdown 存储)
        if self._migrate_html_to_text():
            self.save()

    def _migrate_html_to_text(self) -> bool:
        """把 content 中的旧 HTML(QTextEdit 富文本格式)转为纯文本。返回是否发生迁移。"""
        from PySide6.QtGui import QTextDocument
        changed = False

        def _walk(entries):
            nonlocal changed
            for e in entries:
                c = e.content or ""
                if _looks_like_html(c):
                    doc = QTextDocument()
                    doc.setHtml(e.content)
                    e.content = doc.toPlainText()
                    changed = True
                if e.children:
                    _walk(e.children)

        _walk(self.entries)
        return changed

    def save(self, backup: bool = True):
        try:
            # 滚动备份(保留最近 20 份);自动保存等高频路径可传 backup=False 跳过
            if backup:
                _rotate_backup(str(self.data_path))
            data = {"entries": [self._to_dict(e) for e in self.entries]}
            # 原子写:先写临时文件再替换,避免崩溃截断损坏 worldview.json
            tmp = self.data_path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _os.replace(str(tmp), str(self.data_path))
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
                          content="", order=0)
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

    def to_text(self, max_len=8000) -> str:
        """将世界观渲染为纯文本供 AI 读取(兼容旧 HTML 数据)。"""
        import re as _re
        lines = []

        def _to_text(entries, depth):
            indent = "  " * depth
            for e in entries:
                c = e.content or ""
                if _looks_like_html(c):
                    plain = _re.sub(r"<[^>]+>", "", c)
                else:
                    plain = c
                plain = plain.strip()[:800]  # 单条上限 800，总上限由 max_len 控制
                lines.append(f"{indent}# {'#' * depth} {e.title}")
                if plain:
                    lines.append(f"{indent}  {plain}")
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
        btn_row.setSpacing(4)

        add_btn = QPushButton("+ 添加章节")
        add_btn.setToolTip("添加顶层条目(选中条目时为子条目)")
        add_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 10px; border: 1px solid {Color.PRIMARY};
                border-radius: 4px; background: {Color.SURFACE}; color: {Color.PRIMARY_DARK}; }}
            QPushButton:hover {{ background: {Color.PRIMARY_LIGHT}; }}
        """)
        add_btn.clicked.connect(self._on_add)
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

        # 左右分割：树 + 编辑器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 树形列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["世界观条目"])
        self.tree.header().setVisible(False)
        self.tree.setIndentation(16)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                border: 1px solid {Color.BORDER}; border-radius: 6px;
                background: {Color.SURFACE}; padding: 2px; font-size: 13px;
            }}
            QTreeWidget::item {{ padding: 4px 6px; border-radius: 4px; color: {Color.TEXT}; }}
            QTreeWidget::item:selected {{ background: {Color.PRIMARY_LIGHT}; color: {Color.PRIMARY_DARK}; }}
            QTreeWidget::item:hover {{ background: {Color.BG_ALT}; }}
        """)
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
        self.editor_title.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {Color.TEXT};")
        editor_layout.addWidget(self.editor_title)

        # 格式化工具栏:所见即所得(选中文本直接变粗/斜体/标题,立即可见)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        btn_style = f"""
            QPushButton {{ font-size: 11px; padding: 2px 8px;
                border: 1px solid {Color.BORDER}; border-radius: 3px;
                background: {Color.SURFACE}; color: {Color.TEXT_SECONDARY}; }}
            QPushButton:hover {{ background: {Color.BG_ALT}; }}
        """
        bold_btn = QPushButton("B")
        bold_btn.setStyleSheet(btn_style + "QPushButton { font-weight: bold; }")
        bold_btn.setToolTip("加粗"); bold_btn.clicked.connect(self._toggle_bold)
        toolbar.addWidget(bold_btn)

        italic_btn = QPushButton("I")
        italic_btn.setStyleSheet(btn_style + "QPushButton { font-style: italic; }")
        italic_btn.setToolTip("斜体"); italic_btn.clicked.connect(self._toggle_italic)
        toolbar.addWidget(italic_btn)

        h1_btn = QPushButton("H1"); h1_btn.setStyleSheet(btn_style)
        h1_btn.setToolTip("一级标题"); h1_btn.clicked.connect(lambda: self._set_heading(1))
        toolbar.addWidget(h1_btn)

        h2_btn = QPushButton("H2"); h2_btn.setStyleSheet(btn_style)
        h2_btn.setToolTip("二级标题"); h2_btn.clicked.connect(lambda: self._set_heading(2))
        toolbar.addWidget(h2_btn)

        h3_btn = QPushButton("H3"); h3_btn.setStyleSheet(btn_style)
        h3_btn.setToolTip("三级标题"); h3_btn.clicked.connect(lambda: self._set_heading(3))
        toolbar.addWidget(h3_btn)

        normal_btn = QPushButton("T"); normal_btn.setStyleSheet(btn_style)
        normal_btn.setToolTip("正文(取消标题)")
        normal_btn.clicked.connect(lambda: self._set_heading(0))
        toolbar.addWidget(normal_btn)

        list_btn = QPushButton("• List"); list_btn.setStyleSheet(btn_style)
        list_btn.setToolTip("无序列表"); list_btn.clicked.connect(self._insert_list)
        toolbar.addWidget(list_btn)

        table_btn = QPushButton("+ Table"); table_btn.setStyleSheet(btn_style)
        table_btn.setToolTip("插入3行3列表格"); table_btn.clicked.connect(self._insert_table)
        toolbar.addWidget(table_btn)

        toolbar.addStretch()
        editor_layout.addLayout(toolbar)

        # 富文本编辑器:所见即所得(输入即渲染,保存时无损导出 Markdown)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText("在此编写世界观设定…(加粗/斜体/标题/列表/表格,所见即所得)")
        # 标题级默认样式表:headingLevel 设置后立即渲染(h1-h6 视觉即时生效,
        # 修复"选 H2 后需切换条目才显示"的延迟渲染问题)
        self.editor.document().setDefaultStyleSheet(
            "h1 { font-size: 17pt; font-weight: 700; margin-top: 0; margin-bottom: 6px; }"
            "h2 { font-size: 15pt; font-weight: 700; margin-top: 0; margin-bottom: 6px; }"
            "h3 { font-size: 14pt; font-weight: 700; margin-top: 0; margin-bottom: 6px; }"
            "h4 { font-size: 13pt; font-weight: 700; }"
            "h5, h6 { font-size: 12pt; font-weight: 700; }")
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Color.BORDER}; border-radius: 6px;
                padding: 8px; font-size: 14pt; line-height: 1.8;
                background: {Color.SURFACE};
                font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
            }}
            QTextEdit:focus {{ border-color: {Color.PRIMARY}; }}
        """)
        editor_layout.addWidget(self.editor, stretch=1)

        # 自动保存：停止输入 1 秒后自动存盘(导出为无损 Markdown)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1000)
        self._autosave_timer.timeout.connect(self._auto_save)
        self.editor.textChanged.connect(self._autosave_timer.start)

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
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
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

    # ── 所见即所得格式化操作(富文本直接生效,保存时无损导出) ──

    def _toggle_bold(self):
        """加粗选中文本/当前光标后文本。"""
        fmt = self.editor.currentCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Normal if fmt.fontWeight() >= QFont.Weight.Bold
            else QFont.Weight.Bold)
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _toggle_italic(self):
        """斜体选中文本/当前光标后文本。"""
        fmt = self.editor.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def _set_heading(self, level: int):
        """将文本设为标题(1-3 级,0 为正文)。

        有选区且选区从块首开始(单块内):把选中文字拆出为独立标题块,
        其余保持正文——符合"选中段首'铜币'点 H2,只有'铜币'变标题"的直觉;
        无选区/段中选区/跨块选区:整个光标所在块设为标题。
        视觉:直接合并字符格式(字号+加粗),立即生效(不依赖 Qt 样式表);
        语义:设置 headingLevel,保证导出为 #。
        """
        from PySide6.QtGui import QTextBlockFormat, QTextCharFormat, QFont, QTextCursor
        sizes = {0: 14, 1: 17, 2: 15, 3: 14}
        cfmt = QTextCharFormat()
        cfmt.setFontPointSize(sizes.get(level, 14))
        cfmt.setFontWeight(QFont.Weight.Bold if level > 0 else QFont.Weight.Normal)
        bfmt = QTextBlockFormat()
        if level > 0:
            bfmt.setHeadingLevel(level)

        cursor = self.editor.textCursor()
        selected = cursor.selectedText()
        sel_start = cursor.selectionStart()
        start_block = self.editor.document().findBlock(sel_start)
        at_block_start = (sel_start == start_block.position())
        if (cursor.hasSelection() and selected and at_block_start
                and "\u2029" not in selected and "\u2028" not in selected
                and "\n" not in selected):
            # 段首选区:拆出为独立标题块,原块剩余保持正文
            cursor.removeSelectedText()
            if cursor.block().text() == "":
                # 选区覆盖整块:直接整块应用,避免残留空块
                cursor.insertText(selected)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.setBlockFormat(bfmt)
                cursor.mergeCharFormat(cfmt)
                cursor.clearSelection()
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
                self.editor.setTextCursor(cursor)
                self.editor.setCurrentCharFormat(cfmt)
                self.editor.setFocus()
                return
            # 拆分分支只处理段首选区(at_block_start 已保证),删除后光标必在块首
            pos = cursor.position()       # 记录删除点(块首)
            cursor.insertBlock()          # 分裂:空前段 / 后段
            cursor.setPosition(pos)       # 回到分裂点(空前段)
            cursor.setBlockFormat(bfmt)   # 标题块格式
            cursor.setCharFormat(cfmt)    # 标题块字符格式(输入/插入生效)
            cursor.insertText(selected)   # 标题文本
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()
            return

        # 无选区、段中选区或跨块选区:整块应用标题
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.setBlockFormat(bfmt)
        cursor.mergeCharFormat(cfmt)
        # 清除选中并移光标到块尾,避免后续打字替换整个标题块
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        self.editor.setTextCursor(cursor)
        # 仅空块场景:设置当前默认字符格式,后续输入也按标题样式显示;
        # 有内容块不设置(光标处格式已正确),避免格式残留到其他块/后续输入
        if cursor.block().text() == "":
            self.editor.setCurrentCharFormat(cfmt)
        self.editor.setFocus()

    def _insert_list(self):
        """插入无序列表。"""
        from PySide6.QtGui import QTextListFormat
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDisc)
        self.editor.textCursor().createList(fmt)
        self.editor.setFocus()

    def _insert_table(self):
        """插入 3 行 3 列富文本表格。"""
        self.editor.textCursor().insertTable(3, 3)
        self.editor.setFocus()

    def _on_selection_changed(self, current, previous):
        # 保存当前编辑(切换条目不滚动备份,避免高频复制)
        self._on_save_current(backup=False)
        eid = self._get_entry_id(current)
        entry = self.module._find_entry(self.module.entries, eid) if eid else None
        if entry:
            self._current_id = entry.id
            self.editor_title.setText(f"✏ {entry.title}")
            # 富文本加载:MD → HTML 渲染(所见即所得)
            from .md_document import load_markdown_into
            load_markdown_into(self.editor, entry.content)
            self.editor.setEnabled(True)
        else:
            self._current_id = None
            self.editor_title.setText("选择条目编辑")
            self.editor.clear()
            self.editor.setEnabled(False)

    def _auto_save(self):
        """停止输入 1 秒后自动存盘(仅当正在编辑条目时)。高频路径不滚动备份。"""
        if self._current_id:
            self._on_save_current(backup=False)

    def _on_save_current(self, backup: bool = True):
        """保存当前条目内容(富文本 → 无损 Markdown 导出,立即落盘)。"""
        if self._current_id:
            from .md_document import save_markdown_from
            content = save_markdown_from(self.editor)
            self.module.update_entry(self._current_id, content=content)
            self.module.save(backup=backup)

    def closeEvent(self, event):
        """面板关闭前补一次保存(避免 1 秒防抖窗口内的编辑丢失)。"""
        self._on_save_current(backup=False)
        super().closeEvent(event)

    def _on_save_all(self):
        self._on_save_current(backup=False)
        self.module.save()  # 统一一次备份 + 落盘
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
            eid = self._get_entry_id(item)
            if eid:
                new_title, ok = QInputDialog.getText(self, "重命名", "新标题:", text=item.text(0))
                if ok and new_title.strip():
                    self.module.update_entry(eid, title=new_title.strip())
                    self.module.save()
                    self._build_tree()
        elif action == delete_act:
            self._on_delete()
