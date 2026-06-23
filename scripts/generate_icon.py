"""生成 ReWrite 应用图标。"""
import sys, os
from pathlib import Path

# 需要 QApplication 才能渲染 QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap, QPainterPath, QLinearGradient
from PySide6.QtCore import Qt, QRect, QPoint

app = QApplication(sys.argv)

p = QPixmap(256, 256)
p.fill(Qt.GlobalColor.transparent)

painter = QPainter(p)
painter.setRenderHint(QPainter.RenderHint.Antialiasing)

# 青蓝渐变圆角方块
path = QPainterPath()
r = QRect(8, 8, 240, 240)
path.addRoundedRect(r, 48, 48)
painter.setPen(Qt.PenStyle.NoPen)

grad = QLinearGradient(0, 0, 256, 256)
grad.setColorAt(0.0, QColor("#00BCD4"))
grad.setColorAt(1.0, QColor("#2196F3"))
painter.setBrush(QBrush(grad))
painter.drawPath(path)

# 白色 R 字母
painter.setPen(QPen(QColor(255, 255, 255), 1))
painter.setFont(QFont("Segoe UI", 130, QFont.Weight.Bold))
painter.drawText(QRect(0, 15, 256, 200), Qt.AlignmentFlag.AlignCenter, "R")

# 装饰点
painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
painter.setPen(Qt.PenStyle.NoPen)
painter.drawEllipse(QPoint(195, 68), 8, 8)
painter.drawEllipse(QPoint(210, 83), 6, 6)

painter.end()

out = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
p.save(str(out))
print(f"Icon saved: {out} ({out.stat().st_size} bytes)")
