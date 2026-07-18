"""记忆编辑对话框 — 允许用户逐条查看、修改和删除对话记忆。"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton,
                               QHBoxLayout, QLabel, QMessageBox)


class MemoryEditor:
    """记忆编辑器。从 agent 读取 history，编辑后写回。"""

    def __init__(self, agent, chat_panel):
        self.agent = agent
        self.chat_panel = chat_panel

    def exec(self, parent=None):
        h = self.agent.history
        if not h:
            QMessageBox.information(parent, "编辑记忆", "当前没有对话记录")
            return

        d = QDialog(parent)
        d.setWindowTitle("编辑记忆")
        d.setMinimumSize(700, 500)
        lo = QVBoxLayout(d)
        lo.addWidget(QLabel(f"共 {len(h)} 条记录。每行一条，格式：角色|内容。可编辑、删除行。"))

        te = QTextEdit()
        lines = []
        for m in h:
            role = "用户" if m.get("role") == "user" else "AI"
            content = m.get("content", "").replace("\n", "\\n")
            lines.append(f"{role}|{content}")
        te.setPlainText("\n".join(lines))
        te.setStyleSheet("font-size:12px;font-family:Microsoft YaHei;line-height:1.4;")
        lo.addWidget(te, stretch=1)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存修改")
        save_btn.clicked.connect(lambda: _save())
        btn_row.addWidget(save_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(d.reject)
        btn_row.addWidget(cancel_btn)
        lo.addLayout(btn_row)

        def _save():
            new_h = []
            for line in te.toPlainText().split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|", 1)
                if len(parts) == 2:
                    r = "user" if parts[0].strip() == "用户" else "assistant"
                    new_h.append({"role": r, "content": parts[1].replace("\\n", "\n")})
            if new_h:
                self.agent.history = new_h
                self.agent._persist()
                self.chat_panel._on_clear()
                from .orchestrator import AIOrchestrator
                for msg in new_h:
                    self.chat_panel.add_message(msg["role"], AIOrchestrator.render_message(msg["content"]))
                self.chat_panel.update_memory(len(new_h))
                d.accept()
            else:
                QMessageBox.warning(d, "错误", "至少需要保留一条记录")

        d.exec()
