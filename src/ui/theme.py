"""ReWrite 主题系统 — 现代青蓝风格，玻璃质感，统一视觉。"""

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


# ── 配色系统 ──

class Color:
    """主题色板。修改此处即全局换肤。"""
    # 背景
    BG = "#f0f6fa"              # 主背景：浅青蓝
    BG_ALT = "#e8f0f8"          # 交替背景

    # 表面
    SURFACE = "#ffffff"         # 卡片/面板背景
    SURFACE_GLASS = "rgba(255, 255, 255, 0.85)"  # 玻璃质感

    # 品牌色
    PRIMARY = "#2196F3"         # 主色：Material Blue
    PRIMARY_LIGHT = "#BBDEFB"   # 浅蓝
    PRIMARY_DARK = "#1976D2"    # 深蓝
    ACCENT = "#00BCD4"          # 强调色：青
    ACCENT_LIGHT = "#B2EBF2"    # 浅青

    # 文字
    TEXT = "#1a2332"            # 主文字：深蓝黑
    TEXT_SECONDARY = "#5a6a7a"  # 次要文字
    TEXT_HINT = "#8a9aaa"       # 提示文字
    TEXT_INVERSE = "#ffffff"    # 反色文字

    # 边框
    BORDER = "#e0e8f0"          # 边框
    BORDER_LIGHT = "#eef2f6"    # 浅边框

    # 阴影
    SHADOW = "rgba(0, 0, 0, 0.06)"
    SHADOW_STRONG = "rgba(0, 0, 0, 0.10)"

    # 功能色
    SUCCESS = "#4CAF50"
    WARNING = "#FF9800"
    ERROR = "#F44336"
    INFO = "#2196F3"

    # 语义色背景/边框/文字(状态提示用)
    SUCCESS_BG = "#E8F5E9"
    SUCCESS_BORDER = "#A5D6A7"
    SUCCESS_TEXT = "#2E7D32"
    WARNING_BG = "#FFF8E1"
    WARNING_BORDER = "#FFE0B2"
    WARNING_TEXT = "#795548"
    ERROR_BG = "#FFEBEE"
    ERROR_BORDER = "#FFCDD2"
    ERROR_TEXT = "#C62828"


# ── 主题系统 ──
# 每个主题 = 上述全部 token 的完整配色。切换时通过 set_theme 更新 Color 类属性,
# 所有 `from src.ui.theme import Color` 的引用自动跟随,无需改动各模块。

_THEMES = {
    "light_blue": {
        "label": "浅青蓝",
        "desc": "默认主题 · 清新明亮",
        "colors": {k: getattr(Color, k) for k in dir(Color) if k.isupper()},
    },
    "paper": {
        "label": "暖纸",
        "desc": "米黄护眼 · 柔和纸质",
        "colors": {
            "BG": "#F6F1E7", "BG_ALT": "#EFE7D8", "SURFACE": "#FDFBF5",
            "SURFACE_GLASS": "rgba(253, 251, 245, 0.85)",
            "PRIMARY": "#C08A50", "PRIMARY_LIGHT": "#F0DFC8", "PRIMARY_DARK": "#A06E3A",
            "ACCENT": "#7FA98F", "ACCENT_LIGHT": "#D8E8DE",
            "TEXT": "#3E342A", "TEXT_SECONDARY": "#7A6E60", "TEXT_HINT": "#A99C8C",
            "TEXT_INVERSE": "#FFFFFF",
            "BORDER": "#E2D7C4", "BORDER_LIGHT": "#EFE7D8",
            "SHADOW": "rgba(0, 0, 0, 0.06)", "SHADOW_STRONG": "rgba(0, 0, 0, 0.10)",
            "SUCCESS": "#5B8A5E", "WARNING": "#D98E32", "ERROR": "#C25E4C", "INFO": "#5B8FB9",
            "SUCCESS_BG": "#E4EFE3", "SUCCESS_BORDER": "#BFD8BE", "SUCCESS_TEXT": "#3F6B43",
            "WARNING_BG": "#FBF0DC", "WARNING_BORDER": "#F0DCB4", "WARNING_TEXT": "#8A5F1F",
            "ERROR_BG": "#F9E4DF", "ERROR_BORDER": "#EFC9C0", "ERROR_TEXT": "#A44433",
        },
    },
    "dark": {
        "label": "深夜黑",
        "desc": "深色护眼 · 夜间写作",
        "colors": {
            "BG": "#1E222A", "BG_ALT": "#262B35", "SURFACE": "#2B313D",
            "SURFACE_GLASS": "rgba(43, 49, 61, 0.85)",
            "PRIMARY": "#5B9BD5", "PRIMARY_LIGHT": "#3D5A78", "PRIMARY_DARK": "#82B4E8",
            "ACCENT": "#4EC9B0", "ACCENT_LIGHT": "#2C5C54",
            "TEXT": "#D8DEE9", "TEXT_SECONDARY": "#9AA5B1", "TEXT_HINT": "#6B7684",
            "TEXT_INVERSE": "#1E222A",
            "BORDER": "#3A4150", "BORDER_LIGHT": "#313846",
            "SHADOW": "rgba(0, 0, 0, 0.40)", "SHADOW_STRONG": "rgba(0, 0, 0, 0.55)",
            "SUCCESS": "#57B36C", "WARNING": "#E0A84C", "ERROR": "#E06C5F", "INFO": "#5B9BD5",
            "SUCCESS_BG": "#2A3B30", "SUCCESS_BORDER": "#3E5748", "SUCCESS_TEXT": "#7CC98E",
            "WARNING_BG": "#403822", "WARNING_BORDER": "#5A4C2C", "WARNING_TEXT": "#E0B35C",
            "ERROR_BG": "#422B2A", "ERROR_BORDER": "#5C3A38", "ERROR_TEXT": "#E58A7E",
        },
    },
    "sakura": {
        "label": "樱花粉",
        "desc": "柔粉浪漫 · 少女心",
        "colors": {
            "BG": "#FFF0F2", "BG_ALT": "#FBE3E8", "SURFACE": "#FFFBFB",
            "SURFACE_GLASS": "rgba(255, 251, 251, 0.85)",
            "PRIMARY": "#E27396", "PRIMARY_LIGHT": "#FAD3DE", "PRIMARY_DARK": "#C2557B",
            "ACCENT": "#B8A1D9", "ACCENT_LIGHT": "#E8DFF3",
            "TEXT": "#4A3340", "TEXT_SECONDARY": "#8C6B7B", "TEXT_HINT": "#B79AA8",
            "TEXT_INVERSE": "#FFFFFF",
            "BORDER": "#F0D5DC", "BORDER_LIGHT": "#F8E7EB",
            "SHADOW": "rgba(0, 0, 0, 0.05)", "SHADOW_STRONG": "rgba(0, 0, 0, 0.09)",
            "SUCCESS": "#6FA477", "WARNING": "#D9A13E", "ERROR": "#D96A7A", "INFO": "#6F9EC9",
            "SUCCESS_BG": "#E3F0E4", "SUCCESS_BORDER": "#C0DCC4", "SUCCESS_TEXT": "#46754E",
            "WARNING_BG": "#FBF1DC", "WARNING_BORDER": "#F0DFB4", "WARNING_TEXT": "#8A641F",
            "ERROR_BG": "#F9E2E6", "ERROR_BORDER": "#EFC7CE", "ERROR_TEXT": "#B6485A",
        },
    },
}

_CURRENT_THEME = "light_blue"


def get_theme_names() -> list:
    """返回全部主题 id 列表。"""
    return list(_THEMES.keys())


def get_theme_label(name: str) -> str:
    return _THEMES.get(name, {}).get("label", name)


def get_theme_desc(name: str) -> str:
    return _THEMES.get(name, {}).get("desc", "")


def get_theme_color(name: str, token: str) -> str:
    """读取指定主题的单个 token 色值(用于预览)。"""
    t = _THEMES.get(name)
    if t:
        return t["colors"].get(token, getattr(Color, token, "#000000"))
    return getattr(Color, token, "#000000")


def get_theme_colors(name: str) -> dict:
    """返回指定主题的完整 token 副本(用于预览渲染)。"""
    t = _THEMES.get(name)
    return dict(t["colors"]) if t else {}


def get_current_theme() -> str:
    return _CURRENT_THEME


def set_theme(name: str) -> bool:
    """切换主题:更新 Color 类属性,全部现有引用自动跟随。"""
    global _CURRENT_THEME
    t = _THEMES.get(name)
    if not t:
        return False
    for k, v in t["colors"].items():
        setattr(Color, k, v)
    _CURRENT_THEME = name
    return True


def apply_theme(name: str, app: QApplication):
    """应用主题:更新 Color + palette + 全局 QSS(即时生效)。"""
    if set_theme(name):
        setup_palette(app)
        app.setStyleSheet(global_stylesheet())


def setup_palette(app: QApplication):
    """设置全局 QPalette。"""
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window, QColor(Color.BG))
    p.setColor(QPalette.ColorRole.WindowText, QColor(Color.TEXT))
    p.setColor(QPalette.ColorRole.Base, QColor(Color.SURFACE))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(Color.BG_ALT))
    p.setColor(QPalette.ColorRole.Text, QColor(Color.TEXT))
    p.setColor(QPalette.ColorRole.Button, QColor(Color.SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(Color.TEXT))
    p.setColor(QPalette.ColorRole.BrightText, QColor(Color.TEXT_INVERSE))
    p.setColor(QPalette.ColorRole.Highlight, QColor(Color.PRIMARY))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(Color.TEXT_INVERSE))
    p.setColor(QPalette.ColorRole.Link, QColor(Color.PRIMARY))

    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(Color.TEXT_HINT))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(Color.TEXT_HINT))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(Color.TEXT_HINT))

    app.setPalette(p)


def global_stylesheet() -> str:
    """返回全局 QSS 样式表。"""
    return f"""
        /* ── 全局基础 ── */
        QWidget {{
            font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 13px;
            color: {Color.TEXT};
        }}

        QMainWindow {{
            background-color: {Color.BG};
        }}

        /* ── 菜单栏 ── */
        QMenuBar {{
            background-color: {Color.SURFACE};
            border-bottom: 1px solid {Color.BORDER};
            padding: 2px 0;
        }}
        QMenuBar::item {{
            padding: 6px 12px;
            border-radius: 4px;
            margin: 2px 2px;
        }}
        QMenuBar::item:selected {{
            background-color: {Color.PRIMARY_LIGHT};
        }}
        QMenu {{
            background-color: {Color.SURFACE};
            border: 1px solid {Color.BORDER};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {Color.PRIMARY_LIGHT};
        }}
        QMenu::separator {{
            height: 1px;
            background: {Color.BORDER};
            margin: 4px 12px;
        }}

        /* ── Dock Widget（所有面板） ── */
        QDockWidget {{
            background-color: {Color.BG};
            titlebar-close-icon: none;
            titlebar-normal-icon: none;
        }}
        QDockWidget::title {{
            background-color: {Color.SURFACE};
            padding: 8px 12px;
            border-bottom: 1px solid {Color.BORDER};
            text-align: left;
            font-size: 12px;
            font-weight: 600;
            color: {Color.TEXT_SECONDARY};
        }}
        QDockWidget::close-button, QDockWidget::float-button {{
            border: none;
            border-radius: 3px;
            padding: 2px;
        }}
        QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
            background-color: {Color.BORDER};
        }}

        /* ── 按钮 ── */
        QPushButton {{
            border: 1px solid {Color.BORDER};
            border-radius: 6px;
            padding: 6px 16px;
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
        }}
        QPushButton:hover {{
            background-color: {Color.BG_ALT};
            border-color: {Color.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {Color.PRIMARY_LIGHT};
        }}
        QPushButton:disabled {{
            color: {Color.TEXT_HINT};
            background-color: {Color.BG_ALT};
        }}

        /* ── 输入框 ── */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            border: 1px solid {Color.BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
            selection-background-color: {Color.PRIMARY_LIGHT};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {Color.PRIMARY};
        }}

        /* ── 下拉框 ── */
        QComboBox {{
            border: 1px solid {Color.BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
        }}
        QComboBox:hover {{
            border-color: {Color.PRIMARY};
        }}
        QComboBox QAbstractItemView {{
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
            border: 1px solid {Color.BORDER};
            border-radius: 6px;
            selection-background-color: {Color.PRIMARY_LIGHT};
            selection-color: {Color.TEXT};
        }}

        /* ── 复选框 ── */
        QCheckBox {{
            spacing: 8px;
            color: {Color.TEXT};
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {Color.BORDER};
            border-radius: 4px;
        }}
        QCheckBox::indicator:checked {{
            background-color: {Color.PRIMARY};
            border-color: {Color.PRIMARY};
        }}

        /* ── 列表 / 树 ── */
        QListWidget, QTreeWidget {{
            border: none;
            border-radius: 8px;
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
            outline: none;
        }}
        QListWidget::item, QTreeWidget::item {{
            padding: 8px 12px;
            border-radius: 4px;
            color: {Color.TEXT};
        }}
        QListWidget::item:selected, QTreeWidget::item:selected {{
            background-color: {Color.PRIMARY_LIGHT};
            color: {Color.TEXT};
        }}
        QListWidget::item:hover, QTreeWidget::item:hover {{
            background-color: {Color.BG_ALT};
        }}

        /* ── 滚动区域 ── */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}

        /* ── 分割器 ── */
        QSplitter::handle {{
            background-color: {Color.BORDER};
            width: 1px;
        }}

        /* ── 状态栏 ── */
        QStatusBar {{
            background-color: {Color.SURFACE};
            border-top: 1px solid {Color.BORDER};
            font-size: 11px;
            color: {Color.TEXT_SECONDARY};
            padding: 2px 8px;
        }}

        /* ── 分组框 ── */
        QGroupBox {{
            border: 1px solid {Color.BORDER};
            border-radius: 8px;
            margin-top: 12px;
            padding: 16px 12px 8px;
            background-color: {Color.SURFACE};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: {Color.TEXT};
            font-weight: 600;
        }}

        /* ── 标签 ── */
        QLabel {{
            color: {Color.TEXT};
            border: none;
        }}

        /* ── Tab Widget ── */
        QTabWidget::pane {{
            border: none;
            background-color: {Color.BG};
        }}
        QTabBar::tab {{
            padding: 8px 20px;
            border: none;
            border-bottom: 2px solid transparent;
            color: {Color.TEXT_SECONDARY};
        }}
        QTabBar::tab:selected {{
            color: {Color.PRIMARY};
            border-bottom: 2px solid {Color.PRIMARY};
        }}
        QTabBar::tab:hover {{
            color: {Color.TEXT};
        }}

        /* ── 工具栏 ── */
        QToolBar {{
            background-color: {Color.SURFACE};
            border-bottom: 1px solid {Color.BORDER};
            spacing: 2px;
            padding: 2px 8px;
        }}
        QToolButton {{
            padding: 4px 10px;
            border-radius: 4px;
            color: {Color.TEXT};
        }}
        QToolButton:hover {{
            background-color: {Color.BG_ALT};
        }}
        QToolButton:pressed {{
            background-color: {Color.PRIMARY_LIGHT};
        }}

        /* ── 对话框 ── */
        QDialog {{
            background-color: {Color.SURFACE};
            color: {Color.TEXT};
        }}

        /* ── 消息框 ── */
        QMessageBox {{
            background-color: {Color.SURFACE};
        }}
        QMessageBox QLabel {{
            color: {Color.TEXT};
        }}
    """
