"""ReWrite 写作软件 —— 入口。"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.storage.workspace import Workspace
from src.ui.theme import setup_palette, global_stylesheet


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
    app.setApplicationVersion("0.1.0")

    # 应用现代主题
    setup_palette(app)

    # 设置应用图标（任务栏和标题栏）
    icon_path = _project_root / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 全局字体
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)

    # 应用全局 QSS
    app.setStyleSheet(global_stylesheet())

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

    def open_editor(work_path: str):
        from src.editor.window import EditorWindow
        editor = EditorWindow(work_path)

        def on_editor_closed():
            _editor_ref.clear()
            launcher.refresh_after_edit()
            launcher.show()

        editor.closed.connect(on_editor_closed)
        _editor_ref.append(editor)
        launcher.hide()
        editor.show()

    def open_settings():
        from src.settings.window import SettingsWindow
        dialog = SettingsWindow(launcher)
        dialog.exec()

    launcher.open_work_requested.connect(open_editor)
    launcher.settings_requested.connect(open_settings)
    launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
