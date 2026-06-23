"""通用设置页面。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QFormLayout, QComboBox,
    QGroupBox, QCheckBox, QFontComboBox, QMessageBox,
    QLineEdit, QScrollArea,
)

from ..storage.paths import get_config_dir

DEFAULT_SETTINGS = {
    "autosave_delay": 3000,
    "autosave_enabled": True,
    "snapshot_enabled": True,
    "max_snapshots": 10,
    "font_family": "Microsoft YaHei UI",
    "font_size": 14,
    "auto_git_status": True,
}


def _settings_path() -> Path:
    return get_config_dir() / "settings.json"


def load_settings() -> dict:
    """加载设置。"""
    import json
    path = _settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    """保存设置。"""
    import json
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        print(f"保存设置失败")


class GeneralSettingsPage(QWidget):
    """通用设置页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._setup_ui()

    def _setup_ui(self):
        # 外层：保存按钮固定在底部
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # 滚动区域包裹所有设置项
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QLabel.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 编辑器 ──
        editor_group = QGroupBox("编辑器")
        editor_layout = QFormLayout(editor_group)

        font_layout = QHBoxLayout()
        self.font_combo = QFontComboBox()
        font_name = self.settings.get("font_family", "Microsoft YaHei UI")
        self.font_combo.setCurrentFont(QFont(font_name))
        font_layout.addWidget(self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 36)
        self.font_size_spin.setValue(self.settings.get("font_size", 14))
        font_layout.addWidget(self.font_size_spin)

        editor_layout.addRow("正文字体:", font_layout)

        layout.addWidget(editor_group)

        # ── 自动保存 ──
        autosave_group = QGroupBox("自动保存")
        autosave_layout = QFormLayout(autosave_group)

        self.autosave_check = QCheckBox("启用自动保存")
        self.autosave_check.setChecked(self.settings.get("autosave_enabled", True))
        autosave_layout.addRow(self.autosave_check)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 30)
        self.delay_spin.setValue(self.settings.get("autosave_delay", 3000) // 1000)
        autosave_layout.addRow("停止输入后 (秒):", self.delay_spin)

        self.snapshot_check = QCheckBox("启用快照回溯")
        self.snapshot_check.setChecked(self.settings.get("snapshot_enabled", True))
        autosave_layout.addRow(self.snapshot_check)

        self.snapshot_spin = QSpinBox()
        self.snapshot_spin.setRange(3, 50)
        self.snapshot_spin.setValue(self.settings.get("max_snapshots", 10))
        autosave_layout.addRow("保留快照数:", self.snapshot_spin)

        layout.addWidget(autosave_group)

        # ── Git ──
        git_group = QGroupBox("Git")
        git_layout = QVBoxLayout(git_group)

        self.git_status_check = QCheckBox("显示 Git 状态栏")
        self.git_status_check.setChecked(self.settings.get("auto_git_status", True))
        git_layout.addWidget(self.git_status_check)

        layout.addWidget(git_group)

        # ── 数据位置 ──
        path_group = QGroupBox("数据位置（重启后生效）")
        path_layout = QFormLayout(path_group)

        # 作品目录
        from ..storage.paths import load_location_config, get_works_dir
        from pathlib import Path as _Path
        import sys as _sys

        self.works_path_edit = QLineEdit()
        self.works_path_edit.setMinimumWidth(360)

        loc = load_location_config()
        _current = _Path.cwd() / "works" if not getattr(_sys, 'frozen', False) else _Path.home() / "Documents" / "ReWrite" / "works"
        if loc.get("works_path"):
            self.works_path_edit.setText(loc["works_path"])
            self.works_path_edit.setPlaceholderText(f"默认位置：{_current}")
        else:
            self.works_path_edit.setText(str(_current))
            self.works_path_edit.setPlaceholderText("留空使用当前路径")
        path_layout.addRow("作品目录:", self.works_path_edit)

        works_btn_row = QHBoxLayout()
        works_migrate_btn = QPushButton("迁移到此位置")
        works_migrate_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        works_migrate_btn.clicked.connect(self._on_migrate_works)
        works_btn_row.addWidget(works_migrate_btn)
        works_reset_btn = QPushButton("恢复默认")
        works_reset_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        works_reset_btn.clicked.connect(lambda: self.works_path_edit.clear())
        works_btn_row.addWidget(works_reset_btn)
        works_btn_row.addStretch()
        path_layout.addRow("", works_btn_row)

        # 配置目录
        from ..storage.paths import get_config_dir as _get_cfg

        self.config_path_edit = QLineEdit()
        self.config_path_edit.setMinimumWidth(360)
        _default_cfg = _get_cfg()
        if loc.get("config_path"):
            self.config_path_edit.setText(loc["config_path"])
            self.config_path_edit.setPlaceholderText(f"默认位置：{_default_cfg}")
        else:
            self.config_path_edit.setText(str(_default_cfg))
            self.config_path_edit.setPlaceholderText("留空使用当前路径")
        path_layout.addRow("配置目录:", self.config_path_edit)

        config_btn_row = QHBoxLayout()
        config_migrate_btn = QPushButton("迁移到此位置")
        config_migrate_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        config_migrate_btn.clicked.connect(self._on_migrate_config)
        config_btn_row.addWidget(config_migrate_btn)
        config_reset_btn = QPushButton("恢复默认")
        config_reset_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        config_reset_btn.clicked.connect(lambda: self.config_path_edit.clear())
        config_btn_row.addWidget(config_reset_btn)
        config_btn_row.addStretch()
        path_layout.addRow("", config_btn_row)

        layout.addWidget(path_group)

        layout.addStretch()

        # 结束内容区，放进滚动区域
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # ── 保存按钮（固定在底部） ──
        save_btn = QPushButton("保存设置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 8px 24px; font-size: 13px;
            }
            QPushButton:hover { background-color: #3a7bc8; }
        """)
        save_btn.clicked.connect(self._on_save)
        outer.addWidget(save_btn)

    def _on_migrate_works(self):
        from ..storage.paths import migrate_works
        new_path = self.works_path_edit.text().strip()
        ok, msg = migrate_works(new_path)
        if ok:
            QMessageBox.information(self, "迁移完成", msg)
        else:
            QMessageBox.warning(self, "迁移失败", msg)

    def _on_migrate_config(self):
        from ..storage.paths import migrate_config
        new_path = self.config_path_edit.text().strip()
        ok, msg = migrate_config(new_path)
        if ok:
            QMessageBox.information(self, "迁移完成", msg)
        else:
            QMessageBox.warning(self, "迁移失败", msg)

    def _on_save(self):
        self.settings["autosave_enabled"] = self.autosave_check.isChecked()
        self.settings["autosave_delay"] = self.delay_spin.value() * 1000
        self.settings["snapshot_enabled"] = self.snapshot_check.isChecked()
        self.settings["max_snapshots"] = self.snapshot_spin.value()
        self.settings["font_family"] = self.font_combo.currentFont().family()
        self.settings["font_size"] = self.font_size_spin.value()
        self.settings["auto_git_status"] = self.git_status_check.isChecked()
        try:
            save_settings(self.settings)
            # 确认保存路径
            from ..storage.paths import get_config_dir
            saved_path = get_config_dir() / "settings.json"
            QMessageBox.information(self, "成功",
                f"设置已保存\n\n保存位置：{saved_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
