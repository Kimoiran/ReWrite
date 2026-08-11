"""批注边条 — 编辑器右侧显示批注位置标记(Word 式),点击跳转。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QTextCursor
from PySide6.QtWidgets import QWidget

from ...ui.theme import Color

# 状态色(与列表/高亮一致的语义色)
_STATUS_COLORS = {
    "pending": Color.WARNING,
    "accepted": Color.SUCCESS,
    "ignored": Color.TEXT_HINT,
}


class AnnotationGutter(QWidget):
    """编辑器右侧批注标记条:圆点表示批注位置,点击跳转到对应原文。"""

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._marks = []  # [(视口y, annotation), ...]
        self.setFixedWidth(14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("批注位置(点击跳转)")
        # 编辑器滚动/内容变化时刷新标记
        editor.verticalScrollBar().valueChanged.connect(self._update_marks)
        editor.textChanged.connect(self._update_marks)

    def _update_marks(self):
        self._marks = []
        anns = getattr(self._editor, "_annotations", []) or []
        doc = self._editor.document()
        if not anns or doc is None or doc.isEmpty():
            self.update()
            return
        max_pos = max(0, doc.characterCount() - 1)
        for a in anns:
            if a.target_type != "chapter" or a.start_pos < 0:
                continue
            c = QTextCursor(doc)
            c.setPosition(min(a.start_pos, max_pos))
            rect = self._editor.cursorRect(c)  # 视口坐标,随滚动更新
            self._marks.append((max(0, rect.top()), a))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
        for y, a in self._marks:
            color = _STATUS_COLORS.get(a.status, Color.WARNING)
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(3, y + 2, 8, 8)
        p.end()

    def mousePressEvent(self, event):
        if self._marks:
            target = min(self._marks, key=lambda m: abs(m[0] - event.position().y()))
            y, a = target
            doc = self._editor.document()
            if doc is not None:
                c = QTextCursor(doc)
                c.setPosition(min(max(0, a.start_pos), max(0, doc.characterCount() - 1)))
                self._editor.setTextCursor(c)
                self._editor.ensureCursorVisible()
                self._editor.setFocus()
        super().mousePressEvent(event)
