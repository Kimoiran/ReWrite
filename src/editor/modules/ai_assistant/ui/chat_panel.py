"""AI 对话面板 — 聊天式交互界面。"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QCheckBox, QTextBrowser, QSizePolicy, QApplication,
)


class MessageBubble(QFrame):
    """单条消息气泡。用 QTextBrowser 替代 QLabel 解决长文本截断。"""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        role_label = QLabel("你" if role == "user" else "AI")
        role_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; color: #888888; border: none;"
        )
        layout.addWidget(role_label)

        # QTextBrowser — 固定高度基于内容，不挤缩
        self.browser = QTextBrowser()
        self.browser.setHtml(content)
        self.browser.setOpenExternalLinks(True)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        # 根据内容计算高度（用 480 作为默认宽度，避免布局未完成时的窄 fallback）
        doc = self.browser.document()
        doc.setTextWidth(480)
        content_height = int(doc.size().height()) + 16
        self.browser.setMinimumHeight(max(40, min(content_height, 400)))
        QTimer.singleShot(50, lambda: self._resize_to_content())
        bg = "#E3F2FD" if role == "user" else "#F5F7FA"
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 13px;
                line-height: 1.6;
                background-color: {bg};
                color: #1a2332;
                border: none;
            }}
        """)
        layout.addWidget(self.browser)

    def set_content(self, html: str):
        self.browser.setHtml(html)

    def _resize_to_content(self):
        """等布局稳定后根据实际宽度重新计算高度。"""
        w = self.browser.viewport().width()
        if w > 100:
            doc = self.browser.document()
            doc.setTextWidth(w)
            h = int(doc.size().height()) + 16
            self.browser.setMinimumHeight(max(40, min(h, 400)))


class LoadingBubble(QFrame):
    """加载动画气泡，支持显示 AI 推理过程。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        role_label = QLabel("AI")
        role_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #888888; border: none;")
        layout.addWidget(role_label)

        self.dots_label = QLabel("  思考中...")
        self.dots_label.setStyleSheet("""
            QLabel {
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 13px;
                background-color: #F5F7FA;
                color: #8a9aaa;
                border: none;
                font-style: italic;
            }
        """)
        layout.addWidget(self.dots_label)

        # 推理过程显示区（可滚动，默认隐藏）
        self.reasoning_scroll = QScrollArea()
        self.reasoning_scroll.setWidgetResizable(True)
        self.reasoning_scroll.setMaximumHeight(160)
        self.reasoning_scroll.setVisible(False)
        self.reasoning_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #FFE0B2;
                border-radius: 6px;
                background-color: #FFF8E1;
                margin-top: 2px;
            }
        """)
        self.reasoning_content = QLabel("")
        self.reasoning_content.setWordWrap(True)
        self.reasoning_content.setStyleSheet("""
            QLabel {
                padding: 6px 10px;
                font-size: 11px;
                color: #795548;
                background: transparent;
                border: none;
            }
        """)
        self.reasoning_scroll.setWidget(self.reasoning_content)
        layout.addWidget(self.reasoning_scroll)

        # 动画
        self._dot_count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(400)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._dot_count = 0
        self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()

    def set_reasoning(self, text: str):
        """显示 AI 的推理过程。"""
        if text.strip():
            current = self.reasoning_content.text()
            # 增量追加，避免截断
            self.reasoning_content.setText(f"🧠 {current}{text}")
            self.reasoning_scroll.setVisible(True)
        else:
            self.reasoning_scroll.setVisible(False)

    def _tick(self):
        self._dot_count = (self._dot_count % 3) + 1
        dots = "." * self._dot_count
        self.dots_label.setText(f"  思考中{dots}")


class ConfirmBubble(QFrame):
    """确认气泡 — 嵌入聊天框，带允许/取消按钮。确认后变灰显示已确认。"""

    confirmed = Signal(list)
    cancelled = Signal()

    def __init__(self, descriptions: list[str], tool_calls: list, parent=None):
        super().__init__(parent)
        self.tool_calls = tool_calls
        self._confirmed = False
        self.setStyleSheet("border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.role_label = QLabel("AI 请求操作")
        self.role_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #FF8F00; border: none;")
        layout.addWidget(self.role_label)

        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: #FFF8E1;
                border: 1px solid #FFE0B2;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setSpacing(4)

        for desc in descriptions:
            label = QLabel(f"  • {desc}")
            label.setWordWrap(True)
            label.setStyleSheet("color: #795548; font-size: 12px; border: none;")
            bg_layout.addWidget(label)

        layout.addWidget(self.bg_frame)

        # 按钮行
        self.btn_row = QHBoxLayout()
        self.btn_row.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton { font-size: 11px; padding: 4px 14px;
                border: 1px solid #d0d0d0; border-radius: 4px;
                background: #ffffff; color: #666; }
        """)
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        self.btn_row.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("允许")
        self.confirm_btn.setStyleSheet("""
            QPushButton { font-size: 11px; padding: 4px 14px;
                border: none; border-radius: 4px;
                background: #2196F3; color: white; font-weight: bold; }
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.btn_row.addWidget(self.confirm_btn)

        layout.addLayout(self.btn_row)

    def _on_confirm(self):
        """标记已确认，禁用按钮，变色。"""
        self._confirmed = True
        self.role_label.setText("✅ 已确认")
        self.role_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #4CAF50; border: none;")
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: #E8F5E9;
                border: 1px solid #A5D6A7;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        for i in range(self.bg_frame.layout().count()):
            w = self.bg_frame.layout().itemAt(i).widget()
            if isinstance(w, QLabel):
                w.setStyleSheet("color: #2E7D32; font-size: 12px; border: none;")
        self.cancel_btn.setVisible(False)
        self.confirm_btn.setText("执行中...")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("""
            QPushButton { font-size: 11px; padding: 4px 14px;
                border: none; border-radius: 4px;
                background: #A5D6A7; color: #1B5E20; }
        """)
        self.confirmed.emit(self.tool_calls)


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

    send_message_signal = Signal(str, str)
    undo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("AI 助手", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(440)
        self._loading_bubble = None
        self._setup_ui()
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(10)
        self._scroll_timer.timeout.connect(self._scroll_to_bottom)

    def _setup_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 上下文芯片
        scope_label = QLabel("AI 可以读取：")
        scope_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #5a6a7a;")
        layout.addWidget(scope_label)

        self.scope_chips = {}
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        for sid, label, default in [("current_chapter", "当前章节", True), ("selected_text", "选中文本", False), ("outline", "大纲", True)]:
            chip = ScopeChip(sid, label, default); self.scope_chips[sid] = chip; row1.addWidget(chip)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        for sid, label, default in [("characters", "人物设定卡", True), ("timeline", "时间线", False), ("worldview", "世界观", True), ("map", "🗺️ 地图", True), ("work_meta", "作品信息", False)]:
            chip = ScopeChip(sid, label, default); self.scope_chips[sid] = chip; row2.addWidget(chip)
        layout.addLayout(row2)

        # 预设按钮行
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(4)
        for label, scope_list in [
            ("写作助手", ["current_chapter", "outline", "characters", "worldview", "map"]),
            ("深度分析", ["current_chapter", "outline", "characters", "timeline", "worldview", "map", "work_meta"]),
            ("灵感发散", ["outline", "characters", "timeline", "worldview", "map"]),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet("font-size: 10px; padding: 2px 8px; border: 1px solid #e0e8f0; border-radius: 8px; background: #f5f7fa; color: #5a6a7a;")
            btn.clicked.connect(lambda checked, s=scope_list: self._apply_preset(s))
            preset_layout.addWidget(btn)

        # 快捷创建人物按钮
        add_char_btn = QPushButton("+ 创建人物")
        add_char_btn.setStyleSheet("font-size: 10px; padding: 2px 8px; border: 1px solid #4CAF50; border-radius: 8px; background: #E8F5E9; color: #2E7D32;")
        add_char_btn.clicked.connect(self._on_quick_add_character)
        preset_layout.addWidget(add_char_btn)

        self.memory_label = QLabel("")
        self.memory_label.setStyleSheet("font-size: 10px; color: #8a9aaa; padding: 0 4px;")
        preset_layout.addWidget(self.memory_label)

        self.clear_btn = QPushButton("清空记忆")
        self.clear_btn.setStyleSheet("font-size: 10px; padding: 2px 8px; border: none; border-radius: 8px; color: #888;")
        self.clear_btn.clicked.connect(self._on_clear)
        preset_layout.addWidget(self.clear_btn)
        layout.addLayout(preset_layout)

        # 消息区域
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

        # 输入区
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入你的问题… 如「分析这一章的情节节奏」")
        self.input_edit.setMaximumHeight(80)
        self.input_edit.setStyleSheet("QTextEdit { padding: 6px; font-size: 12px; }")
        self.input_edit.setAcceptRichText(False)
        self.input_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self.input_edit)

        # 操作按钮行
        btn_layout = QHBoxLayout()
        self.undo_btn = QPushButton("↩ 撤回")
        self.undo_btn.setStyleSheet("font-size: 10px; padding: 4px 8px; border: 1px solid #e0e0e0; border-radius: 3px; background: #fff5f5; color: #c62828;")
        self.undo_btn.setToolTip("撤回上一条对话")
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        self.undo_btn.setEnabled(False)
        btn_layout.addWidget(self.undo_btn)

        self.analyze_btn = QPushButton("分析全文")
        self.analyze_btn.setStyleSheet("font-size: 11px; padding: 4px 8px; border: 1px solid #d0d0d0; border-radius: 3px; background: #f8f8f8; color: #555;")
        btn_layout.addWidget(self.analyze_btn)
        btn_layout.addStretch()
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("""
            QPushButton { background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background-color: #3a7bc8; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)
        layout.addLayout(btn_layout)

        self.setWidget(widget)
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)

    def _on_input_changed(self):
        self.send_btn.setEnabled(bool(self.input_edit.toPlainText().strip()))

    def remove_last_bubble(self):
        """移除最后一条消息气泡。"""
        count = self.messages_layout.count()
        if count > 0:
            item = self.messages_layout.takeAt(count - 1)
            if item and item.widget():
                item.widget().deleteLater()

    def set_undo_enabled(self, enabled: bool):
        self.undo_btn.setEnabled(enabled)

    def update_memory(self, count: int):
        if count > 0:
            self.memory_label.setText(f"🧠 {count} 条记忆")
        else:
            self.memory_label.setText("")

    def _scroll_to_bottom(self):
        """滚动消息区域到底部（布局完成后再滚动一次，确保准确）。"""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            sb = scroll_area.verticalScrollBar()
            sb.setValue(sb.maximum())
            # 延迟再滚一次，等布局稳定
            QTimer.singleShot(100, lambda: sb.setValue(sb.maximum()))

    def add_message(self, role: str, content: str):
        bubble = MessageBubble(role, content)
        self.messages_layout.addWidget(bubble)
        self._scroll_to_bottom()

    def show_loading(self):
        self._loading_bubble = LoadingBubble()
        self.messages_layout.addWidget(self._loading_bubble)
        self._loading_bubble.start()
        self._scroll_to_bottom()
        QApplication.processEvents()

    def hide_loading(self):
        if self._loading_bubble:
            self._loading_bubble.stop()
            self._loading_bubble.deleteLater()
            self._loading_bubble = None

    def set_analyze_callback(self, callback):
        self.analyze_btn.clicked.connect(callback)

    def _on_quick_add_character(self):
        """快捷创建人物：填好提示词模板到输入框。"""
        template = (
            "请用 [EDIT] 语法帮我创建一个新角色。\n"
            "我会逐项告诉你信息，你每次用 [EDIT:character:xxx] 写入一个字段。\n"
            "先等我给出具体数据再操作。"
        )
        self.input_edit.setPlainText(template)

    def get_selected_scope(self) -> str:
        selected = [s.scope_id for s in self.scope_chips.values() if s.isChecked()]
        return ",".join(selected) if selected else "current_chapter"

    def _apply_preset(self, scope_list: list):
        for sid, chip in self.scope_chips.items():
            chip.setChecked(sid in scope_list)

    def add_confirm_bubble(self, descriptions: list, tool_calls: list) -> ConfirmBubble:
        """添加确认气泡到聊天框。"""
        self.hide_loading()
        bubble = ConfirmBubble(descriptions, tool_calls)
        self.messages_layout.addWidget(bubble)
        self._scroll_to_bottom()
        return bubble

    def enable_send(self):
        self.send_btn.setEnabled(True)

    def _on_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.send_btn.setEnabled(False)
        self.add_message("user", text)
        self.input_edit.clear()
        context_scope = self.get_selected_scope()
        self.send_message_signal.emit(text, context_scope)

    def _on_clear(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
