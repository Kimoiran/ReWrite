"""导入对话框 — 支持从 ZIP 导入 / 从 Git 仓库导入。"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QRadioButton, QMessageBox,
    QFileDialog, QWidget, QStackedWidget,
)


class ImportDialog(QDialog):
    """导入对话框，选择 ZIP 导入或 Git 仓库导入。"""

    def __init__(self, works_dir: Path, parent=None):
        super().__init__(parent)
        self.works_dir = works_dir
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("导入作品")
        self.setMinimumSize(450, 280)
        self.resize(500, 320)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 来源选择
        source_group = QGroupBox("导入来源")
        source_layout = QVBoxLayout(source_group)

        self.radio_zip = QRadioButton("从 ZIP 文件导入（.writepack / .zip）")
        self.radio_zip.setChecked(True)
        self.radio_zip.toggled.connect(lambda chk: self._on_switch() if chk else None)
        source_layout.addWidget(self.radio_zip)

        self.radio_git = QRadioButton("从 Git 仓库克隆（GitHub / Git 地址）")
        self.radio_git.toggled.connect(lambda chk: self._on_switch() if chk else None)
        source_layout.addWidget(self.radio_git)

        layout.addWidget(source_group)

        # ── ZIP 导入面板 ──
        self.zip_panel = QWidget()
        zip_layout = QVBoxLayout(self.zip_panel)
        zip_layout.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        self.zip_path_edit = QLineEdit()
        self.zip_path_edit.setPlaceholderText("选择 .writepack 或 .zip 文件...")
        file_row.addWidget(self.zip_path_edit, stretch=1)

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_zip)
        file_row.addWidget(browse_btn)

        zip_layout.addLayout(file_row)

        self.zip_name_edit = QLineEdit()
        self.zip_name_edit.setPlaceholderText("作品名称（留空使用压缩包内的名称）")
        zip_layout.addWidget(self.zip_name_edit)

        layout.addWidget(self.zip_panel)

        # ── Git 导入面板 ──
        self.git_panel = QWidget()
        self.git_panel.setVisible(False)
        git_layout = QVBoxLayout(self.git_panel)
        git_layout.setContentsMargins(0, 0, 0, 0)

        self.git_url_edit = QLineEdit()
        self.git_url_edit.setPlaceholderText("https://github.com/用户名/仓库名.git")
        git_layout.addWidget(self.git_url_edit)

        self.git_name_edit = QLineEdit()
        self.git_name_edit.setPlaceholderText("作品名称（留空使用仓库名）")
        git_layout.addWidget(self.git_name_edit)

        git_info = QLabel(
            "需要先配置 Git，首次克隆会要求认证。\n"
            "私有仓库需要在设置中配置 GitHub Token。"
        )
        git_info.setStyleSheet("font-size: 11px; color: #8a9aaa;")
        git_info.setWordWrap(True)
        git_layout.addWidget(git_info)

        layout.addWidget(self.git_panel)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("background-color: #e0e0e0; color: #333;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.import_btn = QPushButton("导入")
        self.import_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(self.import_btn)

        layout.addLayout(btn_layout)

    def _on_switch(self):
        self.zip_panel.setVisible(self.radio_zip.isChecked())
        self.git_panel.setVisible(self.radio_git.isChecked())

    def _browse_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择导入文件", "",
            "ZIP 或 Writepack (*.zip *.writepack);;所有文件 (*)"
        )
        if path:
            self.zip_path_edit.setText(path)

    def _on_import(self):
        if self.radio_zip.isChecked():
            path = self.zip_path_edit.text().strip()
            if not path:
                QMessageBox.warning(self, "提示", "请选择要导入的文件")
                return
            if not Path(path).exists():
                QMessageBox.warning(self, "提示", "文件不存在")
                return
            self._result = {
                "type": "zip",
                "path": path,
                "name": self.zip_name_edit.text().strip(),
            }
        else:
            url = self.git_url_edit.text().strip()
            if not url:
                QMessageBox.warning(self, "提示", "请输入 Git 仓库地址")
                return
            self._result = {
                "type": "git",
                "url": url,
                "name": self.git_name_edit.text().strip(),
            }
        self.accept()

    def get_result(self) -> dict:
        return getattr(self, "_result", None)
