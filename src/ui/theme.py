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
