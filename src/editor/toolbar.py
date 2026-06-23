"""编辑器格式化工具栏。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QTextCharFormat
from PySide6.QtWidgets import QToolBar, QComboBox, QWidgetAction


class EditorToolbar(QToolBar):
    """富文本编辑器配套的格式工具栏。"""

    def __init__(self, editor, parent=None):
        super().__init__("格式化", parent)
        self.editor = editor
        self.setMovable(False)
        self.setIconSize(self.iconSize())
        self.setStyleSheet("QToolBar { padding: 2px 8px; }")
        self._build_toolbar()

    def _build_toolbar(self):
        """构建工具栏按钮。"""

        # ── 文本格式化 ──
        bold_act = QAction("B", self)
        bold_act.setToolTip("加粗 (Ctrl+B)")
        bold_act.setCheckable(True)
        bold_act.triggered.connect(lambda: self.editor.toggle_bold())
        bold_act.setShortcut("Ctrl+B")
        self.addAction(bold_act)
        self.addAction("I", lambda: self.editor.toggle_italic())
        self.addAction("U", lambda: self.editor.toggle_underline())
        self.actions()[-1].setShortcut("Ctrl+I")
        self.actions()[-2].setShortcut("Ctrl+U")

        self.addSeparator()

        # ── 标题 ──
        self.addAction("H1", lambda: self.editor.set_heading(1))
        self.addAction("H2", lambda: self.editor.set_heading(2))
        self.addAction("H3", lambda: self.editor.set_heading(3))
        self.addAction("P", lambda: self.editor.set_heading(0))

        self.addSeparator()

        # ── 列表 ──
        self.addAction("•", lambda: self.editor.insert_bullet_list())
        self.addAction("1.", lambda: self.editor.insert_ordered_list())
        self.addAction("❝", lambda: self.editor.insert_blockquote())
