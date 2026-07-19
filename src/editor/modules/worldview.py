"""世界观模块——分章节式记录世界观设定。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import shutil as _su

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont


def _rotate_backup(file_path: str, max_keep: int = 20):
    """滚动备份文件，保留最近 max_keep 份。"""
    p = Path(file_path)
    if not p.exists():
        return
    existing = sorted(p.parent.glob(p.name + ".bak.*"))
    while len(existing) >= max_keep:
        existing.pop(0).unlink(missing_ok=True)
    next_num = (int(existing[-1].name.rsplit(".", 1)[-1]) + 1) if existing else 1
    _su.copy2(p, p.parent / f"{p.name}.bak.{next_num}")
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
            # 先滚动备份（保留最近 20 份）
            _rotate_backup(str(self.data_path))
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

    def to_text(self, max_len=8000) -> str:
        """将世界观渲染为纯文本供 AI 读取。"""
        lines = []
        def _to_text(entries, depth):
            indent = "  " * depth
            for e in entries:
                import re
                plain = re.sub(r"<[^>]+>", "", e.content)[:800]  # 单条上限 800，总上限由 max_len 控制
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

        # 格式化工具栏：插入 Markdown 标记 → 重渲染
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        btn_style = """
            QPushButton { font-size: 11px; padding: 2px 8px;
                border: 1px solid #d0d0d0; border-radius: 3px;
                background: #f5f5f5; color: #333; }
            QPushButton:hover { background: #e8e8e8; }
        """
        bold_btn = QPushButton("B")
        bold_btn.setStyleSheet(btn_style + "QPushButton { font-weight: bold; }")
        bold_btn.setToolTip("加粗"); bold_btn.clicked.connect(lambda: self._md_action("**"))
        toolbar.addWidget(bold_btn)

        italic_btn = QPushButton("I")
        italic_btn.setStyleSheet(btn_style + "QPushButton { font-style: italic; }")
        italic_btn.setToolTip("斜体"); italic_btn.clicked.connect(lambda: self._md_action("*"))
        toolbar.addWidget(italic_btn)

        h1_btn = QPushButton("H1"); h1_btn.setStyleSheet(btn_style)
        h1_btn.setToolTip("一级标题"); h1_btn.clicked.connect(lambda: self._md_action("# ", line_prefix=True))
        toolbar.addWidget(h1_btn)

        h2_btn = QPushButton("H2"); h2_btn.setStyleSheet(btn_style)
        h2_btn.setToolTip("二级标题"); h2_btn.clicked.connect(lambda: self._md_action("## ", line_prefix=True))
        toolbar.addWidget(h2_btn)

        h3_btn = QPushButton("H3"); h3_btn.setStyleSheet(btn_style)
        h3_btn.setToolTip("三级标题"); h3_btn.clicked.connect(lambda: self._md_action("### ", line_prefix=True))
        toolbar.addWidget(h3_btn)

        list_btn = QPushButton("- List"); list_btn.setStyleSheet(btn_style)
        list_btn.setToolTip("无序列表"); list_btn.clicked.connect(lambda: self._md_action("- ", line_prefix=True))
        toolbar.addWidget(list_btn)

        table_btn = QPushButton("+ Table"); table_btn.setStyleSheet(btn_style)
        table_btn.setToolTip("插入3列表格"); table_btn.clicked.connect(self._md_insert_table)
        toolbar.addWidget(table_btn)

        toolbar.addStretch()
        editor_layout.addLayout(toolbar)

        self.editor = QTextEdit()
        self.editor.textChanged.connect(lambda: setattr(self, '_md_source', None))
        self.editor.setPlaceholderText("在此编写世界观设定...\n工具栏支持加粗/斜体/标题/列表/表格")
        self.editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e8f0; border-radius: 4px;
                padding: 8px; font-size: 14px; line-height: 1.8;
                font-family: 'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
            }
        """)
        editor_layout.addWidget(self.editor, stretch=1)

        # 自动保存：停止输入 1 秒后自动存盘
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

    def _on_selection_changed(self, current, previous):
        # 保存当前编辑
        self._on_save_current()
        eid = self._get_entry_id(current)
        entry = self.module._find_entry(self.module.entries, eid) if eid else None
        if entry:
            self._current_id = entry.id
            self.editor_title.setText(f"✏ {entry.title}")
            content = entry.content
            self.editor.blockSignals(True)
            if content.strip().startswith("<"):
                self._md_source = content  # HTML 格式
                self.editor.setHtml(content)
            else:
                self._md_source = content  # Markdown 格式，存盘原样保留
                self.editor.setMarkdown(content)
            self.editor.blockSignals(False)
            self.editor.setEnabled(True)
        else:
            self._current_id = None
            self.editor_title.setText("选择条目编辑")
            self.editor.clear()
            self.editor.setEnabled(False)

    def _md_action(self, marker, line_prefix=False):
        """插入 Markdown 标记 → 重渲染。"""
        cursor = self.editor.textCursor()
        pos = cursor.position()
        if line_prefix:
            cursor.movePosition(cursor.MoveOperation.StartOfBlock)
            cursor.insertText(marker)
        elif cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(end)
            cursor.insertText(marker)
            cursor.setPosition(start)
            cursor.insertText(marker)
        else:
            cursor.insertText(marker * 2)
            cursor.setPosition(cursor.position() - len(marker))
        self.editor.setTextCursor(cursor)
        self._rerender_md()

    def _md_insert_table(self):
        """插入 Markdown 表格模板 → 重渲染。"""
        table = "\n| 列A | 列B | 列C |\n|------|------|------|\n|  |  |  |\n"
        cursor = self.editor.textCursor()
        cursor.insertText(table)
        self.editor.setTextCursor(cursor)
        self._rerender_md()

    def _rerender_md(self):
        """用 setMarkdown 重渲染编辑器内容（保留光标位置）。"""
        cursor = self.editor.textCursor()
        pos = cursor.position()
        md = self._get_md_content()
        self.editor.blockSignals(True)
        self.editor.setMarkdown(md)
        # 恢复光标（不超过新文本长度）
        new_len = len(self.editor.toPlainText())
        cursor = self.editor.textCursor()
        cursor.setPosition(min(pos, new_len))
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)

    def _get_md_content(self) -> str:
        """遍历文档块提取 Markdown（处理表格/列表/加粗/斜体，不丢 CJK）。"""
        from PySide6.QtGui import QTextTable, QTextList
        doc = self.editor.document()
        block = doc.begin()
        lines = []
        seen_tables = set()
        prev_empty = False

        while block.isValid():
            text = block.text()
            fmt = block.blockFormat()
            hl = fmt.headingLevel() if hasattr(fmt, 'headingLevel') else 0
            hl = hl or 0

            # 列表项
            lst = block.textList()
            if lst is not None:
                indent = '  ' * (lst.format().indent() if hasattr(lst.format(), 'indent') else 0)
                md_text = self._block_to_md(block)
                lines.append(f'{indent}- {md_text}')
                prev_empty = False
                block = block.next()
                continue

            # 表格：收集所有表格块，合并为 Markdown 表格
            tbl = block.begin() if block.begin() != block.end() else None
            if tbl is not None:
                try:
                    frame = doc.rootFrame()
                    # 搜索当前 block 属于哪个 QTextTable
                    tbl_obj = None
                    for child in frame.childFrames():
                        if isinstance(child, QTextTable):
                            for r in range(child.rows()):
                                for c in range(child.columns()):
                                    cell = child.cellAt(r, c)
                                    if cell.firstPosition() <= block.position() <= cell.lastPosition():
                                        tbl_obj = child
                                        break
                    if tbl_obj is not None and id(tbl_obj) not in seen_tables:
                        seen_tables.add(id(tbl_obj))
                        md_table = self._table_to_md(tbl_obj)
                        if lines and lines[-1] != '':
                            lines.append('')
                        lines.append(md_table)
                        lines.append('')
                        prev_empty = False
                        # 跳到表格后
                        last_cell = tbl_obj.cellAt(tbl_obj.rows() - 1, tbl_obj.columns() - 1)
                        cursor = self.editor.textCursor()
                        cursor.setPosition(last_cell.lastPosition())
                        block = cursor.block().next()
                        continue
                except Exception:
                    pass

            # 标题
            if hl > 0:
                if lines and lines[-1] != '':
                    lines.append('')
                md_text = self._block_to_md(block)
                lines.append('#' * hl + ' ' + md_text)
                lines.append('')
                prev_empty = False
            elif text.strip():
                if prev_empty:
                    lines.append('')
                md_text = self._block_to_md(block)
                lines.append(md_text)
                prev_empty = True
            else:
                if prev_empty:
                    lines.append('')
                    prev_empty = False
            block = block.next()

        while lines and lines[-1] == '':
            lines.pop()
        return '\n'.join(lines) + '\n'

    def _block_to_md(self, block) -> str:
        """将单个 block 的文本转为带内联格式的 Markdown。"""
        text = block.text()
        if not text:
            return text
        # 立即提取格式属性（避免 C++ 对象被 GC）
        from PySide6.QtGui import QFont
        fragments = []
        for f_range in block.textFormats():
            start = f_range.start
            length = f_range.length
            try:
                bold = f_range.format.fontWeight() == QFont.Weight.Bold
                italic = f_range.format.fontItalic()
            except RuntimeError:
                bold = False
                italic = False
            fragments.append((start, length, bold, italic))
        if not fragments:
            return text
        fragments.sort(key=lambda x: x[0])

        result = []
        i = 0
        while i < len(text):
            bold = False
            italic = False
            for start, length, b, it in fragments:
                if start <= i < start + length:
                    bold = b
                    italic = it
                    break
            boundary = len(text)
            for start, length, b, it in fragments:
                if start > i and start < boundary:
                    boundary = start
                if start <= i < start + length:
                    end = start + length
                    if end < boundary:
                        boundary = end
            chunk = text[i:boundary]
            if bold and italic and chunk.strip():
                result.append(f'***{chunk}***')
            elif bold and chunk.strip():
                result.append(f'**{chunk}**')
            elif italic and chunk.strip():
                result.append(f'*{chunk}*')
            else:
                result.append(chunk)
            i = boundary

        return ''.join(result)

    def _table_to_md(self, tbl) -> str:
        """将 QTextTable 转为 Markdown 表格字符串。"""
        rows = tbl.rows()
        cols = tbl.columns()
        md_rows = []
        for r in range(rows):
            cells = []
            for c in range(cols):
                cell = tbl.cellAt(r, c)
                # 提取 cell 内所有 block 的文本
                cell_lines = []
                cell_block = cell.begin()
                while cell_block.isValid() and cell_block.position() < cell.lastPosition() + 1:
                    cell_md = self._block_to_md(cell_block)
                    if cell_md.strip():
                        cell_lines.append(cell_md.strip())
                    cell_block = cell_block.next()
                    if cell_block.position() >= cell.lastPosition():
                        break
                cells.append(' '.join(cell_lines))
            md_rows.append('| ' + ' | '.join(cells) + ' |')
        # 插入分隔行（第 1 行之后）
        if len(md_rows) > 1:
            sep = '|' + '|'.join(['------' for _ in range(cols)]) + '|'
            md_rows.insert(1, sep)
        return '\n'.join(md_rows)

    def _auto_save(self):
        """停止输入 1 秒后自动存盘（仅当正在编辑条目时）。"""
        if self._current_id:
            self._on_save_current()

    def _on_save_current(self):
        if self._current_id:
            if getattr(self, '_md_source', None) is not None:
                # AI 写入的 Markdown，未被手改 → 原样保存
                content = self._md_source
            else:
                # 用户手改过 → 自定义 MD 序列化（表格/加粗/斜体/标题，不丢 CJK）
                content = self._get_md_content()
                self._md_source = content
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
            eid = self._get_entry_id(item)
            if eid:
                new_title, ok = QInputDialog.getText(self, "重命名", "新标题:", text=item.text(0))
                if ok and new_title.strip():
                    self.module.update_entry(eid, title=new_title.strip())
                    self.module.save()
                    self._build_tree()
        elif action == delete_act:
            self._on_delete()
