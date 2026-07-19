"""新建作品对话框。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QWidget,
)

from ..storage.meta import AVAILABLE_MODULES, WORK_TYPES, WORK_TYPE_NAMES, MODULE_NAMES


class CreateWorkDialog(QDialog):
    """新建作品对话框，支持选模块和 Git 配置。"""

    def __init__(self, works_dir: Path, parent=None):
        super().__init__(parent)
        self.works_dir = works_dir
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("创建新作品")
        self.setFixedSize(520, 600)
        self.setStyleSheet("""QGroupBox { font-weight: 600; }""")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── 基本信息 ──
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("输入作品名称...")
        self.title_edit.textChanged.connect(self._validate)
        basic_layout.addRow("作品名称:", self.title_edit)

        self.type_combo = QComboBox()
        for wt in WORK_TYPES:
            self.type_combo.addItem(WORK_TYPE_NAMES.get(wt, wt), wt)
        basic_layout.addRow("作品类型:", self.type_combo)

        self.era_edit = QLineEdit()
        self.era_edit.setPlaceholderText("如「神启」「星历」，留空则时间线用纯数字排序")
        basic_layout.addRow("纪元名:", self.era_edit)

        layout.addWidget(basic_group)

        # ── 模块选择 ──
        module_group = QGroupBox("启用模块（可随时增减）")
        module_layout = QVBoxLayout(module_group)

        self.module_checks = {}
        for mod_id in AVAILABLE_MODULES:
            cb = QCheckBox(MODULE_NAMES.get(mod_id, mod_id))
            if mod_id == "chapters":
                cb.setChecked(True)
                cb.setEnabled(False)
                cb.setToolTip("章节管理为必选模块")
            else:
                cb.setToolTip(f"启用「{MODULE_NAMES.get(mod_id, mod_id)}」功能")
            self.module_checks[mod_id] = cb
            module_layout.addWidget(cb)

        layout.addWidget(module_group)

        # ── 云端同步 ──
        cloud_group = QGroupBox("云端同步")
        cloud_layout = QVBoxLayout(cloud_group)

        self.cloud_check = QCheckBox("☁ 同步到云端（作品将被 Git 跟踪并可推送到 GitHub）")
        self.cloud_check.setChecked(True)
        self.cloud_check.setToolTip(
            "勾选后作品会参与工作空间 Git 版本管理，可通过启动页推送按钮上传到 GitHub。\n"
            "不勾选则作品仅保存在本地，不会被提交或推送。"
        )
        cloud_layout.addWidget(self.cloud_check)

        hint = QLabel(
            "  提示：GitHub 仓库地址和 Token 请在「设置 → Git 版本管理」中统一配置。\n"
            "  创建后可随时通过右键菜单切换作品的云端同步状态。"
        )
        hint.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 4px;")
        hint.setWordWrap(True)
        cloud_layout.addWidget(hint)

        layout.addWidget(cloud_group)

        layout.addStretch()

        # ── 按钮 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background-color: #e0e0e0; color: #333;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.create_btn = QPushButton("创建")
        self.create_btn.setEnabled(False)
        self.create_btn.setStyleSheet(
            "background-color: #4a90d9; color: white; font-weight: bold;"
        )
        self.create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

    def _validate(self):
        """校验输入有效性。"""
        has_title = bool(self.title_edit.text().strip())
        self.create_btn.setEnabled(has_title)

    def _on_create(self):
        """确认创建。"""
        title = self.title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入作品名称")
            return

        modules = [mid for mid, cb in self.module_checks.items() if cb.isChecked()]
        if "chapters" not in modules:
            modules.insert(0, "chapters")

        work_type = self.type_combo.currentData()

        self.result_data = {
            "title": title,
            "work_type": work_type,
            "modules": modules,
            "cloud_enabled": self.cloud_check.isChecked(),
            "date_era": self.era_edit.text().strip(),
        }
        self.accept()

    def get_result(self) -> dict:
        """获取用户输入。"""
        return getattr(self, "result_data", None)
