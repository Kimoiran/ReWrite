"""QDockWidget 行为工具:浮动窗口关闭时自动停靠回原位。"""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QDockWidget


class DockCloseReturnFilter(QObject):
    """事件过滤器:QDockWidget 关闭前先停靠回原 dock 位置。

    浮动(detach)窗口点击关闭时,先 setFloating(False) 停靠回原位,
    再放行事件(默认关闭行为 = 隐藏)。避免面板保持浮动状态——
    重新打开时位置错乱、需重启才能恢复。放行而非吞掉事件,
    确保子类 closeEvent(如世界观编辑器的保存兜底)仍能执行。
    """

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.Close
                and isinstance(obj, QDockWidget)
                and obj.isFloating()):
            obj.setFloating(False)  # 停靠回 dock 位置,再按默认关闭(隐藏)
        return super().eventFilter(obj, event)
