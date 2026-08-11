"""富文本编辑器组件——支持正文标注高亮显示。"""

import re as _re

from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QBrush
from PySide6.QtWidgets import QTextEdit

from .modules.ai_assistant.markdown_render import markdown_to_html as _md_to_html


_HIGHLIGHT_COLOR = QColor("#E8F5E9")  # 浅绿背景(批注高亮,固定语义色)
_UNDERLINE_COLOR = QColor("#4CAF50")  # 绿色下划线(固定语义色)


class EditorWidget(QTextEdit):
    """富文本编辑器，支持 HTML 读写、格式化、正文标注。"""

    chapter_modified = Signal()
    content_synced = Signal(str, str)  # (chapter_path, md) 给浮动窗口同步用
    annotation_requested = Signal(str, str)  # (highlight_text, suggestion) 手动添加批注
    annotations_changed = Signal()  # 批注集合变化(边条/面板刷新用)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_editor()
        self._current_chapter_path = None
        self._modified = False
        self._annotations = []  # 当前章节的批注列表
        self._rendered_ranges = []  # 上一轮实际渲染的高亮范围(渲染前清除用)
        self._syncing = False  # 防止同步循环

    def _setup_editor(self):
        self.setAcceptRichText(True)
        font = QFont()
        font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Songti SC", "Noto Serif CJK SC", "serif"])
        font.setPointSize(14)
        self.setFont(font)
        self.setStyleSheet("""
            QTextEdit {
                padding: 20px 30px;
                border: none;
                line-height: 1.8;
            }
        """)
        self.setTabStopDistance(32)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # Ctrl+滚轮缩放：在 viewport 上装事件过滤器
        self.viewport().installEventFilter(self)
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        self._modified = True
        self.chapter_modified.emit()

    def keyPressEvent(self, event):
        """Tab/Shift+Tab 缩进处理（全角空格，中文标准）。"""
        _INDENT = "　　"  # 2 个全角空格 = 中文首行缩进
        if event.key() == Qt.Key.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                start = cursor.selectionStart()
                end = cursor.selectionEnd()
                cursor.setPosition(start)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                begin_block = cursor.block().blockNumber()
                cursor.setPosition(end)
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                end_block = cursor.block().blockNumber()
                cursor.beginEditBlock()
                for _ in range(begin_block, end_block + 1):
                    cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                    cursor.insertText(_INDENT)
                    cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
                cursor.endEditBlock()
                return
            else:
                # 仅当光标在行首或本行只有空白时插入缩进
                block = cursor.block()
                col = cursor.columnNumber()
                if col == 0 or not block.text()[:col].strip():
                    cursor.insertText(_INDENT)
                    return
        elif event.key() == Qt.Key.Key_Backtab:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text()
            if text.startswith(_INDENT):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                cursor.movePosition(QTextCursor.MoveOperation.Right,
                                   QTextCursor.MoveMode.KeepAnchor, 2)
                cursor.removeSelectedText()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, ev):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.Type.Wheel:
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = ev.angleDelta().y()
                font = self.currentFont()
                size = font.pointSize()
                if size <= 0:
                    size = 14
                size += 2 if delta > 0 else -2
                size = max(8, min(48, size))
                font.setPointSize(size)
                self.setFont(font)
                self.document().setDefaultFont(font)
                print(f"[Zoom] size={size}")
                return True
        return super().eventFilter(obj, ev)

    def load_html(self, html: str):
        self.blockSignals(True)
        self.setHtml(html)
        self._modified = False
        self.blockSignals(False)

    def load_markdown(self, md: str):
        """加载 Markdown → HTML（自有渲染器，保持字体/缩进一致）。"""
        self.blockSignals(True)
        stripped = md.strip()
        if stripped.startswith("<"):
            # 遗留 HTML 格式（旧文件或导入的 HTML）
            self.setHtml(md)
        else:
            body = _md_to_html(md)
            html = '\n'.join([
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
                '"http://www.w3.org/TR/REC-html40/strict.dtd">',
                '<html><head><meta name="qrichtext" content="1" />'
                '<meta charset="utf-8" />'
                '<style type="text/css">',
                'p, li { white-space: pre-wrap; }',
                'h1 { font-size: 17pt; font-weight: 700; margin-top: 0; margin-bottom: 8px; }',
                'h2 { font-size: 15pt; font-weight: 700; }',
                'h3 { font-size: 14pt; font-weight: 700; }',
                'body { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "sans-serif";'
                ' font-weight: 400; }',
                '</style></head>',
                f'<body>{body}</body></html>',
            ])
            self.setHtml(html)
        self._modified = False
        self.blockSignals(False)

    def get_html(self) -> str:
        return self.toHtml()

    def get_markdown(self) -> str:
        """将编辑器内容导出为 Markdown（遍历文档块，不丢 CJK 文本）。"""
        from PySide6.QtGui import QTextBlockFormat
        doc = self.document()
        block = doc.begin()
        result = []
        prev_was_text = False

        while block.isValid():
            text = block.text()
            fmt = block.blockFormat()

            # 检测标题（QTextBlockFormat 的 headingLevel 属性）
            hl = fmt.property(int(QTextBlockFormat.HeadingLevel)) if hasattr(
                QTextBlockFormat, 'HeadingLevel') else None
            hl = hl or 0

            if hl > 0:
                if prev_was_text:
                    result.append('')
                result.append(f'{"#" * hl} {text.strip()}')
                result.append('')
                prev_was_text = False
            elif text.strip():
                # 列表检测
                is_list = fmt.property(int(QTextBlockFormat.IsListFormat)) if hasattr(
                    QTextBlockFormat, 'IsListFormat') else None
                if is_list:
                    if prev_was_text:
                        result.append('')
                    result.append(f'- {text.strip()}')
                    prev_was_text = False
                else:
                    if prev_was_text:
                        result.append('')
                    result.append(text)
                    prev_was_text = True
            else:
                # 空块：如果之前有文本，插入空行分隔
                if prev_was_text:
                    result.append('')
                    prev_was_text = False

            block = block.next()

        while result and result[-1] == '':
            result.pop()
        return '\n'.join(result) + '\n'

    def get_plain_text(self) -> str:
        return self.toPlainText()

    def set_current_chapter(self, path: str):
        self._current_chapter_path = path
        self._modified = False

    def current_chapter_path(self) -> str:
        return self._current_chapter_path

    def is_modified(self) -> bool:
        return self._modified

    def mark_saved(self):
        self._modified = False

    def apply_sync(self, md: str):
        """接收其他窗口的同步内容（Markdown 格式）。"""
        if self._syncing:
            return
        self._syncing = True
        self.blockSignals(True)
        self.setMarkdown(md)
        self.blockSignals(False)
        self._syncing = False

    def contextMenuEvent(self, event):
        """右键菜单(汉化):剪切/复制/粘贴/全选 + 选中文本时「添加批注」。"""
        from PySide6.QtWidgets import QMenu, QInputDialog, QMessageBox
        menu = QMenu(self)
        cut = menu.addAction("剪切")
        copy = menu.addAction("复制")
        paste = menu.addAction("粘贴")
        menu.addSeparator()
        select_all = menu.addAction("全选")
        has_sel = self.textCursor().hasSelection()
        cut.setEnabled(has_sel)
        copy.setEnabled(has_sel)
        paste.setEnabled(self.canPaste())
        add_ann = None
        if has_sel:
            menu.addSeparator()
            add_ann = menu.addAction("📌 添加批注")
            add_ann.setToolTip("为选中文本添加一条批注(存于 .annotations.json,不修改原文)")
        chosen = menu.exec(event.globalPos())
        if chosen is None:
            return  # 菜单取消(Esc/点外部)
        if chosen == cut:
            self.cut()
        elif chosen == copy:
            self.copy()
        elif chosen == paste:
            self.paste()
        elif chosen == select_all:
            self.selectAll()
        elif chosen == add_ann:
            sel = self.textCursor().selectedText()
            if "\u2029" in sel or "\n" in sel:
                QMessageBox.information(
                    self, "添加批注",
                    "请选择同一段落内的文本(跨段选区暂不支持批注)。")
                return
            suggestion, ok = QInputDialog.getMultiLineText(
                self, "添加批注", f"对以下文本的批注:\n「{sel[:60]}」\n\n建议/说明:", "")
            if ok and suggestion.strip():
                self.annotation_requested.emit(sel, suggestion.strip())

    # ── 批注标注渲染 ──

    def set_annotations(self, annotations: list):
        """设置当前章节的批注列表并渲染。"""
        self._annotations = annotations
        self._render_annotations()
        self.annotations_changed.emit()

    def _render_annotations(self):
        """在正文中渲染批注高亮(blockSignals 防误标 modified/实时写盘)。"""
        self.blockSignals(True)
        try:
            text = self.toPlainText()
            # 先清除上一轮批注高亮(范围可能已变化/批注已忽略/删除)。
            # 仅清除背景/下划线,不触碰用户格式(粗体/标题字号等)
            for s, e in self._rendered_ranges:
                if e <= s or s < 0:
                    continue
                cur = self.textCursor()
                cur.setPosition(min(s, len(text)))
                cur.setPosition(min(e, len(text)), QTextCursor.MoveMode.KeepAnchor)
                clear_fmt = QTextCharFormat()
                clear_fmt.setBackground(QBrush(Qt.BrushStyle.NoBrush))
                clear_fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.NoUnderline)
                cur.mergeCharFormat(clear_fmt)
            self._rendered_ranges = []
            if not self._annotations:
                return

            # 获取纯文本，逐个批注打高亮
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            for ann in self._annotations:
                if ann.target_type != "chapter" or ann.start_pos < 0:
                    continue
                if ann.status == "ignored":
                    continue  # 已忽略的批注不渲染高亮

                # 在纯文本中定位
                if ann.start_pos >= len(text):
                    continue

                start = ann.start_pos
                end = min(ann.end_pos, len(text)) if ann.end_pos > start else start + len(ann.highlight_text)
                if end > len(text):
                    end = len(text)
                if end <= start:
                    continue

                # 设置高亮格式
                fmt = QTextCharFormat()
                fmt.setBackground(_HIGHLIGHT_COLOR)
                fmt.setUnderlineColor(_UNDERLINE_COLOR)
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                # 悬停提示:状态 + 建议(Word 式悬停查看批注内容)
                import html as _html
                status_tag = {"pending": "🟡 待处理", "accepted": "🟢 已采纳",
                              "ignored": "⚪ 已忽略"}.get(ann.status, "🟡 待处理")
                # suggestion 转义后进 tooltip,防止 AI 文本按富文本解析注入
                safe_suggestion = _html.escape(ann.suggestion[:300])
                fmt.setToolTip(f"📌 {status_tag}\n{safe_suggestion}")

                # 定位到起始位置并应用格式
                cursor.setPosition(start)  # MoveAnchor 属 MoveMode,setPosition 默认即 MoveAnchor
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                cursor.mergeCharFormat(fmt)
                self._rendered_ranges.append((start, end))
        finally:
            self.blockSignals(False)

    def _find_text_position(self, search_text: str, plain_text: str) -> tuple[int, int]:
        """在纯文本中搜索原文片段，返回 (start, end)。"""
        idx = plain_text.find(search_text)
        if idx >= 0:
            return (idx, idx + len(search_text))
        # 尝试去除标点后搜索
        clean = _re.sub('[，。！？、；：""''「」【】（）]', '', search_text)
        plain_clean = _re.sub('[，。！？、；：""''「」【】（）]', '', plain_text)
        idx = plain_clean.find(clean)
        if idx >= 0:
            return (idx, idx + len(clean))
        return (-1, -1)

    # ── 格式化工具 ──

    def toggle_bold(self):
        self.setFontWeight(QFont.Weight.Bold if self.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)

    def toggle_italic(self):
        self.setFontItalic(not self.fontItalic())

    def toggle_underline(self):
        self.setFontUnderline(not self.fontUnderline())

    def set_heading(self, level: int):
        if level == 0:
            from PySide6.QtGui import QTextBlockFormat
            cursor = self.textCursor()
            bfmt = QTextBlockFormat()
            cursor.setBlockFormat(bfmt)
            font = self.currentCharFormat().font()
            font.setPointSize(14)
            font.setBold(False)
            self.setCurrentFont(font)
        elif level == 1:
            self.setFontPointSize(24)
            self.setFontWeight(QFont.Weight.Bold)
        elif level == 2:
            self.setFontPointSize(20)
            self.setFontWeight(QFont.Weight.Bold)
        elif level == 3:
            self.setFontPointSize(17)
            self.setFontWeight(QFont.Weight.Bold)

    def insert_bullet_list(self):
        cursor = self.textCursor()
        from PySide6.QtGui import QTextListFormat
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDisc)
        cursor.createList(fmt)

    def insert_ordered_list(self):
        cursor = self.textCursor()
        from PySide6.QtGui import QTextListFormat
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDecimal)
        cursor.createList(fmt)

    def insert_blockquote(self):
        cursor = self.textCursor()
        from PySide6.QtGui import QTextBlockFormat
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(40)
        cursor.setBlockFormat(fmt)
