"""Git 设置页面 — GitHub Token 与工作空间配置。"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox, QCheckBox,
)
from ..storage.paths import get_works_dir


class GitSettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        title = QLabel("Git 工作空间配置")
        title.setStyleSheet("font-size:16px; font-weight:700; color:#1a2332;")
        layout.addWidget(title)

        sub = QLabel("所有作品共享一个 Git 仓库，在启动页统一提交推送。")
        sub.setStyleSheet("color:#666; font-size:12px;")
        layout.addWidget(sub)

        # ── 仓库地址 ──
        repo_group = QGroupBox("远程仓库")
        repo_layout = QFormLayout(repo_group)

        self.repo_edit = QLineEdit()
        self.repo_edit.setPlaceholderText("https://github.com/用户名/仓库名.git")
        repo_layout.addRow("GitHub 仓库 URL:", self.repo_edit)

        repo_hint = QLabel(
            "所有作品共享一个仓库。先去 GitHub 创建空仓库（不要勾选初始化 README），\n"
            "将 HTTPS 地址粘贴到此处。配置后启动页的「推送」按钮即可使用。"
        )
        repo_hint.setStyleSheet("color:#888; font-size:11px; padding:4px 0;")
        repo_layout.addRow(repo_hint)

        repo_btn_layout = QHBoxLayout()
        self.save_repo_btn = QPushButton("保存仓库地址")
        self.save_repo_btn.clicked.connect(self._on_save_repo)
        repo_btn_layout.addWidget(self.save_repo_btn)
        self.repo_status = QLabel("")
        self.repo_status.setStyleSheet("color:#888; font-size:11px;")
        repo_btn_layout.addWidget(self.repo_status)
        repo_btn_layout.addStretch()
        repo_layout.addRow(repo_btn_layout)

        layout.addWidget(repo_group)

        # ── Token ──
        token_group = QGroupBox("GitHub Token")
        token_layout = QFormLayout(token_group)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        token_layout.addRow("Personal Access Token:", self.token_edit)

        hint = QLabel(
            "在 https://github.com/settings/tokens 生成，勾选 repo 权限。\n"
            "Token 保存在本地 ~/.rewrite/git_config.json，不会上传。"
        )
        hint.setStyleSheet("color:#888; font-size:11px; padding:4px 0;")
        token_layout.addRow(hint)

        self.save_btn = QPushButton("保存 Token")
        self.save_btn.clicked.connect(self._on_save)
        token_layout.addRow(self.save_btn)

        layout.addWidget(token_group)

        # 加载已有配置
        from ..storage.git_manager import _load_token
        token, user = _load_token()
        if token:
            self.token_edit.setText(token[:16] + "...")
            self.token_edit.setPlaceholderText("已配置（如需更换请输入新 Token）")
            self.save_btn.setText("更换 Token")

        from ..storage.work_io import load_workspace_git_config
        git_config = load_workspace_git_config(get_works_dir())
        saved_url = git_config.get("remote_url", "")
        # 回退：从 git remote 读取已绑定的 URL
        if not saved_url:
            works_dir = get_works_dir()
            if (works_dir / ".git").exists():
                from ..storage.git_manager import GitManager
                gm = GitManager(works_dir)
                try:
                    saved_url = gm.get_remote_url()
                except Exception:
                    saved_url = ""
        if saved_url:
            self.repo_edit.setText(saved_url)

        # ── 作品云端同步管理 ──
        works_group = QGroupBox("作品云端同步")
        works_group_layout = QVBoxLayout(works_group)
        works_hint = QLabel("勾选的作品将参与 Git 版本控制并可推送到 GitHub：")
        works_hint.setStyleSheet("color:#555; font-size:12px;")
        works_group_layout.addWidget(works_hint)
        self._work_checks = {}
        self._load_work_cloud_list(works_group_layout)
        layout.addWidget(works_group)

        layout.addStretch()

    def _on_save_repo(self):
        url = self.repo_edit.text().strip()
        if not url:
            return
        from ..storage.work_io import save_workspace_git_config
        from ..storage.git_manager import GitManager
        works_dir = get_works_dir()
        save_workspace_git_config(works_dir, {"remote_url": url, "enabled": True})
        if works_dir.exists() and (works_dir / ".git").exists():
            gm = GitManager(works_dir)
            gm.set_remote(url)
            self.repo_status.setText("已保存并绑定远程仓库")
        else:
            self.repo_status.setText("已保存（将在下次推送时生效）")
        self.repo_status.setStyleSheet("color:#4caf50; font-size:11px;")

    def _load_work_cloud_list(self, parent_layout: QVBoxLayout):
        """加载所有作品，每个一行带云同步复选框。"""
        from ..storage.workspace import Workspace
        from ..storage.work_io import set_work_cloud_enabled as toggle_cloud

        works_dir = get_works_dir()
        ws = Workspace(works_dir)
        works = ws.scan()

        if not works:
            no_work = QLabel("暂无作品")
            no_work.setStyleSheet("color:#999; font-size:12px; padding:8px 0;")
            parent_layout.addWidget(no_work)
            return

        for meta in works:
            work_path = ws.get_work_path(meta)
            cb = QCheckBox(f"☁ {meta.title}  ({meta.work_type})")
            cb.setChecked(meta.cloud_enabled)
            cb.setToolTip(f"目录: {work_path.name}")
            cb.toggled.connect(lambda checked, wp=work_path: self._on_work_cloud_toggled(wp, checked))
            self._work_checks[work_path] = cb
            parent_layout.addWidget(cb)

    def _on_work_cloud_toggled(self, work_path: Path, enabled: bool):
        """切换单个作品的云端同步状态。"""
        from ..storage.work_io import set_work_cloud_enabled
        if set_work_cloud_enabled(work_path, enabled):
            self.repo_status.setText(f"已{'启用' if enabled else '取消'}「{work_path.name}」的云端同步")
            self.repo_status.setStyleSheet("color:#4caf50; font-size:11px;")
        else:
            self.repo_status.setText("更新失败")
            self.repo_status.setStyleSheet("color:#f44336; font-size:11px;")

    def _on_save(self):
        token = self.token_edit.text().strip()
        if not token or token.endswith("..."):
            return

        # 验证 Token
        import urllib.request, json
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}",
                         "User-Agent": "ReWrite"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                user = data.get("login", "未知")
        except Exception as e:
            QMessageBox.critical(self, "验证失败", f"Token 无效或网络错误: {e}")
            return

        from ..storage.git_manager import _save_token
        _save_token(token, user)
        QMessageBox.information(self, "成功", f"Token 已保存！GitHub 用户: {user}")
        self.token_edit.setText(token[:16] + "...")
