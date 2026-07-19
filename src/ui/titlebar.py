"""自定义无边框标题栏。"""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class WinButton(QPushButton):
    """Windows 风格标题栏按钮：46x30 矩形，黑色图标，悬停有背景色。"""

    def __init__(self, symbol, hover_color="#e0e0e0", close=False, parent=None):
        super().__init__(parent)
        self._hover = hover_color
        self._sym = symbol
        self._close = close
        self.setFixedSize(46, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: none; background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_hover = self.underMouse()
        if is_hover:
            p.fillRect(self.rect(), QColor(self._hover))
        icon_color = "#ffffff" if (is_hover and self._close) else "#1a1a1a"
        p.setPen(QPen(QColor(icon_color), 1))
        f = QFont()
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._sym)


class TitleBar(QWidget):
    close_requested = Signal()
    minimize_requested = Signal()
    maximize_requested = Signal()

    def __init__(self, title="ReWrite", parent=None):
        super().__init__(parent)
        self._pressing = False
        self._drag_start = QPoint()
        self._maximized = False
        self.setFixedHeight(38)
        self.setStyleSheet("TitleBar { background-color: #ffffff; border-bottom: 1px solid #e0e8f0; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)

        icon = QLabel("✍")
        icon.setStyleSheet("font-size: 15px; border: none; color: #2196F3;")
        layout.addWidget(icon)
        layout.addSpacing(6)

        self.title_label = QLabel(title)
        f = QFont()
        f.setPointSize(11)
        self.title_label.setFont(f)
        self.title_label.setStyleSheet("color: #1a2332; border: none;")
        layout.addWidget(self.title_label)
        layout.addStretch()

        self.min_btn = WinButton("─")
        self.max_btn = WinButton("□")
        self.close_btn = WinButton("✕", hover_color="#e81123", close=True)

        m = QHBoxLayout()
        m.setSpacing(0)
        m.addWidget(self.min_btn)
        m.addWidget(self.max_btn)
        m.addWidget(self.close_btn)
        layout.addLayout(m)

        self.close_btn.clicked.connect(self.close_requested.emit)
        self.min_btn.clicked.connect(self.minimize_requested.emit)
        self.max_btn.clicked.connect(self.maximize_requested.emit)

    def set_title(self, text):
        self.title_label.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressing = True
            self._drag_start = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pressing and not self._maximized:
            w = self.window()
            delta = event.globalPosition().toPoint() - self._drag_start
            if w.pos().y() + delta.y() <= 0:
                w.showMaximized()
                self._maximized = True
            else:
                w.move(w.pos() + delta)
            self._drag_start = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressing = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)


def _fix_taskbar_icon(window):
    """强制 Windows 为 frameless 窗口正确显示任务栏图标。
    三步：AppUserModelID / WS_EX_APPWINDOW / WM_SETICON（大+小图标）。"""
    try:
        import ctypes
        from pathlib import Path

        hwnd = int(window.winId())
        if not hwnd:
            return

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        # 0. 确保 AppUserModelID（影响任务栏图标分组）
        try:
            shell32.SetCurrentProcessExplicitAppUserModelID("Kimoiran.ReWrite")
        except Exception:
            pass

        # 1. WS_EX_APPWINDOW + WS_SYSMENU — 恢复系统菜单和图标支持
        GWL_EXSTYLE = -20
        GWL_STYLE = -16
        WS_EX_APPWINDOW = 0x40000
        WS_SYSMENU = 0x80000
        try:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_APPWINDOW)
            user32.SetWindowLongW(hwnd, GWL_STYLE,
                user32.GetWindowLongW(hwnd, GWL_STYLE) | WS_SYSMENU)
        except Exception:
            pass

        # 2. WM_SETICON — 直接绕过 Qt 设 Windows 原生图标
        ico = Path(__file__).resolve().parent.parent.parent / "assets" / "icon.ico"
        if ico.exists():
            hicon_small = user32.LoadImageW(0, str(ico), 1, 16, 16, 0x10)
            hicon_big = user32.LoadImageW(0, str(ico), 1, 32, 32, 0x10)
            WM_SETICON = 0x80
            ICON_BIG = 1
            ICON_SMALL = 0
            if hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            if hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
    except Exception:
        pass


def make_frameless(window):
    """在构造函数最开头调用：设置无边框标志。"""
    flags = window.windowFlags()
    window.setWindowFlags(flags | Qt.WindowType.FramelessWindowHint)
    # FramelessWindowHint 会导致 Windows 任务栏图标变默认，需在 show 后强制修复
    window._need_icon_fix = True


def attach_title_bar(window, title=None):
    """在窗口布局完成后调用：创建并附加 TitleBar。
    注意：调用前必须已在 __init__ 开头调过 make_frameless()。"""
    t = title or window.windowTitle() or "ReWrite"
    bar = TitleBar(t, window)
    window._title_bar = bar

    if hasattr(window, 'setMenuWidget'):
        window.setMenuWidget(bar)
    else:
        # QWidget — 插入布局最顶部
        old = window.layout()
        if old:
            new = QVBoxLayout(window)
            new.setContentsMargins(0, 0, 0, 0)
            new.setSpacing(0)
            new.addWidget(bar)
            new.addLayout(old)

    def toggle():
        if window.isMaximized():
            window.showNormal()
            bar._maximized = False
        else:
            window.showMaximized()
            bar._maximized = True

    bar.close_requested.connect(window.close)
    bar.minimize_requested.connect(window.showMinimized)
    bar.maximize_requested.connect(toggle)

    return bar
