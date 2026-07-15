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

        # ── Git 版本管理 ──
        git_group = QGroupBox("版本管理")
        git_layout = QVBoxLayout(git_group)

        self.git_check = QCheckBox("启用 Git 工作空间版本管理（推荐，所有作品共享一个仓库）")
        self.git_check.setChecked(True)
        self.git_check.toggled.connect(self._on_git_toggled)
        git_layout.addWidget(self.git_check)

        # 分隔线
        git_layout.addSpacing(8)

        # GitHub 同步
        self.cloud_check = QCheckBox("同步到 GitHub（可选，需先创建空仓库）")
        self.cloud_check.toggled.connect(self._on_cloud_toggled)
        git_layout.addWidget(self.cloud_check)

        # 仓库名称/URL 输入
        url_layout = QHBoxLayout()
        url_layout.addSpacing(24)
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("GitHub 仓库 URL（如 https://github.com/用户名/仓库名.git）")
        self.repo_input.setEnabled(False)
        self.repo_input.setStyleSheet(
            "padding: 6px 10px; border: 1px solid #d0d0d0; border-radius: 4px; background-color: #f0f0f0; color: #333333;"
        )
        url_layout.addWidget(self.repo_input, stretch=1)
        git_layout.addLayout(url_layout)

        # 提示文字
        hint = QLabel(
            "  使用方式：先去 GitHub 新建一个空仓库（不要选「初始化 README」），\n"
            "  把 HTTPS 地址粘贴到上方输入框即可。\n"
            "  如需自动建仓库，在软件设置中配置 GitHub Token。"
        )
        hint.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 24px;")
        hint.setWordWrap(True)
        git_layout.addWidget(hint)

        # 操作按钮行
        action_layout = QHBoxLayout()
        action_layout.addSpacing(24)

        self.test_btn = QPushButton("测试连接")
        self.test_btn.setEnabled(False)
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8; border: 1px solid #d0d0d0;
                border-radius: 4px; padding: 4px 12px; font-size: 11px;
            }
            QPushButton:hover { background-color: #dcdcdc; }
        """)
        self.test_btn.clicked.connect(self._on_test_connection)
        action_layout.addWidget(self.test_btn)

        self.auto_create_btn = QPushButton("自动创建仓库")
        self.auto_create_btn.setEnabled(False)
        self.auto_create_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ea043; color: white; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 11px;
            }
            QPushButton:hover { background-color: #2c974b; }
        """)
        self.auto_create_btn.clicked.connect(self._on_auto_create)
        action_layout.addWidget(self.auto_create_btn)

        self.connection_status = QLabel("")
        self.connection_status.setStyleSheet("color: #999999; font-size: 11px;")
        action_layout.addWidget(self.connection_status, stretch=1)

        action_layout.addStretch()
        git_layout.addLayout(action_layout)

        layout.addWidget(git_group)

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

    def _on_git_toggled(self, checked: bool):
        """Git 开关切换"""
        self.cloud_check.setEnabled(checked)
        if not checked:
            self.cloud_check.setChecked(False)

    def _on_cloud_toggled(self, checked: bool):
        """云同步复选框切换。"""
        self.repo_input.setEnabled(checked)
        self.test_btn.setEnabled(checked)
        self.auto_create_btn.setEnabled(checked)
        if checked:
            self.repo_input.setStyleSheet(
                "padding: 6px 10px; border: 1px solid #d0d0d0; border-radius: 4px; background-color: #ffffff; color: #333333;"
            )
        else:
            self.repo_input.setStyleSheet(
                "padding: 6px 10px; border: 1px solid #d0d0d0; border-radius: 4px; background-color: #f0f0f0; color: #333333;"
            )
            self.connection_status.setText("")

    def _on_test_connection(self):
        """测试远程仓库连接。"""
        url = self.repo_input.text().strip()
        if not url:
            return
        from ..storage.git_manager import test_remote_connection
        self.connection_status.setText("正在测试连接...")
        self.test_btn.setEnabled(False)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        ok, msg = test_remote_connection(url)
        if ok:
            self.connection_status.setStyleSheet("color: #4caf50; font-size: 11px;")
            self.connection_status.setText("连接成功")
        else:
            self.connection_status.setStyleSheet("color: #f44336; font-size: 11px;")
            self.connection_status.setText(msg)
        self.test_btn.setEnabled(True)

    def _on_auto_create(self):
        """通过 GitHub API 自动创建仓库。"""
        from ..storage.git_manager import _load_token, create_github_repo
        token, user = _load_token()
        if not token:
            QMessageBox.information(
                self, "需要 Token",
                "自动创建仓库需要 GitHub Personal Access Token。\n\n"
                "请前往 https://github.com/settings/tokens 生成一个 Token\n"
                "（勾选 repo 权限），然后粘贴到弹窗中。"
            )
            from PySide6.QtWidgets import QInputDialog
            new_token, ok = QInputDialog.getText(
                self, "GitHub Token",
                "Paste your GitHub Personal Access Token:",
                echo=QLineEdit.EchoMode.Password,
            )
            if not ok or not new_token.strip():
                return
            token = new_token.strip()
            # 试着获取用户名
            import urllib.request, json
            try:
                req = urllib.request.Request(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}",
                             "User-Agent": "ReWrite"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    user = data.get("login", "")
            except Exception:
                user = ""
            from ..storage.git_manager import _save_token
            _save_token(token, user)

        # 从输入提取仓库名，或让用户输入
        repo_url = self.repo_input.text().strip()
        repo_name = ""
        if repo_url:
            # 从 URL 提取仓库名：https://github.com/user/repo.git -> repo
            parts = repo_url.rstrip("/").rstrip(".git").split("/")
            if len(parts) >= 2:
                repo_name = parts[-1]

        if not repo_name:
            from PySide6.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(
                self, "仓库名称",
                "输入要创建的 GitHub 仓库名称（英文）：",
                text=repo_name or "my-novel",
            )
            if not ok or not name.strip():
                return
            repo_name = name.strip()

        self.connection_status.setText("正在创建仓库...")
        self.auto_create_btn.setEnabled(False)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        ok, result = create_github_repo(token, repo_name, private=True)
        if ok:
            self.repo_input.setText(result)
            self.connection_status.setStyleSheet("color: #4caf50; font-size: 11px;")
            self.connection_status.setText("仓库创建成功！URL 已填入上方输入框")
        else:
            self.connection_status.setStyleSheet("color: #f44336; font-size: 11px;")
            self.connection_status.setText(result)
        self.auto_create_btn.setEnabled(True)

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

        git_enabled = self.git_check.isChecked()
        cloud_enabled = self.cloud_check.isChecked()
        git_remote = self.repo_input.text().strip() if cloud_enabled else ""
        git_auto_push = False

        self.result_data = {
            "title": title,
            "work_type": work_type,
            "modules": modules,
            "git_enabled": git_enabled,
            "git_remote": git_remote,
            "git_auto_push": git_auto_push,
            "date_era": self.era_edit.text().strip(),
        }
        self.accept()

    def get_result(self) -> dict:
        """获取用户输入。"""
        return getattr(self, "result_data", None)
