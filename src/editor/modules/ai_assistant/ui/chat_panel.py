"""AI 对话面板 — 聊天式交互界面。"""

import html as _html

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QCheckBox, QTextBrowser, QSizePolicy, QApplication,
    QToolButton, QMenu, QInputDialog,
)

from src.ui.theme import Color


# 思考过程在气泡里最多保留这么多字符（超出只留尾部），避免超长推理把界面撑爆
_MAX_REASONING_CHARS = 8000


def merge_reasoning_text(current: str, chunk: str,
                         limit: int = _MAX_REASONING_CHARS) -> str:
    """把流式推理片段并入已显示文本（超长只留尾部）。

    旧实现是 ``setText(f"🧠 {current}{chunk}")``：每来一个片段都重新拼一次
    「大脑图标 + 已有全文」，于是屏幕堆出成百上千个 🧠。这里只做纯文本拼接，
    图标交给固定的标题标签，只会出现一次。
    """
    if not chunk:
        return current or ""
    merged = f"{current or ''}{chunk}"
    if len(merged) > limit:
        merged = "…（前段略）\n" + merged[-limit:]
    return merged


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
        QTimer.singleShot(90, self._resize_to_content)   # 布局稳定后再校一次

    def _resize_to_content(self):
        """按内容真实高度收紧气泡。

        旧实现只用 ``setMinimumHeight``：内容变短时（流式占位的「…」被最终正文替换、
        或思考块被移除）高度收不回来，气泡底部就留出一大片空白。
        改用 ``setFixedHeight``，并记录已应用尺寸，避免 resize 事件递归。
        """
        w = self.browser.viewport().width()
        if w < 50:
            return                       # 尚未布局完成，等下一次
        doc = self.browser.document()
        doc.setTextWidth(w)
        h = max(40, int(doc.size().height()) + 18)
        if getattr(self, "_applied_size", None) == (w, h):
            return
        self._applied_size = (w, h)
        self.browser.setFixedHeight(h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.browser.viewport().width()
        applied_w = getattr(self, "_applied_size", (0, 0))[0]
        if w > 50 and abs(w - applied_w) > 2:
            QTimer.singleShot(0, self._resize_to_content)


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
        self.reasoning_header = QLabel("🧠 思考过程")
        self.reasoning_header.setStyleSheet(
            f"QLabel {{ font-size: 11px; font-weight: 700; color: {Color.WARNING_TEXT};"
            f" background: transparent; border: none; padding: 2px 2px 0 2px; }}")
        self.reasoning_header.setVisible(False)
        layout.addWidget(self.reasoning_header)

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
        """增量显示 AI 的推理过程。

        旧实现写成 ``setText(f"🧠 {current}{text}")``：每来一个流式片段，
        就把「🧠 + 已有全文」重新拼一次，于是屏幕上堆出成百上千个大脑图标。
        现在标题只在头部出现一次，正文按增量追加，并自动滚到最后一行。
        """
        if not text or not text.strip():
            self.reasoning_scroll.setVisible(False)
            self.reasoning_header.setVisible(False)
            return
        current = self.reasoning_content.text()
        self.reasoning_content.setText(merge_reasoning_text(current, text))
        self.reasoning_header.setVisible(True)
        self.reasoning_scroll.setVisible(True)
        # 让最新的思考内容始终可见
        sb = self.reasoning_scroll.verticalScrollBar()
        QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

    def clear_reasoning(self):
        self.reasoning_content.setText("")
        self.reasoning_scroll.setVisible(False)
        self.reasoning_header.setVisible(False)

    @property
    def reasoning_text(self) -> str:
        """当前累计的推理文本（供结束时并入消息，便于回看）。"""
        return self.reasoning_content.text()

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
    stop_requested = Signal()  # 「■ 停止」:中断 AI 当前生成
    edit_work_prompt_requested = Signal()

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
        self.setMinimumWidth(300)  # 最窄保护(侧边栏模式下不至于挤坏)
        # 不锁定最大宽度:编写世界观/地图等长内容时可拖宽到接近正文宽度
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

        # ── 头部:标题 + 工具(分析全文 / 记忆) ──
        header = QHBoxLayout()
        title = QLabel("AI 助手")
        title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {Color.TEXT}; border: none;")
        header.addWidget(title)
        header.addStretch()

        tool_btn_style = f"""
            QToolButton {{ font-size: 10px; padding: 2px 8px;
                border: 1px solid {Color.BORDER}; border-radius: 10px;
                background: {Color.BG_ALT}; color: {Color.TEXT_SECONDARY}; }}
            QToolButton::menu-indicator {{ image: none; }}
        """
        self.analyze_btn = QToolButton()
        self.analyze_btn.setText("分析全文")
        self.analyze_btn.setToolTip("让 AI 分析整部作品全文")
        self.analyze_btn.setStyleSheet(tool_btn_style)
        header.addWidget(self.analyze_btn)

        # 记忆菜单(编辑/压缩/清空 收进一个按钮,计数并入按钮文本)
        self.mem_menu_btn = QToolButton()
        self.mem_menu_btn.setText("🧠 记忆")
        self.mem_menu_btn.setToolTip("管理 AI 的长期记忆(对话历史)")
        self.mem_menu_btn.setStyleSheet(tool_btn_style)
        mem_menu = QMenu(self)
        mem_menu.addAction("编辑记忆", self._on_edit_memory)
        mem_menu.addAction("压缩记忆", self._on_compress_memory)
        mem_menu.addSeparator()
        mem_menu.addAction("清空记忆", self.clear_requested.emit)
        self.mem_menu_btn.setMenu(mem_menu)
        self.mem_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        header.addWidget(self.mem_menu_btn)
        layout.addLayout(header)

        # ── 上下文芯片:一行高频 + 「⋯」展开其余(紧凑侧边栏) ──
        chip_label = QLabel("AI 可以读取:")
        chip_label.setStyleSheet(f"font-size: 10px; color: {Color.TEXT_HINT}; border: none;")
        layout.addWidget(chip_label)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self.scope_chips = {}
        for sid, label, default in [("current_chapter", "当前章节", True),
                                    ("selected_text", "选中文本", False),
                                    ("outline", "大纲", True),
                                    ("worldview", "世界观", True)]:
            chip = ScopeChip(sid, label, default)
            self.scope_chips[sid] = chip
            row1.addWidget(chip)
        self._more_btn = QToolButton()
        self._more_btn.setText("⋯")
        self._more_btn.setToolTip("更多上下文范围")
        self._more_btn.setCheckable(True)
        self._more_btn.setStyleSheet(f"""
            QToolButton {{ font-size: 12px; padding: 2px 8px;
                border: 1px solid {Color.BORDER}; border-radius: 12px;
                background: {Color.BG_ALT}; color: {Color.TEXT_SECONDARY}; }}
            QToolButton:checked {{ border-color: {Color.PRIMARY}; color: {Color.PRIMARY_DARK}; }}
        """)
        self._more_btn.toggled.connect(self._toggle_extra_scopes)
        row1.addWidget(self._more_btn)
        row1.addStretch()
        layout.addLayout(row1)

        self._extra_row = QHBoxLayout()
        self._extra_row.setSpacing(4)
        for sid, label, default in [("characters", "人物设定卡", True),
                                    ("timeline", "时间线", False),
                                    ("map", "🗺️ 地图", True),
                                    ("work_meta", "作品信息", False)]:
            chip = ScopeChip(sid, label, default)
            self.scope_chips[sid] = chip
            self._extra_row.addWidget(chip)
        self._extra_row.addStretch()
        self._extra_widget = QWidget()
        self._extra_widget.setLayout(self._extra_row)
        self._extra_widget.setVisible(False)
        layout.addWidget(self._extra_widget)

        # 消息区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        # 显式持有消息区引用：以前用 findChild(QScrollArea) 查找，
        # 会先命中「思考过程」里那个滚动区，导致自动贴底滚错了控件。
        self.messages_scroll = scroll
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(2)
        scroll.setWidget(self.messages_widget)
        layout.addWidget(scroll, stretch=1)

        # ── 输入区(Cursor 式圆角输入框,固定底部) ──
        # AI 工作状态条:思考中提示 + 锁定发言栏的可见指示
        self.status_indicator = QLabel("🤔 AI 思考中… 请稍候")
        self.status_indicator.setStyleSheet(f"""
            QLabel {{ font-size: 11px; padding: 4px 10px;
                border: 1px solid {Color.PRIMARY}; border-radius: 10px;
                background: {Color.PRIMARY_BG if hasattr(Color, "PRIMARY_BG") else Color.BG_ALT};
                color: {Color.PRIMARY_DARK}; }}
        """)
        self.status_indicator.setVisible(False)
        layout.addWidget(self.status_indicator)
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("输入你的问题… 如「分析这一章的情节节奏」")
        self.input_edit.setMaximumHeight(90)
        self.input_edit.setAcceptRichText(False)
        self.input_edit.textChanged.connect(self._on_input_changed)
        self.input_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Color.BORDER};
                border-radius: 12px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: {Color.SURFACE};
                color: {Color.TEXT};
            }}
            QTextEdit:focus {{ border-color: {Color.PRIMARY}; }}
        """)
        layout.addWidget(self.input_edit)

        # 操作按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.undo_btn = QPushButton("↩ 撤回")
        self.undo_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 10px; padding: 4px 8px; border: 1px solid {Color.ERROR_BORDER};
                border-radius: 6px; background: {Color.ERROR_BG}; color: {Color.ERROR_TEXT}; }}
            QPushButton:disabled {{ color: {Color.TEXT_HINT}; background: {Color.BG_ALT}; border-color: {Color.BORDER}; }}
        """)
        self.undo_btn.setToolTip("撤回上一条对话(若有 AI 数据修改会一并回滚)")
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        self.undo_btn.setEnabled(False)
        btn_layout.addWidget(self.undo_btn)

        # 快捷指令(预设/创建人物 收进菜单,保持面板紧凑)
        self.quick_menu_btn = QToolButton()
        self.quick_menu_btn.setText("✨ 指令")
        self.quick_menu_btn.setToolTip("常用快捷指令:预设上下文组合 / 快速创建人物")
        self.quick_menu_btn.setStyleSheet(f"""
            QToolButton {{ font-size: 10px; padding: 2px 8px;
                border: 1px solid {Color.BORDER}; border-radius: 10px;
                background: {Color.BG_ALT}; color: {Color.TEXT_SECONDARY}; }}
            QToolButton::menu-indicator {{ image: none; }}
        """)
        quick_menu = QMenu(self)
        quick_menu.addAction("写作助手", lambda: self._apply_preset(
            ["current_chapter", "outline", "characters", "worldview", "map"]))
        quick_menu.addAction("深度分析", lambda: self._apply_preset(
            ["current_chapter", "outline", "characters", "timeline", "worldview", "map", "work_meta"]))
        quick_menu.addAction("灵感发散", lambda: self._apply_preset(
            ["outline", "characters", "timeline", "worldview", "map"]))
        quick_menu.addSeparator()
        quick_menu.addAction("创建人物…", self._on_quick_add_character)
        quick_menu.addSeparator()
        quick_menu.addAction("设置作品提示词…", self._on_edit_work_prompt)
        self.quick_menu_btn.setMenu(quick_menu)
        self.quick_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_layout.addWidget(self.quick_menu_btn)

        btn_layout.addStretch()

        # ■ 停止:AI 生成/执行期间显示,点击中断当前生成(已生成内容保留并记入记忆)
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{ font-size: 11px; padding: 6px 14px; border: 1px solid {Color.ERROR_BORDER};
                border-radius: 8px; background: {Color.ERROR_BG}; color: {Color.ERROR_TEXT}; }}
            QPushButton:hover {{ background: {Color.ERROR_BORDER}; color: white; }}
        """)
        self.stop_btn.setToolTip("停止 AI 当前生成(已生成的内容会保留并记入记忆)")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setVisible(False)
        btn_layout.addWidget(self.stop_btn)

        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {Color.PRIMARY}; color: white; border: none;
                border-radius: 8px; padding: 6px 18px; font-size: 12px; }}
            QPushButton:hover {{ background-color: {Color.PRIMARY_DARK}; }}
            QPushButton:disabled {{ background-color: {Color.BORDER}; }}
        """)
        self.send_btn.clicked.connect(self._on_send)
        btn_layout.addWidget(self.send_btn)
        layout.addLayout(btn_layout)

        self.setWidget(widget)
        # 发送按钮初始状态跟随输入框内容(空输入禁用)
        self.send_btn.setEnabled(bool(self.input_edit.toPlainText().strip()))
        self.input_edit.setEnabled(True)

    def _toggle_extra_scopes(self, checked: bool):
        """展开/收起第二行上下文芯片(紧凑侧边栏)。"""
        self._extra_widget.setVisible(checked)

    def showEvent(self, event):
        super().showEvent(event)
        # 面板每次显示时滚到最新消息(历史回放/布局变化后滚动位置会失效,
        # 避免打开 AI 助手时停留在很早的消息)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_input_changed(self):
        self.send_btn.setEnabled(bool(self.input_edit.toPlainText().strip()))

    def set_undo_enabled(self, enabled: bool):
        self._undo_enabled = enabled
        self.undo_btn.setEnabled(enabled and not getattr(self, "_busy", False))

    def update_memory(self, count: int):
        """更新记忆按钮上的计数。"""
        if count > 0:
            self.mem_menu_btn.setText(f"🧠 记忆 ({count})")
        else:
            self.mem_menu_btn.setText("🧠 记忆")

    def _messages_vbar(self):
        """消息区的垂直滚动条（找不到时退回旧行为）。"""
        scroll_area = getattr(self, "messages_scroll", None) or self.findChild(QScrollArea)
        return scroll_area.verticalScrollBar() if scroll_area else None

    def _stick_to_bottom(self):
        """把消息区贴到底部（内部函数，可安全重复调用）。"""
        sb = self._messages_vbar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def _scroll_to_bottom(self, _delay: int = 0):
        """滚动消息区域到底部。

        两段式：立刻一次 + 120ms 后再一次。内容高度在流式更新/气泡移除后
        会异步变化，只滚一次常常停在旧的最大值上，表现为「下面一大片空白」。
        """
        QTimer.singleShot(_delay, self._stick_to_bottom)
        QTimer.singleShot(_delay + 120, self._stick_to_bottom)

    def _scroll_to_bottom_now(self):
        """立即滚动到底部（用于流式更新，先处理待布局再滚）。"""
        QApplication.processEvents()
        self._stick_to_bottom()

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

    @staticmethod
    def _reasoning_block_html(reasoning: str) -> str:
        """思考过程的展示块（主题色，深色主题下不会变成白块）。"""
        esc = _html.escape(reasoning or "").replace("\n", "<br>")
        return (
            f"<div style='font-size:11px;line-height:1.45;color:{Color.TEXT_HINT};"
            f"padding:6px 10px;background:{Color.WARNING_BG};"
            f"border-left:3px solid {Color.WARNING_BORDER};border-radius:4px;"
            f"margin-bottom:8px;'><b>🧠 思考过程</b><br>{esc}</div>"
        )

    def render_assistant(self, text: str) -> str:
        """把 AI 回复渲染成 HTML：主题色思考块 + 正文。

        - 思考过程**保留显示**（用户随时能回看推理）；
        - 但它不会进入上下文：发回模型前由 ``providers.sanitize_messages`` 剥离。
        """
        from ..orchestrator import AIOrchestrator
        from ..markdown_render import markdown_to_html

        reasoning, body = AIOrchestrator.split_reasoning(text or "")
        html = markdown_to_html(body)
        return self._reasoning_block_html(reasoning) + html if reasoning else html

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

    def update_streaming(self, bubble, accumulated_text: str, reasoning: str = ""):
        """用累积的文本更新流式气泡；reasoning 非空时在其上方保留思考块。"""
        from ..markdown_render import markdown_to_html
        html = markdown_to_html(accumulated_text)
        if reasoning:
            html = self._reasoning_block_html(reasoning) + html
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
            # 移除高大的加载/思考气泡后内容骤然变短，滚动条会停在旧的最大值上，
            # 屏幕看起来就是「对话完成后下方一大片空白」。等布局稳定后重新贴底。
            QTimer.singleShot(0, self._stick_to_bottom)
            QTimer.singleShot(150, self._stick_to_bottom)

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

    def set_busy(self, busy: bool):
        """AI 工作状态:锁定/解锁发言栏,并显示「思考中」提示条。

        busy=True:输入框 + 发送按钮禁用,提示条可见(防止 AI 工作期间
        重复输入导致任务交错);busy=False:恢复(发送按钮跟随输入内容)。
        """
        self._busy = bool(busy)
        self.status_indicator.setVisible(self._busy)
        self.input_edit.setEnabled(not self._busy)
        self.send_btn.setEnabled(not self._busy)
        # 停止按钮:AI 工作期间可见可点(即使输入框被锁,也要能刹住车)
        self.stop_btn.setVisible(self._busy)
        self.stop_btn.setEnabled(self._busy)
        # undo 可用性由 set_undo_enabled 决定,busy 只做叠加禁用
        self.undo_btn.setEnabled(
            not self._busy and getattr(self, "_undo_enabled", True))
        self.analyze_btn.setEnabled(not self._busy)
        if not self._busy:
            self.send_btn.setEnabled(bool(self.input_edit.toPlainText().strip()))

    def enable_send(self):
        self.set_busy(False)

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

    def _on_edit_work_prompt(self):
        """设置作品提示词:由 module 处理(需要 work.json 读写)。"""
        self.edit_work_prompt_requested.emit()

    def _on_compress_memory(self):
        self.compress_memory_requested.emit()

    def _on_clear(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._session_first_bubble = None
