"""Git 设置页面 — GitHub Token 与工作空间配置。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QGroupBox, QMessageBox,
)


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

        # 加载已有 Token
        from ..storage.git_manager import _load_token
        token, user = _load_token()
        if token:
            self.token_edit.setText(token[:16] + "...")
            self.token_edit.setPlaceholderText("已配置（如需更换请输入新 Token）")
            self.save_btn.setText("更换 Token")

        layout.addWidget(token_group)
        layout.addStretch()

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
