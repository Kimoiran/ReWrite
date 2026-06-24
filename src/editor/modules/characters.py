"""人物设定卡模块——多级分组，支持 AI 编辑。"""

import json
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFormLayout, QMenu, QMessageBox, QInputDialog,
)
from PySide6.QtGui import QAction

from .base_module import BaseModule


@dataclass
class Relationship:
    target_id: str = ""
    rel_type: str = ""


@dataclass
class CharNode:
    id: str = ""
    name: str = ""
    is_group: bool = False
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
    children: List["CharNode"] = field(default_factory=list)


class CharacterModule(BaseModule):
    module_id = "characters"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.data_path = work_path / "characters.json"
        self.nodes: List[CharNode] = []

    def _node_to_dict(self, n: CharNode) -> dict:
        d = asdict(n)
        d["children"] = [self._node_to_dict(c) for c in n.children]
        return d

    def _dict_to_node(self, d: dict) -> CharNode:
        children = [self._dict_to_node(c) for c in d.get("children", [])]
        rels = [Relationship(**r) for r in d.get("relationships", [])]
        return CharNode(
            id=d.get("id", uuid.uuid4().hex[:12]),
            name=d.get("name", ""),
            is_group=d.get("is_group", False),
            aliases=d.get("aliases", ""),
            age=d.get("age", ""),
            gender=d.get("gender", ""),
            occupation=d.get("occupation", ""),
            appearance=d.get("appearance", ""),
            personality=d.get("personality", ""),
            background=d.get("background", ""),
            goals=d.get("goals", ""),
            notes=d.get("notes", ""),
            relationships=rels,
            children=children,
        )

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                raw = data.get("nodes")
                if raw is None and "characters" in data:
                    raw = data["characters"]
                if raw:
                    self.nodes = [self._dict_to_node(n) for n in raw]
                    return
            except Exception as e:
                print(f"加载人物卡失败: {e}")
        self.nodes = []

    def save(self):
        try:
            data = {"nodes": [self._node_to_dict(n) for n in self.nodes]}
            self.data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except OSError as e:
            print(f"保存人物卡失败: {e}")
            return False

    def _find_node(self, nodes: list, node_id: str) -> Optional[CharNode]:
        for n in nodes:
            if n.id == node_id:
                return n
            if n.children:
                found = self._find_node(n.children, node_id)
                if found:
                    return found
        return None

    def _find_parent_list(self, nodes: list, node_id: str) -> Optional[list]:
        for i, n in enumerate(nodes):
            if n.id == node_id:
                return nodes
            if n.children:
                parent = self._find_parent_list(n.children, node_id)
                if parent is not None:
                    return parent
        return None

    def add_group(self, name: str, parent_id: str = "") -> Optional[CharNode]:
        node = CharNode(id=uuid.uuid4().hex[:12], name=name, is_group=True)
        if parent_id:
            parent = self._find_node(self.nodes, parent_id)
            if parent:
                parent.children.append(node)
                return node
        self.nodes.append(node)
        return node

    def add_character(self, name: str, parent_id: str = "") -> Optional[CharNode]:
        node = CharNode(id=uuid.uuid4().hex[:12], name=name, is_group=False)
        if parent_id:
            parent = self._find_node(self.nodes, parent_id)
            if parent:
                parent.children.append(node)
                return node
        self.nodes.append(node)
        return node

    def insert_sibling_after(self, node_id: str, name: str, is_group: bool) -> Optional[CharNode]:
        """在指定节点后插入同级节点。"""
        parent_list = self._find_parent_list(self.nodes, node_id)
        if parent_list is None:
            return None
        idx = next((i for i, n in enumerate(parent_list) if n.id == node_id), -1)
        if idx < 0:
            return None
        node = CharNode(id=uuid.uuid4().hex[:12], name=name, is_group=is_group)
        parent_list.insert(idx + 1, node)
        return node

    def delete_node(self, node_id: str) -> bool:
        parent_list = self._find_parent_list(self.nodes, node_id)
        if parent_list is None:
            return False
        for i, n in enumerate(parent_list):
            if n.id == node_id:
                parent_list.pop(i)
                return True
        return False

    def update_node(self, node_id: str, **fields) -> bool:
        node = self._find_node(self.nodes, node_id)
        if not node:
            return False
        for k, v in fields.items():
            if hasattr(node, k) and v is not None:
                setattr(node, k, v)
        return True

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        def _search(nodes):
            for n in nodes:
                if q in n.name.lower() or q in n.notes.lower() or q in n.background.lower():
                    label = "分组" if n.is_group else "人物"
                    results.append((n.name, f"人物设定卡 ({label})", n.id))
                _search(n.children)
        _search(self.nodes)
        return results

    # AI 编辑接口
    def apply_edit(self, target_name: str, field: str, value: str) -> tuple[bool, str]:
        """AI 编辑人物卡字段。field 是字段名，value 是新值。"""
        VALID_FIELDS = {"aliases", "age", "gender", "occupation", "appearance",
                        "personality", "background", "goals", "notes", "name"}
        if field not in VALID_FIELDS:
            return False, f"不支持修改字段「{field}」，支持: {', '.join(sorted(VALID_FIELDS))}"
        target = None
        def _find(nodes):
            for n in nodes:
                if n.name == target_name and not n.is_group:
                    return n
                found = _find(n.children)
                if found:
                    return found
            return None
        target = _find(self.nodes)
        if not target:
            return False, f"未找到角色「{target_name}」"
        setattr(target, field, value)
        self.save()
        return True, f"已修改 {target_name} 的 {field}"

    def batch_import(self, text: str) -> tuple[int, int, list[str]]:
        """从 AI 输出的结构化文本批量导入人物和分组。
        返回 (分组数, 角色数, 错误列表)。"""
        import re as _re
        groups = 0
        chars = 0
        errors = []
        current_group = None  # CharNode

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            # 📁 分组: xxx
            m = _re.match(r"📁\s*分组[：:]\s*(.+)", stripped)
            if m:
                name = m.group(1).strip()
                current_group = self.add_group(name)
                groups += 1
                continue

            # 👤 人物: xxx
            m = _re.match(r"👤\s*人物[：:]\s*(.+)", stripped)
            if m:
                name = m.group(1).strip().rstrip("，,")
                parent_id = current_group.id if current_group else ""
                node = self.add_character(name, parent_id)
                if node:
                    chars += 1
                    current_group = current_group  # keep group
                else:
                    errors.append(f"无法创建角色: {name}")
                continue

            # 字段行: 年龄=xxx 或 外貌: xxx
            if current_group and chars > 0:
                # 找到最后一个添加的角色
                target = self._find_node(self.nodes, "")
                def _last_char(nodes):
                    for n in reversed(nodes):
                        if not n.is_group:
                            return n
                        if n.children:
                            r = _last_char(n.children)
                            if r:
                                return r
                    return None
                last = _last_char(self.nodes) if chars > 0 else None
                if last:
                    # 年龄=xxx
                    m = _re.match(r"(\w+)[=：:]\s*(.+)", stripped)
                    if m:
                        field = m.group(1).strip().lower()
                        value = m.group(2).strip()
                        _FIELD_MAP = {
                            "年龄": "age", "age": "age",
                            "性别": "gender", "gender": "gender",
                            "身份": "occupation", "职业": "occupation",
                            "外貌": "appearance", "appearance": "appearance",
                            "性格": "personality", "personality": "personality",
                            "背景": "background", "background": "background",
                            "目标": "goals", "goals": "goals",
                            "备注": "notes", "notes": "notes",
                            "别名": "aliases", "aliases": "aliases",
                        }
                        py_field = _FIELD_MAP.get(field, field)
                        if py_field in ("age","gender","occupation","appearance","personality","background","goals","notes","aliases"):
                            setattr(last, py_field, value)

        self.save()
        return groups, chars, errors

    def create_dock_widget(self) -> QDockWidget:
        return CharacterDock(self, None)


class CharTreeItem(QTreeWidgetItem):
    def __init__(self, node: CharNode, parent=None):
        super().__init__(parent)
        self.node_id = node.id
        self.is_group = node.is_group
        icon = "📁 " if node.is_group else "👤 "
        self.setText(0, f"{icon}{node.name}")
        self.setData(0, Qt.ItemDataRole.UserRole, node.id)
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsEditable)


class CharacterDock(QDockWidget):
    def __init__(self, module: CharacterModule, parent=None):
        super().__init__("人物设定卡", parent)
        self.module = module
        self._current_id = None
        self._renaming = False
        self._setup_ui()
        self._build_tree()

    def _setup_ui(self):
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea |
            Qt.DockWidgetArea.TopDockWidgetArea | Qt.DockWidgetArea.BottomDockWidgetArea
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

        btn_row = QHBoxLayout()
        add_char_btn = QPushButton("+ 角色")
        add_char_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        add_char_btn.clicked.connect(self._on_add_character)
        btn_row.addWidget(add_char_btn)

        add_group_btn = QPushButton("+ 分组")
        add_group_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        add_group_btn.clicked.connect(self._on_add_group)
        btn_row.addWidget(add_group_btn)

        delete_btn = QPushButton("🗑")
        delete_btn.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        import_btn = QPushButton("📥 批量导入")
        import_btn.setStyleSheet("font-size: 10px; padding: 4px 8px; border: 1px solid #4CAF50; color: #2E7D32;")
        import_btn.clicked.connect(self._on_batch_import)
        btn_row.addWidget(import_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["分组 / 角色"])
        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.DoubleClicked | QTreeWidget.EditTrigger.EditKeyPressed
        )
        self.tree.setStyleSheet("""
            QTreeWidget::item { padding: 4px 0; min-height: 24px; }
            QTreeWidget QLineEdit { min-height: 28px; padding: 2px 6px; }
        """)
        self.tree.itemChanged.connect(self._on_item_edited)
        self.tree.currentItemChanged.connect(self._on_selection_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.tree, stretch=1)

        # 详情编辑区
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_title = QLabel("选中角色查看详情")
        self.detail_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #1a2332;")
        detail_layout.addWidget(self.detail_title)

        form = QFormLayout()
        form.setSpacing(2)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("姓名")
        form.addRow("姓名:", self.name_edit)

        self.aliases_edit = QLineEdit()
        self.aliases_edit.setPlaceholderText("别名/昵称")
        form.addRow("别名:", self.aliases_edit)

        age_gender = QHBoxLayout()
        self.age_edit = QLineEdit()
        self.age_edit.setPlaceholderText("年龄")
        from PySide6.QtWidgets import QComboBox
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["男", "女", "其他", "未设置"])
        age_gender.addWidget(self.age_edit)
        age_gender.addWidget(self.gender_combo)
        form.addRow("年龄/性别:", age_gender)

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

        save_btn = QPushButton("保存修改")
        save_btn.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        save_btn.clicked.connect(self._on_save)
        detail_layout.addWidget(save_btn)

        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)

        self.setWidget(widget)

    def _save_expanded(self) -> set:
        """保存当前展开的节点 ID。"""
        expanded = set()
        def _walk(item):
            if item.isExpanded():
                nid = item.data(0, Qt.ItemDataRole.UserRole)
                if nid:
                    expanded.add(nid)
            for i in range(item.childCount()):
                _walk(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            _walk(self.tree.topLevelItem(i))
        return expanded

    def _restore_expanded(self, expanded: set):
        """恢复展开的节点。"""
        def _walk(item):
            nid = item.data(0, Qt.ItemDataRole.UserRole)
            if nid and nid in expanded:
                item.setExpanded(True)
            for i in range(item.childCount()):
                _walk(item.child(i))
        for i in range(self.tree.topLevelItemCount()):
            _walk(self.tree.topLevelItem(i))

    def _build_tree(self, keep_expanded=True):
        """重建树，默认保持展开状态。"""
        expanded = self._save_expanded() if keep_expanded else set()
        self.tree.blockSignals(True)
        self.tree.clear()

        def _add(nodes, parent):
            for n in nodes:
                item = CharTreeItem(n, parent)
                if n.children:
                    _add(n.children, item)

        for n in self.module.nodes:
            item = CharTreeItem(n, self.tree)
            if n.children:
                _add(n.children, item)

        self.tree.blockSignals(False)
        if expanded:
            self._restore_expanded(expanded)

    def _get_node_id(self, item) -> str:
        return item.data(0, Qt.ItemDataRole.UserRole) or "" if item else ""

    def _on_add_group(self):
        item = self.tree.currentItem()
        parent_id = self._get_node_id(item) if item else ""
        name, ok = QInputDialog.getText(self, "添加分组", "分组名称:")
        if ok and name.strip():
            self.module.add_group(name.strip(), parent_id)
            self.module.save()
            self._build_tree()

    def _on_add_character(self):
        item = self.tree.currentItem()
        parent_id = self._get_node_id(item) if item else ""
        name, ok = QInputDialog.getText(self, "添加人物", "人物名称:")
        if ok and name.strip():
            self.module.add_character(name.strip(), parent_id)
            self.module.save()
            self._build_tree()

    def _on_delete(self):
        item = self.tree.currentItem()
        if not item:
            return
        nid = self._get_node_id(item)
        node = self.module._find_node(self.module.nodes, nid)
        if not node:
            return
        label = "分组" if node.is_group else "人物"
        reply = QMessageBox.question(self, "确认删除",
            f"删除{label}「{node.name}」？\n子级也会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.module.delete_node(nid)
            self.module.save()
            if self._current_id == nid:
                self._current_id = None
                self.detail_widget.setVisible(False)
            self._build_tree()

    def _on_batch_import(self):
        """批量导入 AI 输出的人物数据。"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLabel, QDialogButtonBox, QMessageBox

        dialog = QDialog(self)
        dialog.setWindowTitle("批量导入人物/分组")
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("粘贴 AI 生成的人物数据（支持「📁 分组」和「👤 人物」格式）："))

        editor = QTextEdit()
        editor.setPlaceholderText(
            "📁 分组: 水神\n"
            "👤 人物: 克诺\n"
            "    年龄=约十岁\n"
            "    性别=男\n"
            "    身份=水神代行者\n"
            "    外貌: 偏瘦...\n"
        )
        layout.addWidget(editor, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        text = editor.toPlainText()
        if not text.strip():
            return

        groups, chars, errors = self.module.batch_import(text)
        self._build_tree()
        msg = f"导入完成：{groups} 个分组，{chars} 个角色"
        if errors:
            msg += "\n\n错误：\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "导入结果", msg)

    def _on_selection_changed(self, current, previous):
        nid = self._get_node_id(current)
        node = self.module._find_node(self.module.nodes, nid) if nid else None
        if node and not node.is_group:
            self.detail_widget.setVisible(True)
            self._current_id = node.id
            self.detail_title.setText(f"✏ {node.name}")
            self.name_edit.setText(node.name)
            self.aliases_edit.setText(node.aliases)
            self.age_edit.setText(node.age)
            idx = self.gender_combo.findText(node.gender)
            if idx >= 0:
                self.gender_combo.setCurrentIndex(idx)
            self.occ_edit.setText(node.occupation)
            self.appearance_edit.setPlainText(node.appearance)
            self.personality_edit.setPlainText(node.personality)
            self.background_edit.setPlainText(node.background)
            self.goals_edit.setPlainText(node.goals)
            self.notes_edit.setPlainText(node.notes)
        else:
            self.detail_widget.setVisible(False)
            self._current_id = None

    def _on_item_edited(self, item, column):
        """双击编辑标题完成时保存。"""
        if self._renaming:
            return
        self._renaming = True
        nid = self._get_node_id(item)
        raw = item.text(column).strip()
        if nid and raw:
            self.module.update_node(nid, name=raw)
            self.module.save()
            # 重建树以刷新显示，保留展开状态
            expanded = self._save_expanded()
            self._build_tree(keep_expanded=False)
            self._restore_expanded(expanded)
        self._renaming = False

    def _on_save(self):
        if self._current_id:
            self.module.update_node(
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

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        nid = self._get_node_id(item)
        node = self.module._find_node(self.module.nodes, nid) if nid else None
        if not node:
            return

        menu = QMenu(self)
        add_char = menu.addAction("在此下添加角色")
        add_group = menu.addAction("在此下添加分组")
        menu.addSeparator()
        add_sibling = menu.addAction("在此后添加同级")
        menu.addSeparator()
        rename_act = menu.addAction("重命名")
        delete_act = menu.addAction("删除")

        action = menu.exec(self.tree.mapToGlobal(pos))

        if action == add_char:
            name, ok = QInputDialog.getText(self, "添加人物", "人物名称:")
            if ok and name.strip():
                self.module.add_character(name.strip(), nid)
                self.module.save()
                self._build_tree()
        elif action == add_group:
            name, ok = QInputDialog.getText(self, "添加分组", "分组名称:")
            if ok and name.strip():
                self.module.add_group(name.strip(), nid)
                self.module.save()
                self._build_tree()
        elif action == add_sibling:
            title = "添加同级角色" if node.is_group else "添加同级角色"
            name, ok = QInputDialog.getText(self, "添加同级", "名称:")
            if ok and name.strip():
                self.module.insert_sibling_after(nid, name.strip(), is_group=False)
                self.module.save()
                self._build_tree()
        elif action == rename_act:
            self.tree.editItem(item, 0)
        elif action == delete_act:
            self._on_delete()
