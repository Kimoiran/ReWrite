"""ReWrite 写作软件 —— 入口。"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.storage.workspace import Workspace


def _clean_crash_markers(workspace: Workspace):
    """启动时静默清理崩溃标记，不弹窗。"""
    from src.editor.autosave.recovery import has_crashed
    for meta in workspace.scan():
        wp = workspace.get_work_path(meta)
        if has_crashed(wp):
            marker = wp / ".autosave" / ".crash_marker"
            try:
                marker.unlink()
            except OSError:
                pass


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ReWrite")
    app.setOrganizationName("ReWrite")
    app.setApplicationVersion("1.2.0")
    # Windows 任务栏图标：AppUserModelID 必须在窗口创建前设置
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Kimoiran.ReWrite")
    except Exception:
        pass

    # Windows 定时器精度 1ms(默认 ~15.6ms):QPropertyAnimation 帧率
    # 从 ~64fps 提升到近 1000Hz tick,高刷屏(120/180Hz)动画不再卡顿闪烁
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass

    # 应用主题(用户配置;默认浅青蓝,非法值兜底)
    from src.settings.general_settings import load_settings
    from src.ui.theme import apply_theme, get_theme_names
    theme = load_settings().get("theme", "light_blue")
    if theme not in get_theme_names():
        theme = "light_blue"
    apply_theme(theme, app)

    # 设置应用图标（任务栏和标题栏）
    # Windows 任务栏需要 .ico 格式，.png 可能不生效
    icon_paths = [_project_root / "assets" / "icon.ico",
                  _project_root / "assets" / "icon.png"]
    for p in icon_paths:
        if p.exists():
            app.setWindowIcon(QIcon(str(p)))
            break

    # 全局字体
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)

    # 底层样式引擎
    app.setStyle("Fusion")

    from src.storage.paths import get_works_dir, get_config_dir

    # 根据配置确定作品和配置目录
    works_dir = get_works_dir(_project_root)
    workspace = Workspace(works_dir)

    # 静默清理崩溃标记（不弹窗）
    _clean_crash_markers(workspace)

    from src.launcher.window import LauncherWindow
    launcher = LauncherWindow(workspace)

    # 持有编辑器引用，防止被垃圾回收
    _editor_ref = []
    _switching = []  # 打开作品淡出过渡中标志(防重复点击/editor 泄漏)

    def open_editor(work_path: str):
        from src.editor.window import EditorWindow
        if _switching:
            return  # 构造/切换中,忽略重复点击
        _switching.append(True)
        try:
            editor = EditorWindow(work_path)
        finally:
            _switching.pop()
        _editor_ref.append(editor)

        def on_editor_closed():
            if _switching:
                return  # 打开过程中,忽略关闭回调
            _editor_ref.clear()
            launcher._skip_fade_in = True  # 直接切换:本次显示跳过淡入(先置位,兜底路径一致)
            try:
                launcher.refresh_after_edit()
                # 恢复启动页几何与透明度,直接显示(无动画)
                prev_geo = getattr(launcher, "_prev_geometry", None)
                if prev_geo is not None:
                    launcher.setGeometry(prev_geo)
                launcher.show()
            except Exception:
                launcher.show()  # 兜底:异常也要回到主页
            finally:
                # 本次切换后恢复淡入(下次打开作品等场景仍生效)
                QTimer.singleShot(0, lambda: setattr(launcher, "_skip_fade_in", False))

        editor.closed.connect(on_editor_closed)

        # 直接切换(无开关动画):记录启动页几何 → 隐藏 → 显示编辑器
        launcher._prev_geometry = launcher.geometry()
        launcher.hide()
        editor._skip_fade_in = True
        editor.show()

    def open_settings():
        from src.settings.window import SettingsWindow
        from src.ui.theme import get_current_theme
        old_path = workspace.works_dir
        old_theme = get_current_theme()
        dialog = SettingsWindow(launcher)
        dialog.exec()
        # 主题变化 → 启动页即时刷新(背景/按钮/卡片)
        if get_current_theme() != old_theme:
            launcher.refresh_theme()
        # 设置关闭后检查作品路径是否变更，如有变更则刷新
        new_works_dir = get_works_dir(_project_root)
        if new_works_dir != old_path:
            workspace.works_dir = new_works_dir
            workspace.works_dir.mkdir(parents=True, exist_ok=True)
            launcher.refresh_after_edit()

    launcher.open_work_requested.connect(open_editor)
    launcher.settings_requested.connect(open_settings)
    # 启动:先弹品牌标识卡(ReWrite × Kimoiran),再展开启动页
    from src.ui.transition import BrandSplash
    splash = BrandSplash(on_hidden=launcher.show)
    splash.play_in(hold_ms=650)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
