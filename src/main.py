"""ReWrite 写作软件 —— 入口。"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.storage.workspace import Workspace
from src.ui.theme import setup_palette, global_stylesheet


def _check_crash_recovery(workspace: Workspace):
    """检测上次退出是否异常，提示恢复。"""
    from src.editor.autosave.recovery import has_crashed, get_recoverable_snapshots
    from PySide6.QtWidgets import QMessageBox

    crashed_works = []
    for meta in workspace.scan():
        wp = workspace.get_work_path(meta)
        if has_crashed(wp):
            snapshots = get_recoverable_snapshots(wp)
            if snapshots:
                crashed_works.append((meta.title, wp, snapshots))

    if not crashed_works:
        return

    msg = "上次退出时检测到异常，以下作品包含自动保存的快照：\n\n"
    for title, wp, snaps in crashed_works:
        msg += f"  {title}: {len(snaps)} 个快照\n"

    reply = QMessageBox.question(
        None, "检测到异常退出",
        msg + "\n是否查看快照并恢复？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if reply == QMessageBox.StandardButton.Yes:
        for title, wp, snaps in crashed_works:
            QMessageBox.information(
                None, f"恢复: {title}",
                f"最近的快照: {snaps[0]['time']}\n"
                f"快照保存在: {wp}/.autosave/snapshots/\n\n"
                "进入编辑器后可从 .autosave 目录手动复制。"
            )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ReWrite")
    app.setOrganizationName("ReWrite")
    app.setApplicationVersion("0.1.0")

    # 应用现代主题
    setup_palette(app)

    # 全局字体
    font = QFont()
    font.setFamilies(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)

    # 应用全局 QSS
    app.setStyleSheet(global_stylesheet())

    # 底层样式引擎
    app.setStyle("Fusion")

    from src.storage.paths import get_works_dir, get_config_dir, LOCATION_FILE
    from src.storage.paths import load_location_config as _loc

    # 根据配置确定作品和配置目录
    works_dir = get_works_dir(_project_root)
    config_dir = get_config_dir()

    # 打包后第一次运行提示路径信息
    import sys as _sys
    if getattr(_sys, 'frozen', False) and not LOCATION_FILE.exists():
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.information(
            None, "ReWrite",
            f"作品保存在：\n{works_dir}\n\n"
            f"配置文件（API Key、Token、AI 记忆）在：\n{config_dir}\n\n"
            "你在设置中可随时修改这些路径。\n\n"
            "exe 可放在任意位置，数据不受影响。",
            QMessageBox.StandardButton.Ok,
        )

    workspace = Workspace(works_dir)

    # 崩溃恢复检测
    _check_crash_recovery(workspace)

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
