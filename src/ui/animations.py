"""窗口过渡动画:淡入/淡出(透明度动画,天然适配任意主题)。

实现说明:
- 使用 QPropertyAnimation 驱动 windowOpacity(Windows 对 frameless 窗口同样生效),
  配合轻微位移制造"上浮/下沉"的流畅感;
- 动画对象 setParent(widget) 防 GC,DeleteWhenStopped 自动清理;
- fade_out 提供 on_finished 回调,供"动画结束后真正关闭窗口"等场景使用;
- fade_out 会先停止同窗口未完成的位移动画,避免淡出/隐藏期间窗口被"拉回"。
"""

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget


def _start(anim: QPropertyAnimation, widget: QWidget) -> QPropertyAnimation:
    anim.setParent(widget)  # 持有引用,防 GC 中断动画
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_in(widget: QWidget, duration: int = 280, shift: int = 16):
    """窗口淡入 + 轻微上移滑动(OutCubic,轻快自然)。返回动画元组供测试。"""
    target_pos = widget.pos()
    if shift:
        widget.move(target_pos.x(), target_pos.y() + shift)

    widget.setWindowOpacity(0.0)
    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    _start(anim, widget)

    if shift:
        anim2 = QPropertyAnimation(widget, b"pos")
        anim2.setDuration(duration)
        anim2.setStartValue(widget.pos())
        anim2.setEndValue(target_pos)
        anim2.setEasingCurve(QEasingCurve.Type.OutCubic)
        _start(anim2, widget)
        widget._pos_anim = anim2
        # 动画完成即清理引用:DeleteWhenStopped 会删除 C++ 对象,
        # 不及时清理会导致 fade_out 访问悬空引用抛 RuntimeError
        anim2.finished.connect(lambda w=widget: setattr(w, "_pos_anim", None))
        return (anim, anim2)
    return (anim,)


def fade_out(widget: QWidget, duration: int = 200, on_finished=None):
    """窗口淡出(InCubic,下沉感)。结束时可选执行回调(如真正关闭窗口)。"""
    # 停止未完成的位移动画,避免淡出/隐藏期间窗口被拉回原位
    pos_anim = getattr(widget, "_pos_anim", None)
    if (pos_anim is not None
            and pos_anim.state() == QAbstractAnimation.State.Running):
        pos_anim.stop()

    anim = QPropertyAnimation(widget, b"windowOpacity")
    anim.setDuration(duration)
    anim.setStartValue(widget.windowOpacity())
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)
    if on_finished is not None:
        anim.finished.connect(on_finished)
    _start(anim, widget)
    return anim
