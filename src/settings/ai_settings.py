"""AI 助手设置页面。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QGroupBox,
    QCheckBox, QPlainTextEdit, QMessageBox,
)

from .ai_config import load_ai_config, save_ai_config


class AISettingsPage(QWidget):
    """AI 助手设置页。"""

    PROVIDER_INFO = {
        "claude": {
            "label": "Anthropic Claude",
            "models": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5"],
            "url_hint": "https://api.anthropic.com",
            "default_url": "https://api.anthropic.com",
            "api_type": "claude",
        },
        "openai": {
            "label": "OpenAI",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "url_hint": "https://api.openai.com/v1",
            "default_url": "https://api.openai.com/v1",
            "api_type": "openai",
        },
        "deepseek": {
            "label": "DeepSeek",
            "models": ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
            "url_hint": "https://api.deepseek.com",
            "default_url": "https://api.deepseek.com",
            "api_type": "openai",
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = load_ai_config()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # ── API 配置 ──
        api_group = QGroupBox("API 服务")
        api_layout = QFormLayout(api_group)

        self.provider_combo = QComboBox()
        for key, info in self.PROVIDER_INFO.items():
            self.provider_combo.addItem(info["label"], key)
        idx = self.provider_combo.findData(self.config.get("provider", "claude"))
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        api_layout.addRow("供应商:", self.provider_combo)

        self.model_combo = QComboBox()
        self._update_models()
        api_layout.addRow("模型:", self.model_combo)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("输入 API Key...")
        if self.config.get("api_key"):
            self.api_key_edit.setText(self.config["api_key"])
        api_layout.addRow("API Key:", self.api_key_edit)

        self.api_url_edit = QLineEdit()
        provider_key = self.provider_combo.currentData()
        info = self.PROVIDER_INFO.get(provider_key, {})
        self.api_url_edit.setPlaceholderText(info.get("url_hint", ""))
        self.api_url_edit.setText(self.config.get("api_url", info.get("default_url", "")))
        api_layout.addRow("API 地址:", self.api_url_edit)

        layout.addWidget(api_group)

        # ── 上下文范围 ──
        ctx_group = QGroupBox("上下文范围（AI 可以读取的内容）")
        ctx_layout = QVBoxLayout(ctx_group)

        self.context_checks = {}
        ctx_options = [
            ("current_chapter", "当前章节"),
            ("outline", "大纲"),
            ("characters", "人物设定卡"),
            ("timeline", "时间线"),
        ]
        current_scope = self.config.get("context_scope", ["current_chapter", "outline", "characters"])
        for key, label in ctx_options:
            cb = QCheckBox(label)
            cb.setChecked(key in current_scope)
            self.context_checks[key] = cb
            ctx_layout.addWidget(cb)

        ctx_layout.addWidget(QLabel("注意：AI 只能读取不能修改原文。"))
        layout.addWidget(ctx_group)

        # ── 系统提示词 ──
        prompt_group = QGroupBox("系统提示词（可选）")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "自定义 AI 的行为提示词。留空使用默认提示词。"
        )
        self.prompt_edit.setPlainText(self.config.get("system_prompt", ""))
        self.prompt_edit.setMaximumHeight(100)
        prompt_layout.addWidget(self.prompt_edit)

        layout.addWidget(prompt_group)

        layout.addStretch()

        # ── 按钮 ──
        btn_layout = QHBoxLayout()

        test_btn = QPushButton("测试连接")
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #e8e8e8; border: 1px solid #d0d0d0;
                border-radius: 4px; padding: 6px 16px;
            }
            QPushButton:hover { background-color: #dcdcdc; }
        """)
        test_btn.clicked.connect(self._on_test)
        btn_layout.addWidget(test_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("保存设置")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 8px 24px; font-size: 13px;
            }
            QPushButton:hover { background-color: #3a7bc8; }
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_provider_changed(self, idx: int):
        self._update_models()
        provider_key = self.provider_combo.currentData()
        info = self.PROVIDER_INFO.get(provider_key, {})
        if not self.api_url_edit.text() or self.api_url_edit.text() in [
            v.get("default_url", "") for v in self.PROVIDER_INFO.values()
        ]:
            self.api_url_edit.setText(info.get("default_url", ""))
            self.api_url_edit.setPlaceholderText(info.get("url_hint", ""))

    def _update_models(self):
        self.model_combo.clear()
        provider_key = self.provider_combo.currentData()
        info = self.PROVIDER_INFO.get(provider_key, {})
        for m in info.get("models", []):
            self.model_combo.addItem(m, m)
        current = self.config.get("model")
        if current:
            idx = self.model_combo.findData(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

    def _on_test(self):
        """测试 API 连接是否有效。"""
        provider_key = self.provider_combo.currentData()
        api_key = self.api_key_edit.text().strip()
        api_url = self.api_url_edit.text().strip()
        model = self.model_combo.currentData()

        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        from ..editor.modules.ai_assistant.providers import create_provider

        try:
            provider = create_provider(provider_key, api_key, model, api_url)
            test_msg = [{"role": "user", "content": "回复'连接成功'四个字即可。"}]
            result = provider.send_message(test_msg)

            if "[错误]" in result:
                QMessageBox.warning(self, "连接失败", result)
            else:
                # 保存配置（连接成功自动存）
                ctx_scope = [k for k, cb in self.context_checks.items() if cb.isChecked()]
                self.config = {
                    "provider": provider_key,
                    "api_key": api_key,
                    "api_url": api_url,
                    "model": model,
                    "context_scope": ctx_scope,
                    "system_prompt": self.prompt_edit.toPlainText().strip(),
                }
                from .ai_config import save_ai_config
                save_ai_config(self.config)
                QMessageBox.information(self, "连接成功",
                    f"API 连接正常！\n回复内容：{result[:100]}")
        except Exception as e:
            QMessageBox.warning(self, "连接失败", f"请求出错：{e}")

    def _on_save(self):
        ctx_scope = [
            k for k, cb in self.context_checks.items() if cb.isChecked()
        ]
        self.config = {
            "provider": self.provider_combo.currentData(),
            "api_key": self.api_key_edit.text().strip(),
            "api_url": self.api_url_edit.text().strip(),
            "model": self.model_combo.currentData(),
            "context_scope": ctx_scope,
            "system_prompt": self.prompt_edit.toPlainText().strip(),
        }
        save_ai_config(self.config)
        QMessageBox.information(self, "成功", "AI 配置已保存")
