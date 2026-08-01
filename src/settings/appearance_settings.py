"""外观设置页 — 主题选择(组件化卡片)与实时预览。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QScrollArea, QMessageBox, QApplication,
)

from ..ui.theme import (
    Color, get_theme_names, get_theme_label, get_theme_desc,
    get_theme_colors, get_current_theme, apply_theme,
)
from .general_settings import load_settings, save_settings


# 色板条展示的 token(预览卡上的一排色块)
_PREVIEW_TOKENS = ("PRIMARY", "ACCENT", "SUCCESS", "WARNING", "ERROR", "BG", "SURFACE", "TEXT")


class ThemeCard(QFrame):
    """主题卡片:色板条 + 名称 + 描述,点击选中。"""

    selected_changed = Signal(str)

    def __init__(self, name: str, colors: dict, parent=None):
        super().__init__(parent)
        self.theme_name = name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(170)
        # 用 objectName 选择器(PySide6 中 Python 子类 QSS 类型选择器不生效)
        self.setObjectName("themeCard")
        self.setStyleSheet(
            f"#themeCard {{ border: 2px solid {Color.BORDER};"
            f"border-radius: 10px; background: {Color.SURFACE}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 色板条
        bar = QHBoxLayout()
        bar.setSpacing(3)
        for token in _PREVIEW_TOKENS:
            swatch = QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(
                f"background: {colors.get(token, '#ccc')};"
                f"border: 1px solid rgba(0,0,0,0.15); border-radius: 3px;")
            bar.addWidget(swatch)
        bar.addStretch()
        layout.addLayout(bar)

        # 名称与描述(动态取当前主题色,深色主题下保持可读)
        title = QLabel(get_theme_label(name))
        title.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Color.TEXT}; border: none;")
        layout.addWidget(title)

        desc = QLabel(get_theme_desc(name))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 10px; color: {Color.TEXT_HINT}; border: none;")
        layout.addWidget(desc)

    def set_selected(self, selected: bool):
        """选中态:主色边框 + 浅主色背景(动态取当前主题)。"""
        border = (f"2px solid {Color.PRIMARY}" if selected else f"2px solid {Color.BORDER}")
        bg = (f"{Color.PRIMARY_LIGHT}" if selected else f"{Color.SURFACE}")
        self.setStyleSheet(
            f"#themeCard {{ border: {border}; border-radius: 10px; background: {bg}; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected_changed.emit(self.theme_name)
        super().mousePressEvent(event)


class PreviewPanel(QWidget):
    """主题预览面板:用指定主题的 token 渲染一组示例组件(即时换肤)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors = dict(get_theme_colors(get_current_theme()))
        self._build()

    def _build(self, layout=None):
        if layout is None:
            layout = QVBoxLayout(self)
        c = self._colors
        layout.setContentsMargins(0, 0, 0, 0)

        hint = QLabel("主题预览(选择卡片即时切换)")
        hint.setStyleSheet(f"font-size: 11px; color: {Color.TEXT_HINT};")
        layout.addWidget(hint)

        # 模拟窗口
        self.window_box = QFrame()
        self.window_box.setStyleSheet(
            f"background: {c['BG']}; border: 1px solid {c['BORDER']}; border-radius: 10px;")
        win = QVBoxLayout(self.window_box)
        win.setContentsMargins(16, 16, 16, 16)
        win.setSpacing(10)

        self.title_label = QLabel("ReWrite 写作")
        self.title_label.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {c['TEXT']}; border: none;")
        win.addWidget(self.title_label)

        self.text_label = QLabel("主文字示例:夜雨剪春韭,新炊间黄粱。")
        self.text_label.setStyleSheet(f"font-size: 13px; color: {c['TEXT']}; border: none;")
        win.addWidget(self.text_label)

        self.sub_label = QLabel("次要文字示例:用于辅助说明与注释。")
        self.sub_label.setStyleSheet(f"font-size: 11px; color: {c['TEXT_SECONDARY']}; border: none;")
        win.addWidget(self.sub_label)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("输入框示例…")
        self.edit.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {c['BORDER']}; border-radius: 4px;"
            f"padding: 5px 8px; background: {c['SURFACE']}; color: {c['TEXT']}; }}")
        win.addWidget(self.edit)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn = QPushButton("主要按钮")
        self.btn.setStyleSheet(
            f"QPushButton {{ background: {c['PRIMARY']}; color: {c['TEXT_INVERSE']};"
            f"border: none; border-radius: 4px; padding: 6px 16px; font-size: 12px; }}")
        row.addWidget(self.btn)

        self.success_badge = QLabel("已完成")
        self.success_badge.setStyleSheet(
            f"background: {c['SUCCESS_BG']}; color: {c['SUCCESS_TEXT']};"
            f"border-radius: 8px; padding: 4px 12px; font-size: 11px; border: none;")
        row.addWidget(self.success_badge)

        self.warn_badge = QLabel("写作中")
        self.warn_badge.setStyleSheet(
            f"background: {c['WARNING_BG']}; color: {c['WARNING_TEXT']};"
            f"border-radius: 8px; padding: 4px 12px; font-size: 11px; border: none;")
        row.addWidget(self.warn_badge)
        row.addStretch()
        win.addLayout(row)

        layout.addWidget(self.window_box, stretch=1)

    def set_theme(self, name: str):
        """切换预览主题:清空并复用既有布局重建(避免重复 setLayout 被 Qt 拒绝)。"""
        self._colors = dict(get_theme_colors(name))
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._build(layout)


class AppearanceSettingsPage(QWidget):
    """外观设置页:主题选择 + 预览 + 保存应用。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.current = self.settings.get("theme", get_current_theme())
        if self.current not in get_theme_names():
            self.current = "light_blue"
        self._cards = {}
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("主题")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Color.TEXT};")
        layout.addWidget(title)

        hint = QLabel("选择喜欢的主题,下方即时预览;点击「保存并应用」立即生效。")
        hint.setStyleSheet(f"font-size: 11px; color: {Color.TEXT_HINT};")
        layout.addWidget(hint)

        # 主题卡片区
        card_row = QHBoxLayout()
        card_row.setSpacing(10)
        for name in get_theme_names():
            card = ThemeCard(name, get_theme_colors(name))
            card.selected_changed.connect(self._on_card_selected)
            card.set_selected(name == self.current)
            self._cards[name] = card
            card_row.addWidget(card)
        card_row.addStretch()
        layout.addLayout(card_row)

        # 预览区
        self.preview = PreviewPanel()
        self.preview.set_theme(self.current)
        layout.addWidget(self.preview, stretch=1)

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # 保存按钮
        save_btn = QPushButton("保存并应用")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Color.PRIMARY}; color: {Color.TEXT_INVERSE};
                border: none; border-radius: 4px; padding: 8px 24px; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {Color.PRIMARY_DARK}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        outer.addWidget(save_btn)

    def _on_card_selected(self, name: str):
        """选中卡片:更新选中态 + 即时预览。"""
        if name == self.current:
            return
        self.current = name
        for n, card in self._cards.items():
            card.set_selected(n == name)
        self.preview.set_theme(name)

    def _on_save(self):
        """保存并应用主题(立即生效)。合并最新设置,不覆盖其他页面的字段。"""
        app = QApplication.instance()
        if app is not None:
            apply_theme(self.current, app)
        save_settings({**load_settings(), "theme": self.current})
        QMessageBox.information(
            self, "主题已应用",
            f"已切换为「{get_theme_label(self.current)}」主题\n\n"
            f"已打开的面板将在下次打开时完全应用新主题。")
