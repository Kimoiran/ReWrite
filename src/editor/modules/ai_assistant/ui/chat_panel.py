"""AI 对话面板 — 聊天式交互界面。"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QCheckBox, QTextBrowser, QSizePolicy, QApplication,
    QToolButton, QMenu, QInputDialog,
)

from src.ui.theme import Color


class MessageBubble(QFrame):
    """单条消息气泡。用 QTextBrowser 替代 QLabel 解决长文本截断。"""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        role_label = QLabel("你" if role == "user" else "AI")
        role_label.setStyleSheet(
            f"font-weight: bold; font-size: 11px; color: {Color.TEXT_HINT}; border: none;"
        )
        layout.addWidget(role_label)

        # QTextBrowser — 固定高度基于内容，不挤缩
        self.browser = QTextBrowser()
        self.browser.setHtml(content)
        # 安全:禁用链接点击(openLinks 关闭内部导航,external 关闭外部打开,
        # AI 输出中的 http/file 链接点击零动作,防 SSRF 与本地文件读取)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        bg = Color.PRIMARY_LIGHT if role == "user" else Color.BG_ALT
        self.browser.setStyleSheet(f"""
            QTextBrowser {{
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 13px;
                line-height: 1.6;
                background-color: {bg};
                color: {Color.TEXT};
                border: none;
            }}
        """)
        layout.addWidget(self.browser)

        # 延迟一次 resize，等布局稳定
        QTimer.singleShot(30, self._resize_to_content)

    def set_content(self, html: str):
        self.browser.setHtml(html)
        QTimer.singleShot(10, self._resize_to_content)

    def _resize_to_content(self):
        """根据实际宽度重新计算气泡高度。"""
        w = self.browser.viewport().width()
        if w < 50:
            w = 480
        doc = self.browser.document()
        doc.setTextWidth(w)
        h = int(doc.size().height()) + 16
        self.browser.setMinimumHeight(max(40, h))


class LoadingBubble(QFrame):
    """加载动画气泡，支持显示 AI 推理过程。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        role_label = QLabel("AI")
        role_label.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {Color.TEXT_HINT}; border: none;")
        layout.addWidget(role_label)

        self.dots_label = QLabel("  思考中...")
        self.dots_label.setStyleSheet(f"""
            QLabel {{
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 13px;
                background-color: {Color.BG_ALT};
                color: {Color.TEXT_HINT};
                border: none;
                font-style: italic;
            }}
        """)
        layout.addWidget(self.dots_label)

        # 推理过程显示区（可滚动，默认隐藏）
        self.reasoning_scroll = QScrollArea()
        self.reasoning_scroll.setWidgetResizable(True)
        self.reasoning_scroll.setMaximumHeight(400)
        self.reasoning_scroll.setVisible(False)
        self.reasoning_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {Color.WARNING_BORDER};
                border-radius: 6px;
                background-color: {Color.WARNING_BG};
                margin-top: 2px;
            }}
        """)
        self.reasoning_content = QLabel("")
        self.reasoning_content.setWordWrap(True)
        # 安全:纯文本渲染,防止流式推理内容中的 HTML 被当富文本解析
        self.reasoning_content.setTextFormat(Qt.TextFormat.PlainText)
        self.reasoning_content.setStyleSheet(f"""
            QLabel {{
                padding: 6px 10px;
                font-size: 11px;
                color: {Color.WARNING_TEXT};
                background: transparent;
                border: none;
            }}
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
    """确认气泡 — 嵌入聊天框，带允许/取消/全部允许按钮。确认后变灰显示已确认。"""

    confirmed = Signal(list)
    auto_confirmed = Signal(list)
    cancelled = Signal()

    def __init__(self, descriptions: list[str], tool_calls: list, parent=None):
        super().__init__(parent)
        self.tool_calls = tool_calls
        self._confirmed = False
        self.setStyleSheet("border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.role_label = QLabel("AI 请求操作")
        self.role_label.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {Color.WARNING}; border: none;")
        layout.addWidget(self.role_label)

        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Color.WARNING_BG};
                border: 1px solid {Color.WARNING_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setSpacing(4)

        for desc in descriptions:
            label = QLabel(f"  • {desc}")
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {Color.WARNING_TEXT}; font-size: 12px; border: none;")
            bg_layout.addWidget(label)

        layout.addWidget(self.bg_frame)

        # 按钮行
        self.btn_row = QHBoxLayout()
        self.btn_row.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 14px;
                border: 1px solid {Color.BORDER}; border-radius: 4px;
                background: {Color.SURFACE}; color: {Color.TEXT_SECONDARY}; }}
        """)
        self.cancel_btn.clicked.connect(self.cancelled.emit)
        self.btn_row.addWidget(self.cancel_btn)

        self.auto_btn = QPushButton("全部允许")
        self.auto_btn.setToolTip("允许本次及后续所有 AI 操作,不再逐条确认")
        self.auto_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 14px;
                border: 1px solid {Color.SUCCESS}; border-radius: 4px;
                background: {Color.SUCCESS_BG}; color: {Color.SUCCESS_TEXT}; }}
        """)
        self.auto_btn.clicked.connect(self._on_auto_confirm)
        self.btn_row.addWidget(self.auto_btn)

        self.confirm_btn = QPushButton("允许")
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 14px;
                border: none; border-radius: 4px;
                background: {Color.PRIMARY}; color: white; font-weight: bold; }}
        """)
        self.confirm_btn.clicked.connect(self._on_confirm)
        self.btn_row.addWidget(self.confirm_btn)

        layout.addLayout(self.btn_row)

    def _mark_confirmed(self, label_text: str):
        """标记已确认，禁用按钮，变色。"""
        self._confirmed = True
        self.role_label.setText(label_text)
        self.role_label.setStyleSheet(
            f"font-weight: bold; font-size: 11px; color: {Color.SUCCESS}; border: none;")
        self.bg_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Color.SUCCESS_BG};
                border: 1px solid {Color.SUCCESS_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        for i in range(self.bg_frame.layout().count()):
            w = self.bg_frame.layout().itemAt(i).widget()
            if isinstance(w, QLabel):
                w.setStyleSheet(f"color: {Color.SUCCESS_TEXT}; font-size: 12px; border: none;")
        self.cancel_btn.setVisible(False)
        self.auto_btn.setVisible(False)
        self.confirm_btn.setText("执行中...")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 14px;
                border: none; border-radius: 4px;
                background: {Color.SUCCESS_BORDER}; color: {Color.SUCCESS_TEXT}; }}
        """)

    def _on_confirm(self):
        self._mark_confirmed("✅ 已确认")
        self.confirmed.emit(self.tool_calls)

    def _on_auto_confirm(self):
        self._mark_confirmed("✅ 已确认(后续操作自动允许)")
        self.auto_confirmed.emit(self.tool_calls)


class ScopeChip(QCheckBox):
    """单个上下文范围开关。"""

    def __init__(self, scope_id: str, label: str, default: bool = False, parent=None):
        super().__init__(label, parent)
        self.scope_id = scope_id
        self.setChecked(default)
        self.setStyleSheet(f"""
            QCheckBox {{
                font-size: 11px;
                padding: 3px 8px;
                border: 1px solid {Color.BORDER};
                border-radius: 12px;
                background-color: {Color.BG_ALT};
                color: {Color.TEXT_SECONDARY};
                spacing: 4px;
            }}
            QCheckBox:checked {{
                background-color: {Color.PRIMARY_LIGHT};
                border-color: {Color.PRIMARY};
                color: {Color.PRIMARY_DARK};
            }}
            QCheckBox::indicator {{
                width: 0;
                height: 0;
            }}
        """)

    def _get_scope(self) -> str:
        return self.scope_id


class ChatPanel(QDockWidget):
    """AI 对话面板。"""

    send_message_signal = Signal(str, str)
    undo_requested = Signal()
    edit_memory_requested = Signal()
    compress_memory_requested = Signal()
    clear_requested = Signal()

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
        # 本轮对话的第一个气泡(撤回时从它开始删除)
        self._session_first_bubble = None
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
        scope_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {Color.TEXT_SECONDARY};")
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
            btn.setStyleSheet(f"font-size: 10px; padding: 2px 8px; border: 1px solid {Color.BORDER}; border-radius: 8px; background: {Color.BG_ALT}; color: {Color.TEXT_SECONDARY};")
            btn.clicked.connect(lambda checked, s=scope_list: self._apply_preset(s))
            preset_layout.addWidget(btn)

        # 快捷创建人物按钮
        add_char_btn = QPushButton("+ 创建人物")
        add_char_btn.setToolTip("输入角色名,AI 将创建人物卡片并引导你补充信息")
        add_char_btn.setStyleSheet(f"font-size: 10px; padding: 2px 8px; border: 1px solid {Color.SUCCESS}; border-radius: 8px; background: {Color.SUCCESS_BG}; color: {Color.SUCCESS_TEXT};")
        add_char_btn.clicked.connect(self._on_quick_add_character)
        preset_layout.addWidget(add_char_btn)

        # 记忆菜单(编辑/压缩/清空 收进一个按钮,计数并入按钮文本)
        self.mem_menu_btn = QToolButton()
        self.mem_menu_btn.setText("🧠 记忆")
        self.mem_menu_btn.setToolTip("管理 AI 的长期记忆(对话历史)")
        self.mem_menu_btn.setStyleSheet(f"""
            QToolButton {{
                font-size: 10px; padding: 2px 8px;
                border: 1px solid {Color.BORDER}; border-radius: 8px;
                background: {Color.BG_ALT}; color: {Color.TEXT_SECONDARY};
            }}
            QToolButton::menu-indicator {{ image: none; }}
        """)
        mem_menu = QMenu(self)
        mem_menu.addAction("编辑记忆", self._on_edit_memory)
        mem_menu.addAction("压缩记忆", self._on_compress_memory)
        mem_menu.addSeparator()
        mem_menu.addAction("清空记忆", self.clear_requested.emit)
        self.mem_menu_btn.setMenu(mem_menu)
        self.mem_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        preset_layout.addWidget(self.mem_menu_btn)

        preset_layout.addStretch()
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
        self.input_edit.setAcceptRichText(False)
        self.input_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self.input_edit)

        # 操作按钮行
        btn_layout = QHBoxLayout()
        self.undo_btn = QPushButton("↩ 撤回")
        self.undo_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 10px; padding: 4px 8px; border: 1px solid {Color.ERROR_BORDER};
                border-radius: 3px; background: {Color.ERROR_BG}; color: {Color.ERROR_TEXT}; }}
            QPushButton:disabled {{ color: {Color.TEXT_HINT}; background: {Color.BG_ALT}; border-color: {Color.BORDER}; }}
        """)
        self.undo_btn.setToolTip("撤回上一条对话(若有 AI 数据修改会一并回滚)")
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        self.undo_btn.setEnabled(False)
        btn_layout.addWidget(self.undo_btn)

        self.analyze_btn = QPushButton("分析全文")
        self.analyze_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 4px 8px; border: 1px solid {Color.BORDER};
                border-radius: 3px; background: {Color.SURFACE}; color: {Color.TEXT_SECONDARY}; }}
        """)
        btn_layout.addWidget(self.analyze_btn)
        btn_layout.addStretch()
        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {Color.PRIMARY}; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px; }}
            QPushButton:hover {{ background-color: {Color.PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: {Color.BORDER}; }}
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)
        layout.addLayout(btn_layout)

        self.setWidget(widget)
        self.send_btn.setEnabled(True)
        self.input_edit.setEnabled(True)

    def _on_input_changed(self):
        self.send_btn.setEnabled(bool(self.input_edit.toPlainText().strip()))

    def set_undo_enabled(self, enabled: bool):
        self.undo_btn.setEnabled(enabled)

    def update_memory(self, count: int):
        """更新记忆按钮上的计数。"""
        if count > 0:
            self.mem_menu_btn.setText(f"🧠 记忆 ({count})")
        else:
            self.mem_menu_btn.setText("🧠 记忆")

    def _scroll_to_bottom(self):
        """滚动消息区域到底部（延迟版本，用于一次性添加消息）。"""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            sb = scroll_area.verticalScrollBar()
            QTimer.singleShot(100, lambda: sb.setValue(sb.maximum()))

    def _scroll_to_bottom_now(self):
        """立即滚动到底部（用于流式更新，先处理待布局再滚）。"""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            sb = scroll_area.verticalScrollBar()
            QApplication.processEvents()
            sb.setValue(sb.maximum())

    def remove_session(self):
        """删除从最近一次用户消息起的全部气泡(用于撤回),保留更早的对话。"""
        if self._session_first_bubble is None:
            return
        idx = self.messages_layout.indexOf(self._session_first_bubble)
        if idx >= 0:
            while self.messages_layout.count() > idx:
                item = self.messages_layout.takeAt(idx)
                if item and item.widget():
                    item.widget().deleteLater()
        self._session_first_bubble = None

    def add_message(self, role: str, content: str, track: bool = True) -> MessageBubble:
        """添加消息气泡。track=False 用于历史回放(不记录会话起点,避免撤回误清全部历史)。"""
        bubble = MessageBubble(role, content)
        self.messages_layout.addWidget(bubble)
        if track and self._session_first_bubble is None:
            self._session_first_bubble = bubble
        self._scroll_to_bottom()
        return bubble

    def begin_streaming_message(self) -> MessageBubble:
        """创建流式消息气泡（替代 loading），返回气泡供后续更新。"""
        self.hide_loading()
        from ..markdown_render import markdown_to_html
        bubble = MessageBubble("assistant", markdown_to_html("<em>...</em>"))
        self.messages_layout.addWidget(bubble)
        self._scroll_to_bottom()
        return bubble

    def update_streaming(self, bubble, accumulated_text: str):
        """用累积的文本更新流式气泡的内容。"""
        from ..markdown_render import markdown_to_html
        html = markdown_to_html(accumulated_text)
        bubble.set_content(html)
        self._scroll_to_bottom_now()

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
        """快捷创建人物:询问角色名,填入引导提示词(走真实 skill 流程)。"""
        name, ok = QInputDialog.getText(self, "创建角色", "角色名称:")
        if ok and name.strip():
            self.input_edit.setPlainText(
                f"请帮我创建角色「{name.strip()}」:先调用 create_character 创建角色卡片,"
                f"然后逐项询问我补充信息(年龄/身份/性格/背景/目标等),"
                f"每次用 update_character 写入一个字段。")
            self.input_edit.setFocus()

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
        # 新一轮对话:记录起始气泡,供撤回精确删除
        self._session_first_bubble = None
        self.add_message("user", text)
        self.input_edit.clear()
        context_scope = self.get_selected_scope()
        self.send_message_signal.emit(text, context_scope)

    def _on_edit_memory(self):
        self.edit_memory_requested.emit()

    def _on_compress_memory(self):
        self.compress_memory_requested.emit()

    def _on_clear(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._session_first_bubble = None
