"""设置对话框 —— 左侧导航 + 右侧页面。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget, QPushButton,
)

from .general_settings import GeneralSettingsPage
from .ai_settings import AISettingsPage


class SettingsWindow(QDialog):
    """设置主窗口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(900, 700)
        self.resize(900, 700)
        self.setStyleSheet("")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 左侧导航 ──
        nav_widget = QWidget()
        nav_widget.setFixedWidth(150)
        nav_widget.setStyleSheet("background-color: #ffffff; border-right: 1px solid #e0e0e0;")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                border: none; background-color: transparent; font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 16px; border: none; color: #333333;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe; color: #1a73e8; font-weight: bold;
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        nav_layout.addWidget(self.nav_list)

        nav_layout.addStretch()

        layout.addWidget(nav_widget)

        # ── 右侧页面 ──
        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet("background-color: #ffffff;")

        self.general_page = GeneralSettingsPage()
        self.ai_page = AISettingsPage()

        self.stacked.addWidget(self.general_page)
        self.stacked.addWidget(self.ai_page)

        layout.addWidget(self.stacked, stretch=1)

        # 填充导航
        items = [
            ("通用", "一般设置"),
            ("AI 助手", "API 和模型配置"),
        ]
        for name, desc in items:
            item = QListWidgetItem(f"  {name}")
            item.setToolTip(desc)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)

    def _on_nav_changed(self, row: int):
        if row >= 0:
            self.stacked.setCurrentIndex(row)
