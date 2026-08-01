"""编辑器状态栏——显示字数、保存状态、章节名、Git 状态。"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QStatusBar, QLabel, QPushButton, QMenu,
)
from PySide6.QtGui import QAction
from ..ui.theme import Color


class EditorStatusBar(QStatusBar):
    """编辑器底部状态栏。"""

    commit_push_requested = Signal(str)  # message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QStatusBar { padding: 2px 8px; }")

        # 章节名
        self.chapter_label = QLabel("未打开章节")
        self.addWidget(self.chapter_label)

        self.addPermanentWidget(QLabel("  │  "))

        # 字数
        self.word_count_label = QLabel("0 字")
        self.addPermanentWidget(self.word_count_label)

        self.addPermanentWidget(QLabel("  │  "))

        # 保存状态
        self.save_label = QLabel("已保存")
        self.save_label.setStyleSheet(f"color: {Color.SUCCESS};")
        self.addPermanentWidget(self.save_label)

        self.addPermanentWidget(QLabel("  │  "))

        # 手动推送按钮
        self.push_btn = QPushButton("☁  提交并推送")
        self.push_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Color.PRIMARY};
                color: {Color.TEXT_INVERSE};
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Color.PRIMARY_DARK};
            }}
            QPushButton:disabled {{
                background-color: {Color.BORDER};
                color: {Color.TEXT_HINT};
            }}
        """)
        self.push_btn.setVisible(False)
        self.push_btn.clicked.connect(self._on_push_clicked)
        self.addPermanentWidget(self.push_btn)

        self.addPermanentWidget(QLabel("  │  "))

        # Git 状态按钮（可点击弹出菜单）
        self.git_btn = QPushButton("Git: --")
        self.git_btn.setFlat(True)
        self.git_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.git_btn.setStyleSheet(f"""
            QPushButton {{
                color: {Color.TEXT_HINT}; border: none; font-size: 11px;
                padding: 0 4px; text-align: left;
            }}
            QPushButton:hover {{ color: {Color.TEXT}; }}
        """)
        self.git_btn.clicked.connect(self._on_git_click)
        self.addPermanentWidget(self.git_btn)

        # 保存状态计时器
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._on_save_timeout)

    def update_word_count(self, count: int):
        self.word_count_label.setText(f"{format_word_count(count)} 字")

    def set_chapter_name(self, name: str):
        self.chapter_label.setText(f"{name}")

    def show_saving(self):
        self.save_label.setText("保存中...")
        self.save_label.setStyleSheet(f"color: {Color.WARNING};")

    def show_saved(self):
        self.save_label.setText(f"已保存 {datetime.now():%H:%M:%S}")
        self.save_label.setStyleSheet(f"color: {Color.SUCCESS};")

    def show_unsaved(self):
        self.save_label.setText("未保存")
        self.save_label.setStyleSheet(f"color: {Color.ERROR};")

    def _on_save_timeout(self):
        self.show_saved()

    def flash_saved(self):
        self.show_saving()
        QTimer.singleShot(500, self.show_saved)

    def update_git_status(self, status: dict):
        """更新 Git 状态显示。内容为空时隐藏按钮。"""
        # 有远程仓库就显示推送按钮
        self.push_btn.setVisible(False)  # 提交推送已移到启动页

        if not status.get("has_remote") and not status.get("dirty") and not status.get("commit_count"):
            self.git_btn.setText("Git: -")
            self.git_btn.setStyleSheet(
                f"QPushButton {{ color: {Color.TEXT_HINT}; border: none; font-size: 11px; padding: 0 4px; }}"
            )
            return

        parts = []
        style = f"color: {Color.TEXT_HINT};"

        if status["ahead"] > 0:
            parts.append(f"↑{status['ahead']}")
            style = f"color: {Color.PRIMARY};"
        if status["behind"] > 0:
            parts.append(f"↓{status['behind']}")
            style = f"color: {Color.WARNING};"
        if status["unstaged"] > 0:
            parts.append(f"~{status['unstaged']}")
            style = f"color: {Color.WARNING};"
        if status["staged"] > 0:
            parts.append(f"+{status['staged']}")
            style = f"color: {Color.SUCCESS};"
        if not status["has_remote"] and status["commit_count"] > 0:
            parts.append("(仅本地)")

        text = "Git: " + (" ".join(parts) if parts else "干净")
        self.git_btn.setText(text)
        self.git_btn.setStyleSheet(
            f"QPushButton {{ color: {style.split(':')[1].strip()}; border: none; font-size: 11px; padding: 0 4px; text-align: left; }}"
            f"QPushButton:hover {{ color: {Color.TEXT}; }}"
        )

    def _on_git_click(self):
        """点击 Git 按钮显示状态（提交推送已移到启动页）。"""
        menu = QMenu(self)
        menu.addAction("提交并推送请使用启动页的 Git 按钮").setEnabled(False)
        menu.exec(self.git_btn.mapToGlobal(self.git_btn.rect().bottomLeft()))

    def _on_commit_push(self):
        pass

    def _on_push_clicked(self):
        pass


def format_word_count(count: int) -> str:
    return f"{count:,}"
