"""品牌过渡动画:ReWrite × Kimoiran 标识卡 + 窗口柔性缩放转场。

- BrandSplash:品牌标识卡(icon + ReWrite + by Kimoiran),
  play_in 淡入并放大图标,play_out 淡出(仅启动时使用);
- collapse_to_center:窗口快照柔性缩小到屏幕中心小矩形并淡出(完成回调);
- expand_from_center:窗口快照从中心小矩形柔性放大到原尺寸并淡入。

柔性 = 平滑缓动(QEasingCurve.OutQuart/InQuart,快速起落、收尾柔和,无回弹过冲),
快照 = 离屏渲染位图缩放(动画期间不触发布局重算,不卡顿)。
"""

from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, Qt, QTimer,
                            QVariantAnimation, QRect)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .theme import Color

_ASSET_ICON = (Path(__file__).resolve().parent.parent.parent
               / "assets" / "icon.ico")


def _anim(widget: QWidget, prop: bytes, start, end, duration: int,
          easing, parent: QWidget) -> QPropertyAnimation:
    a = QPropertyAnimation(widget, prop)
    a.setDuration(duration)
    a.setStartValue(start)
    a.setEndValue(end)
    a.setEasingCurve(easing)
    a.setParent(parent)  # 防 GC
    a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return a


def _snapshot(widget: QWidget, rect) -> QLabel:
    """把窗口离屏渲染为位图,放进无边框置顶 QLabel(快照窗口)。"""
    from PySide6.QtGui import QPixmap
    pix = QPixmap(rect.width(), rect.height())
    widget.render(pix)
    snap = QLabel()
    snap.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    snap.setPixmap(pix)
    snap.setGeometry(rect)
    snap.show()
    return snap


def _center_rect(widget: QWidget, size: int) -> QRect:
    """widget 所在屏幕中心的正方形矩形。"""
    screen = widget.screen()
    avail = (screen.availableGeometry() if screen
             else QApplication.primaryScreen().availableGeometry())
    return QRect(avail.center().x() - size // 2,
                 avail.center().y() - size // 2,
                 size, size)


def collapse_to_center(widget: QWidget, size: int = 64,
                       duration: int = 240, on_finished=None):
    """窗口快照柔和缩小到屏幕中心小矩形并淡出(InQuart 平滑收尾,无回弹)。

    完成后回调(可切换页面)。返回快照,调用方可持有以在中断时主动关闭。
    """
    start_rect = widget.frameGeometry()
    if start_rect.width() < 50 or start_rect.height() < 50:
        on_finished and on_finished()
        return None
    end_rect = _center_rect(widget, size)
    # 先隐藏真实窗口再建快照,避免两窗口短暂重叠闪烁
    widget.hide()
    snap = _snapshot(widget, start_rect)
    a = _anim(snap, b"geometry", start_rect, end_rect, duration,
              QEasingCurve.Type.InQuart, widget)
    a_op = _anim(snap, b"windowOpacity", 1.0, 0.0, duration,
                 QEasingCurve.Type.InQuart, widget)

    def _done():
        for anim in (a, a_op):
            try:
                anim.stop()
            except RuntimeError:
                pass
        try:
            snap.close()
            snap.deleteLater()
        except RuntimeError:
            pass
        if on_finished:
            on_finished()

    a.finished.connect(_done)
    return snap


def expand_from_center(widget: QWidget, size: int = 64,
                       duration: int = 280, on_finished=None):
    """窗口快照从中心小矩形柔和放大到原尺寸并淡入(OutQuart 平滑收尾,无回弹)。"""
    target_rect = widget.frameGeometry()
    avail = (widget.screen() if widget.screen()
             else QApplication.primaryScreen()).availableGeometry()
    # 窗口尚未显示时 frameGeometry 可能无效,退回可用几何并居中
    if target_rect.width() < 50 or target_rect.height() < 50:
        target_rect = QRect(avail.x(), avail.y(),
                            max(target_rect.width(), 1200),
                            max(target_rect.height(), 800))
    if (target_rect.x() == 0 and target_rect.y() == 0) \
            or not avail.intersects(target_rect):
        target_rect.moveCenter(avail.center())

    start_rect = _center_rect(widget, size)
    # render 成功后再置标志(异常时不会残留跳过状态)
    widget.setGeometry(target_rect)
    snap = _snapshot(widget, target_rect)
    widget.hide()
    snap.setGeometry(start_rect)
    # 张开动画自驱透明度,跳过目标窗口自身的 fade_in(避免冲突)
    widget._skip_fade_in = True
    widget._faded_in = True
    a_geo = _anim(snap, b"geometry", start_rect, target_rect, duration,
                  QEasingCurve.Type.OutQuart, widget)
    a_op = _anim(snap, b"windowOpacity", 0.0, 1.0, duration,
                 QEasingCurve.Type.OutQuart, widget)

    def _done():
        for anim in (a_geo, a_op):
            try:
                anim.stop()
            except RuntimeError:
                pass
        # 先显示真实窗口再关快照,避免切换间隙的空白闪烁;
        # show 期间 _skip_fade_in 仍为 True(showEvent 据此跳过 fade_in)
        widget.show()
        widget._skip_fade_in = False
        try:
            snap.close()
            snap.deleteLater()
        except RuntimeError:
            pass
        if on_finished:
            on_finished()

    a_geo.finished.connect(_done)
    return snap


class BrandSplash(QWidget):
    """品牌标识卡:ReWrite × Kimoiran,居中卡片,图标 + 文字。

    - play_in(): 淡入 + 图标放大(150ms)
    - 自动停留 hold_ms 后调 on_hidden(默认自动关闭)
    """

    def __init__(self, parent=None, on_hidden=None):
        super().__init__(parent)
        self._on_hidden = on_hidden
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # 小卡片(非全屏):居中 340×400,品牌感
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else self.geometry()
        self.setGeometry(avail.center().x() - 170, avail.center().y() - 200,
                         340, 400)
        self._icon_size = 88
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QFrame
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(self)
        card.setObjectName("brandCard")
        card.setStyleSheet(
            f"#brandCard {{ background-color: {Color.SURFACE};"
            f" border: 1px solid {Color.BORDER_LIGHT}; border-radius: 18px; }}")
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 32, 28, 32)
        self.icon_label = QLabel(card)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(self._pixmap(self._icon_size))
        layout.addWidget(self.icon_label)
        title = QLabel("ReWrite", card)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 28px; font-weight: 700; color: {Color.PRIMARY};"
            " background: transparent; border: none;")
        layout.addWidget(title)
        sub = QLabel("by Kimoiran", card)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"font-size: 13px; color: {Color.TEXT_HINT};"
            " background: transparent; border: none;")
        layout.addWidget(sub)
        outer.addWidget(card)

    def _pixmap(self, size: int):
        if _ASSET_ICON.exists():
            return QIcon(str(_ASSET_ICON)).pixmap(size, size)
        return QIcon().pixmap(size, size)

    def play_in(self, hold_ms: int = 600):
        """淡入 + 图标放大;停留 hold_ms 后自动关闭(或调 on_hidden)。"""
        self.show()
        self.setWindowOpacity(0.0)
        _anim(self, b"windowOpacity", 0.0, 1.0, 150,
              QEasingCurve.Type.OutCubic, self)
        grow = QVariantAnimation(self)
        grow.setDuration(150)
        grow.setStartValue(64)
        grow.setEndValue(self._icon_size)
        grow.setEasingCurve(QEasingCurve.Type.OutCubic)
        grow.valueChanged.connect(
            lambda v: self.icon_label.setPixmap(self._pixmap(int(v))))
        grow.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)

        def _finish():
            self.play_out()
            if self._on_hidden:
                self._on_hidden()

        QTimer.singleShot(150 + hold_ms, _finish)

    def play_out(self, duration: int = 200):
        """淡出并关闭(幂等:重复调用不叠加动画)。"""
        if getattr(self, "_out_started", False):
            return
        self._out_started = True
        a = _anim(self, b"windowOpacity", self.windowOpacity(), 0.0,
                  duration, QEasingCurve.Type.InCubic, self)
        a.finished.connect(self.close)
