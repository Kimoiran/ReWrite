"""富文本编辑器组件——基于 QTextEdit。"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit, QWidget


class EditorWidget(QTextEdit):
    """富文本编辑器，支持 HTML 内容的读写和格式化。"""

    chapter_modified = Signal()      # 内容变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_editor()
        self._current_chapter_path = None
        self._modified = False

    def _setup_editor(self):
        """初始化编辑器样式和设置。"""
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
                font-size: 14px;
            }
        """)

        self.setTabStopDistance(32)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setTextInteractionFlags(
            self.textInteractionFlags() |
            self.textInteractionFlags()  # keep defaults
        )

        # 监听内容变化
        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        """内容变化时标记修改。不发射额外信号，避免窗口弹跳。"""
        self._modified = True
        self.chapter_modified.emit()

    def load_html(self, html: str):
        """加载 HTML 内容到编辑器（不触发同步）。"""
        self.blockSignals(True)
        self._syncing = True
        self.setHtml(html)
        self._modified = False
        self._syncing = False
        self.blockSignals(False)

    def get_html(self) -> str:
        """获取当前内容的 HTML。"""
        return self.toHtml()

    def get_plain_text(self) -> str:
        """获取纯文本内容。"""
        return self.toPlainText()

    def set_current_chapter(self, path: str):
        """记录当前打开的章节路径。"""
        self._current_chapter_path = path
        self._modified = False

    def current_chapter_path(self) -> str:
        """获取当前章节路径。"""
        return self._current_chapter_path

    def is_modified(self) -> bool:
        """内容是否已修改未保存。"""
        return self._modified

    def mark_saved(self):
        """标记为已保存状态。"""
        self._modified = False

    def apply_sync(self, html: str):
        """从其他窗口接收同步内容（不触发信号循环）。"""
        if self._syncing:
            return
        self._syncing = True
        self.blockSignals(True)
        self.setHtml(html)
        self.blockSignals(False)
        self._syncing = False

    # ── 格式化快捷方法 ──

    def toggle_bold(self):
        self.setFontWeight(
            QFont.Weight.Bold if self.fontWeight() != QFont.Weight.Bold
            else QFont.Weight.Normal
        )

    def toggle_italic(self):
        self.setFontItalic(not self.fontItalic())

    def toggle_underline(self):
        self.setFontUnderline(not self.fontUnderline())

    def set_heading(self, level: int):
        """设置标题级别（1-3），0 为普通段落。"""
        cursor = self.textCursor()
        from PySide6.QtGui import QTextBlockFormat
        fmt = QTextBlockFormat()

        if level == 0:
            # 普通段落
            from PySide6.QtGui import QTextBlockFormat as TBF
            bfmt = TBF()
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
        """插入无序列表。"""
        cursor = self.textCursor()
        from PySide6.QtGui import QTextListFormat
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDisc)
        cursor.createList(fmt)

    def insert_ordered_list(self):
        """插入有序列表。"""
        cursor = self.textCursor()
        from PySide6.QtGui import QTextListFormat
        fmt = QTextListFormat()
        fmt.setStyle(QTextListFormat.Style.ListDecimal)
        cursor.createList(fmt)

    def insert_blockquote(self):
        """插入引用块。"""
        cursor = self.textCursor()
        from PySide6.QtGui import QTextBlockFormat
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(40)
        cursor.setBlockFormat(fmt)
