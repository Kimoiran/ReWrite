"""全局搜索对话框——Ctrl+Shift+F 跨模块搜索。"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
)


class SearchDialog(QDialog):
    """全局搜索浮窗。"""

    result_selected = Signal(str, str)  # module_id, ref_data

    def __init__(self, modules: dict, parent=None):
        """
        modules: dict[str, BaseModule] — 已激活的模块 {module_id: instance}
        """
        super().__init__(parent)
        self.modules = modules
        self._all_results = []  # [(title, description, module_id, ref_data)]
        self._setup_ui()
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._do_search)

    def _setup_ui(self):
        self.setWindowTitle("搜索")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Popup |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(480, 400)
        self.setStyleSheet("""
            SearchDialog {
                border: 1px solid #e0e8f0;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索章节、人物、大纲、时间线...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #2196F3;
                border-radius: 8px;
                font-size: 14px;
            }
        """)
        search_font = QFont()
        search_font.setPointSize(13)
        self.search_input.setFont(search_font)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input)

        # 结果列表
        self.result_list = QListWidget()
        self.result_list.setStyleSheet("""
            QListWidget {
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px 12px;
            }
        """)
        self.result_list.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self.result_list, stretch=1)

        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("输入关键词开始搜索")
        self.status_label.setStyleSheet("color: #999999; font-size: 11px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.hint_label = QLabel("Esc 关闭")
        self.hint_label.setStyleSheet("color: #bbbbbb; font-size: 11px;")
        status_layout.addWidget(self.hint_label)

        layout.addLayout(status_layout)

    def _on_text_changed(self, text: str):
        self._debounce_timer.start()

    def _do_search(self):
        query = self.search_input.text().strip()
        self.result_list.clear()
        self._all_results = []

        if not query:
            self.status_label.setText("输入关键词开始搜索")
            return

        for mod_id, module in self.modules.items():
            if hasattr(module, "search"):
                try:
                    results = module.search(query)
                    for title, desc, ref in results:
                        self._all_results.append((title, desc, mod_id, ref))
                except Exception as e:
                    print(f"搜索模块 {mod_id} 出错: {e}")

        if not self._all_results:
            self.status_label.setText("未找到匹配结果")
            return

        # 按模块分组显示
        current_mod = None
        for title, desc, mod_id, ref in self._all_results:
            if mod_id != current_mod:
                current_mod = mod_id
                from . import MODULE_DISPLAY_NAMES
                display_name = MODULE_DISPLAY_NAMES.get(mod_id, mod_id)
                header_item = QListWidgetItem(f"── {display_name} ──")
                header_item.setFlags(Qt.ItemFlag.NoItemFlags)
                header_item.setData(Qt.ItemDataRole.UserRole, "__header__")
                font = QFont()
                font.setBold(True)
                font.setPointSize(11)
                header_item.setFont(font)
                header_item.setForeground(Qt.GlobalColor.gray)
                self.result_list.addItem(header_item)

            item = QListWidgetItem(f"{title}  —  {desc}")
            item.setData(Qt.ItemDataRole.UserRole, f"{mod_id}||{ref}")
            self.result_list.addItem(item)

        self.status_label.setText(f"找到 {len(self._all_results)} 条结果")

    def _on_item_activated(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data != "__header__":
            mod_id, ref = data.split("||", 1)
            self.result_selected.emit(mod_id, ref)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return:
            item = self.result_list.currentItem()
            if item:
                self._on_item_activated(item)
        elif event.key() == Qt.Key.Key_Down:
            self.result_list.setCurrentRow(
                min(self.result_list.currentRow() + 1, self.result_list.count() - 1)
            )
        elif event.key() == Qt.Key.Key_Up:
            self.result_list.setCurrentRow(max(self.result_list.currentRow() - 1, 0))
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
