"""作品卡片组件。"""

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QCursor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QMenu,
)

from ..storage.meta import WorkMeta, type_to_name, module_to_name
from ..utils.stats import format_word_count


class WorkCard(QFrame):
    """作品卡片，显示在启动器网格中。"""

    clicked = Signal(str)  # 作品目录名
    delete_requested = Signal(str)  # 作品目录名

    CARD_WIDTH = 200
    CARD_HEIGHT = 240

    def __init__(self, meta: WorkMeta, dir_name: str, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.dir_name = dir_name
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(self.meta.title)

        self.setStyleSheet("""
            WorkCard {
                background-color: #ffffff;
                border-radius: 12px;
                border: none;
            }
            WorkCard:hover {
                border: 2px solid #2196F3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 封面色条
        color_bar = QFrame()
        color_bar.setFixedHeight(80)
        color_bar.setStyleSheet(
            f"background-color: {self.meta.cover_color};"
            f"border-radius: 12px 12px 0 0;"
        )
        layout.addWidget(color_bar)

        # 内容区
        content = QWidget()
        content.setStyleSheet("background-color: #ffffff; border: none; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(4)

        # 标题
        title_label = QLabel(self.meta.title)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(40)
        content_layout.addWidget(title_label)

        # 类型标签
        type_label = QLabel(type_to_name(self.meta.work_type))
        type_label.setStyleSheet("font-size: 11px; color: #5a6a7a;")
        content_layout.addWidget(type_label)

        content_layout.addStretch()

        # 底部信息行
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        # 字数
        word_label = QLabel(f"{format_word_count(self.meta.total_words)} 字")
        word_label.setStyleSheet("font-size: 11px; color: #5a6a7a;")
        info_layout.addWidget(word_label)

        info_layout.addStretch()

        # 模块数
        modules_text = f"{len(self.meta.modules)} 模块"
        modules_label = QLabel(modules_text)
        modules_label.setStyleSheet("font-size: 10px; color: #8a9aaa;")
        info_layout.addWidget(modules_label)

        content_layout.addLayout(info_layout)

        # 更新时间
        try:
            dt = datetime.fromisoformat(self.meta.updated)
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = ""
        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-size: 10px; color: #8a9aaa;")
        content_layout.addWidget(date_label)

        layout.addWidget(content)

    def mousePressEvent(self, event):
        """鼠标点击发射 clicked 信号。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.dir_name)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单。"""
        menu = QMenu(self)

        delete_action = menu.addAction("🗑  删除作品")
        menu.addSeparator()
        open_action = menu.addAction("📂  打开所在目录")

        action = menu.exec(event.globalPos())
        if action == delete_action:
            self.delete_requested.emit(self.dir_name)
        elif action == open_action:
            import subprocess
            from ..storage.workspace import Workspace
            ws = Workspace(Path.cwd() / "works")
            path = ws.get_work_path(self.meta)
            if path.exists():
                subprocess.run(f'explorer "{path}"', shell=True)

    def paintEvent(self, event):
        """自定义绘制，添加阴影效果。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            painter.setPen(QPen(QColor("#2196F3"), 2))
            painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 8, 8)
