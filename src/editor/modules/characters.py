"""人物设定卡模块——管理角色信息、外貌、性格、关系网。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFormLayout, QSplitter,
    QMessageBox, QInputDialog, QGroupBox,
)

from .base_module import BaseModule


@dataclass
class Relationship:
    target_id: str = ""
    rel_type: str = ""


@dataclass
class Character:
    id: str = ""
    name: str = ""
    aliases: str = ""
    age: str = ""
    gender: str = ""
    occupation: str = ""
    appearance: str = ""
    personality: str = ""
    background: str = ""
    goals: str = ""
    notes: str = ""
    relationships: List[Relationship] = field(default_factory=list)


class CharacterModule(BaseModule):
    """人物设定卡数据管理。"""

    module_id = "characters"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "characters.json"
        self.characters: List[Character] = []
        self._dirty = False

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.characters = []
                for c in data.get("characters", []):
                    rels = []
                    for r in c.get("relationships", []):
                        rels.append(Relationship(**r))
                    c["relationships"] = rels
                    self.characters.append(Character(**c))
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"加载人物卡失败: {e}")
                self.characters = []
        if not self.characters:
            self.characters = []

    def save(self):
        try:
            data = {
                "characters": [
                    {**asdict(c), "relationships": [asdict(r) for r in c.relationships]}
                    for c in self.characters
                ]
            }
            self.data_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._dirty = False
            return True
        except OSError as e:
            print(f"保存人物卡失败: {e}")
            return False

    def add_character(self, name: str) -> Character:
        char = Character(
            id=uuid.uuid4().hex[:12],
            name=name,
        )
        self.characters.append(char)
        self._dirty = True
        return char

    def delete_character(self, char_id: str) -> bool:
        self.characters = [c for c in self.characters if c.id != char_id]
        self._dirty = True
        return True

    def get_character(self, char_id: str) -> Optional[Character]:
        for c in self.characters:
            if c.id == char_id:
                return c
        return None

    def update_character(self, char_id: str, **fields) -> bool:
        char = self.get_character(char_id)
        if not char:
            return False
        for k, v in fields.items():
            if hasattr(char, k):
                setattr(char, k, v)
        self._dirty = True
        return True

    def add_relationship(self, char_id: str, target_id: str, rel_type: str = "") -> bool:
        char = self.get_character(char_id)
        if not char:
            return False
        char.relationships.append(Relationship(target_id=target_id, rel_type=rel_type))
        self._dirty = True
        return True

    def remove_relationship(self, char_id: str, target_id: str) -> bool:
        char = self.get_character(char_id)
        if not char:
            return False
        char.relationships = [r for r in char.relationships if r.target_id != target_id]
        self._dirty = True
        return True

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        for c in self.characters:
            fields = [c.name, c.aliases, c.notes, c.background]
            if any(q in f.lower() for f in fields):
                results.append((c.name, f"人物设定卡", c.id))
        return results

    def create_dock_widget(self) -> QDockWidget:
        return CharacterDock(self, None)


class CharacterDock(QDockWidget):
    """人物设定卡 UI 面板。"""

    def __init__(self, module: CharacterModule, parent=None):
        super().__init__("👤 人物设定卡", parent)
        self.module = module
        self._setup_ui()
        self._load_list()

    def _setup_ui(self):
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea |
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setMinimumWidth(300)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 添加按钮
        add_btn = QPushButton("+ 添加人物")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9; color: white; border: none;
                border-radius: 4px; padding: 6px; font-size: 12px;
            }
            QPushButton:hover { background-color: #3a7bc8; }
            QPushButton:disabled { color: #aaaaaa; }
        """)
        add_btn.clicked.connect(self._on_add)
        layout.addWidget(add_btn)

        # 分割：左侧列表，右侧详情
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 角色列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""QListWidget::item { padding: 6px; }""")
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.list_widget)

        # 详情编辑区
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        form.setSpacing(4)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("姓名")
        form.addRow("姓名:", self.name_edit)

        self.aliases_edit = QLineEdit()
        self.aliases_edit.setPlaceholderText("别名/昵称")
        form.addRow("别名:", self.aliases_edit)

        from PySide6.QtWidgets import QComboBox
        age_layout = QHBoxLayout()
        self.age_edit = QLineEdit()
        self.age_edit.setPlaceholderText("年龄")
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["男", "女", "其他", "未设置"])
        self.gender_combo.setStyleSheet("""
            QComboBox { background-color: #ffffff; color: #333333; border: 1px solid #d0d0d0; border-radius: 4px; padding: 4px; }
            QComboBox QAbstractItemView { background-color: #ffffff; color: #333333; selection-background-color: #e8f0fe; selection-color: #333333; }
        """)
        age_layout.addWidget(self.age_edit)
        age_layout.addWidget(self.gender_combo)
        form.addRow("年龄/性别:", age_layout)

        self.occ_edit = QLineEdit()
        self.occ_edit.setPlaceholderText("职业/身份")
        form.addRow("职业:", self.occ_edit)

        form.addRow("外貌:", QLabel(""))
        self.appearance_edit = QTextEdit()
        self.appearance_edit.setMaximumHeight(60)
        self.appearance_edit.setPlaceholderText("外貌描述...")
        form.addRow(self.appearance_edit)

        form.addRow("性格:", QLabel(""))
        self.personality_edit = QTextEdit()
        self.personality_edit.setMaximumHeight(60)
        self.personality_edit.setPlaceholderText("性格描述...")
        form.addRow(self.personality_edit)

        form.addRow("背景:", QLabel(""))
        self.background_edit = QTextEdit()
        self.background_edit.setMaximumHeight(80)
        self.background_edit.setPlaceholderText("背景故事...")
        form.addRow(self.background_edit)

        form.addRow("目标:", QLabel(""))
        self.goals_edit = QTextEdit()
        self.goals_edit.setMaximumHeight(60)
        self.goals_edit.setPlaceholderText("动机/目标...")
        form.addRow(self.goals_edit)

        form.addRow("备注:", QLabel(""))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        self.notes_edit.setPlaceholderText("自由备注...")
        form.addRow(self.notes_edit)

        detail_layout.addLayout(form)

        # 保存按钮
        save_btn = QPushButton("💾 保存修改")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50; color: white; border: none;
                border-radius: 4px; padding: 6px; font-size: 12px;
            }
            QPushButton:hover { background-color: #43a047; }
        """)
        save_btn.clicked.connect(self._on_save)
        detail_layout.addWidget(save_btn)

        delete_btn = QPushButton("🗑 删除此人物")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white; border: none;
                border-radius: 4px; padding: 6px; font-size: 12px;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        delete_btn.clicked.connect(self._on_delete)
        detail_layout.addWidget(delete_btn)

        detail_layout.addStretch()

        splitter.addWidget(detail_widget)
        splitter.setSizes([150, 400])
        layout.addWidget(splitter, stretch=1)

        self.setWidget(widget)
        self._current_id = None

    def _load_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for c in self.module.characters:
            item = QListWidgetItem(c.name or "(未命名)")
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    def _on_selection_changed(self, row: int):
        if row < 0:
            return
        item = self.list_widget.item(row)
        if not item:
            return
        char_id = item.data(Qt.ItemDataRole.UserRole)
        char = self.module.get_character(char_id)
        if char:
            self._current_id = char.id
            self.name_edit.setText(char.name)
            self.aliases_edit.setText(char.aliases)
            self.age_edit.setText(char.age)
            idx = self.gender_combo.findText(char.gender)
            if idx >= 0:
                self.gender_combo.setCurrentIndex(idx)
            self.occ_edit.setText(char.occupation)
            self.appearance_edit.setPlainText(char.appearance)
            self.personality_edit.setPlainText(char.personality)
            self.background_edit.setPlainText(char.background)
            self.goals_edit.setPlainText(char.goals)
            self.notes_edit.setPlainText(char.notes)

    def _on_add(self):
        name, ok = QInputDialog.getText(self, "添加人物", "人物名称:")
        if ok and name.strip():
            char = self.module.add_character(name.strip())
            self._load_list()
            # 选中新建的角色
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == char.id:
                    self.list_widget.setCurrentRow(i)
                    break

    def _on_save(self):
        if not self._current_id:
            return
        self.module.update_character(
            self._current_id,
            name=self.name_edit.text(),
            aliases=self.aliases_edit.text(),
            age=self.age_edit.text(),
            gender=self.gender_combo.currentText(),
            occupation=self.occ_edit.text(),
            appearance=self.appearance_edit.toPlainText(),
            personality=self.personality_edit.toPlainText(),
            background=self.background_edit.toPlainText(),
            goals=self.goals_edit.toPlainText(),
            notes=self.notes_edit.toPlainText(),
        )
        self.module.save()
        self._load_list()

    def _on_delete(self):
        if not self._current_id:
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定删除此人物设定？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.module.delete_character(self._current_id)
            self.module.save()
            self._current_id = None
            self._load_list()
            # 清空详情
            self.name_edit.clear()
            self.aliases_edit.clear()
            self.age_edit.clear()
            self.occ_edit.clear()
            self.appearance_edit.clear()
            self.personality_edit.clear()
            self.background_edit.clear()
            self.goals_edit.clear()
            self.notes_edit.clear()
