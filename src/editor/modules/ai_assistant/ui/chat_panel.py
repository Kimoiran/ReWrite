"""AI 对话面板 — 聊天式交互界面。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QCheckBox,
)


class ScopeChip(QCheckBox):
    """单个上下文范围开关。"""

    def __init__(self, scope_id: str, label: str, default: bool = False, parent=None):
        super().__init__(label, parent)
        self.scope_id = scope_id
        self.setChecked(default)
        self.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                padding: 3px 8px;
                border: 1px solid #e0e8f0;
                border-radius: 12px;
                background-color: #f5f7fa;
                color: #5a6a7a;
                spacing: 4px;
            }
            QCheckBox:checked {
                background-color: #E3F2FD;
                border-color: #2196F3;
                color: #1976D2;
            }
            QCheckBox::indicator {
                width: 0;
                height: 0;
            }
        """)

    def _get_scope(self) -> str:
        return self.scope_id


class ChatPanel(QDockWidget):
    """AI 对话面板。"""

    send_message_signal = Signal(str, str)  # message, context_scope_csv

    def __init__(self, parent=None):
        super().__init__("AI 助手", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(280)
        self._setup_ui()

    def _setup_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 上下文范围选择器（多选芯片） ──
        scope_label = QLabel("AI 可以读取：")
        scope_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #5a6a7a;")
        layout.addWidget(scope_label)

        # 第一行
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self.scope_chips = {}
        chip_configs = [
            ("current_chapter", "当前章节", True),
            ("selected_text", "选中文本", False),
            ("outline", "大纲", True),
        ]
        for sid, label, default in chip_configs:
            chip = ScopeChip(sid, label, default)
            self.scope_chips[sid] = chip
            row1.addWidget(chip)
        layout.addLayout(row1)

        # 第二行
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        chip_configs2 = [
            ("characters", "人物设定卡", True),
            ("timeline", "时间线", False),
            ("work_meta", "作品信息", False),
        ]
        for sid, label, default in chip_configs2:
            chip = ScopeChip(sid, label, default)
            self.scope_chips[sid] = chip
            row2.addWidget(chip)
        layout.addLayout(row2)

        # ── 快捷预设按钮行 ──
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(4)

        presets = [
            ("写作助手", ["current_chapter", "outline", "characters"]),
            ("深度分析", ["current_chapter", "outline", "characters", "timeline", "work_meta"]),
            ("灵感发散", ["outline", "characters", "timeline"]),
        ]
        for label, scope_list in presets:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 10px; padding: 2px 8px;
                    border: 1px solid #e0e8f0; border-radius: 8px;
                    background: #f5f7fa; color: #5a6a7a;
                }
                QPushButton:hover {
                    background: #E3F2FD; border-color: #2196F3;
                }
            """)
            btn.clicked.connect(
                lambda checked, s=scope_list, chips=self.scope_chips: self._apply_preset(s)
            )
            preset_layout.addWidget(btn)

        # 记忆状态 + 清空按钮
        self.memory_label = QLabel("")
        self.memory_label.setStyleSheet("font-size: 10px; color: #8a9aaa; padding: 0 4px;")
        preset_layout.addWidget(self.memory_label)

        self.clear_btn = QPushButton("清空记忆")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px; padding: 2px 8px;
                border: none; border-radius: 8px;
                color: #888;
            }
            QPushButton:hover { color: #f44336; }
        """)
        self.clear_btn.clicked.connect(self._on_clear)
        preset_layout.addWidget(self.clear_btn)

        layout.addLayout(preset_layout)

        # ── 消息历史 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(2)
        scroll.setWidget(self.messages_widget)

        layout.addWidget(scroll, stretch=1)

        # ── 输入区 ──
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入你的问题… 如「分析这一章的情节节奏」")
        self.input_edit.setMaximumHeight(80)
        self.input_edit.setStyleSheet("QTextEdit { padding: 6px; font-size: 12px; }")
        self.input_edit.setAcceptRichText(False)
        layout.addWidget(self.input_edit)

        # ── 发送按钮行 ──
        btn_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("分析全文")
        self.analyze_btn.setStyleSheet("""
            QPushButton { font-size: 11px; padding: 4px 8px; border: 1px solid #d0d0d0;
                border-radius: 3px; background: #f8f8f8; color: #555; }
            QPushButton:hover { background: #eee; }
        """)
        btn_layout.addWidget(self.analyze_btn)

        btn_layout.addStretch()

        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }
            QPushButton:hover { background-color: #3a7bc8; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)

        layout.addLayout(btn_layout)

        self.setWidget(widget)
        self.send_btn.setEnabled(False)

    def update_memory(self, count: int):
        """更新记忆状态显示。"""
        if count > 0:
            self.memory_label.setText(f"🧠 {count} 条记忆")
        else:
            self.memory_label.setText("")

    def add_message(self, role: str, content: str):
        bubble = MessageBubble(role, content)
        self.messages_layout.addWidget(bubble)

    def set_analyze_callback(self, callback):
        self.analyze_btn.clicked.connect(callback)

    def get_selected_scope(self) -> str:
        """获取当前选中的上下文范围，逗号分隔。"""
        selected = [s.scope_id for s in self.scope_chips.values() if s.isChecked()]
        return ",".join(selected) if selected else "current_chapter"

    def _apply_preset(self, scope_list: list):
        """应用预设方案。"""
        for sid, chip in self.scope_chips.items():
            chip.setChecked(sid in scope_list)

    def _on_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.send_btn.setEnabled(False)
        self.add_message("user", text)
        self.input_edit.clear()

        context_scope = self.get_selected_scope()
        self.send_message_signal.emit(text, context_scope)

    def show_loading(self):
        self.add_message("assistant", "思考中...")

    def hide_loading(self):
        last = self.messages_layout.count() - 1
        if last >= 0:
            item = self.messages_layout.itemAt(last)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, MessageBubble) and \
                   w.findChild(QLabel) and \
                   "思考中" in w.findChild(QLabel).text():
                    w.deleteLater()

    def enable_send(self):
        self.send_btn.setEnabled(True)

    def _on_clear(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
