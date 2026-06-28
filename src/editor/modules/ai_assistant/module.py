"""AI 助手模块 — 两个独立 Dock：对话 + 批注，均支持多模块。"""

from pathlib import Path

import urllib.error
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDockWidget, QMessageBox

from ..base_module import BaseModule
from .agent import AIAgent
from .annotation_manager import AnnotationManager
from .ui.chat_panel import ChatPanel
from .ui.annotation_list import AnnotationListPanel

from src.settings.ai_config import load_ai_config


class AIAssistantModule(BaseModule):
    """AI 写作助手模块。"""

    module_id = "ai_assistant"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.config = load_ai_config()
        self.agent = AIAgent(self.config, work_name=work_path.name)
        self.annotation_mgr = AnnotationManager(work_path)
        self.annotation_mgr.load()
        self._editor = None

    def load(self):
        self.annotation_mgr.load()

    def save(self):
        self.annotation_mgr.save()

    def set_editor(self, editor):
        self._editor = editor

    def get_context(self, scope: str) -> str:
        from .contexts import collect_context
        html = ""
        sel = ""
        if self._editor:
            html = self._editor.get_html()
            cursor = self._editor.textCursor()
            if cursor.hasSelection():
                sel = cursor.selection().toHtml()
        parent = self.parent()
        wm = {}
        if hasattr(parent, '_work_meta') and parent._work_meta:
            m = parent._work_meta
            wm = {"title": getattr(m, 'title', ''), "work_type": getattr(m, 'work_type', ''),
                  "tags": getattr(m, 'tags', []), "total_words": getattr(m, 'total_words', 0)}
        return collect_context(
            scope=scope.split(","), current_html=html, current_selection=sel,
            chapter_module=self._get_module("chapters"),
            character_module=self._get_module("characters"),
            outline_module=self._get_module("outline"),
            timeline_module=self._get_module("timeline"),
            worldview_module=self._get_module("worldview"),
            work_meta=wm)

    def _get_module(self, mod_id):
        if self.parent() and hasattr(self.parent(), "modules"):
            return self.parent().modules.get(mod_id)
        return None

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        for ann in self.annotation_mgr.annotations:
            if q in ann.suggestion.lower() or q in ann.target_title.lower():
                tag = "已采纳" if ann.status == "accepted" else ("已忽略" if ann.status == "ignored" else "待处理")
                results.append((f"{ann.type_icon} {ann.target_title[:20]}", f"批注 ({ann.type_label})", ann.id))
        return results

    def create_dock_widget(self) -> QDockWidget:
        return self._make_chat_dock()

    def get_extra_docks(self) -> list[QDockWidget]:
        return [self._make_annotation_dock()]

    def _make_chat_dock(self) -> QDockWidget:
        self.chat_panel = ChatPanel()
        self.chat_panel.send_message_signal.connect(self._on_chat_message)
        self.chat_panel.set_analyze_callback(self._on_analyze)
        from .markdown_render import markdown_to_html
        for msg in self.agent.history:
            r = msg.get("role", "user")
            c = msg.get("content", "")
            if c:
                self.chat_panel.add_message(r, markdown_to_html(c))
        self.chat_panel.update_memory(len(self.agent.history))
        self.chat_panel.set_undo_enabled(len(self.agent.history) >= 2)
        self.chat_panel.clear_btn.clicked.disconnect()
        self.chat_panel.clear_btn.clicked.connect(self._on_clear_memory)
        self.chat_panel.undo_requested.connect(self._on_undo)
        return self.chat_panel

    def _on_clear_memory(self):
        self.agent.clear_history()
        self.chat_panel._on_clear()
        self.chat_panel.update_memory(0)
        self.chat_panel.set_undo_enabled(False)

    def _on_undo(self):
        if self.agent.undo_last_message():
            self.chat_panel.remove_last_bubble()
            self.chat_panel.remove_last_bubble()
            self.chat_panel.update_memory(len(self.agent.history))
            self.chat_panel.set_undo_enabled(len(self.agent.history) >= 2)

    def _make_annotation_dock(self) -> QDockWidget:
        self.annotation_panel = AnnotationListPanel(self.annotation_mgr)
        self.annotation_panel.annotation_clicked.connect(self._on_annotation_clicked)
        return self.annotation_panel

    def _on_annotation_clicked(self, ann_id: str):
        for ann in self.annotation_mgr.annotations:
            if ann.id == ann_id:
                dk = self.parent().docks if hasattr(self.parent(), 'docks') else {}
                if ann.target_type in dk:
                    dk[ann.target_type].show()
                    dk[ann.target_type].raise_()
                break

    def _create_module_annotations(self, response: str):
        import re as _re
        cm = self._get_module("characters")
        om = self._get_module("outline")
        tm = self._get_module("timeline")
        cp = self._editor.current_chapter_path() if self._editor else None
        pl = self._editor.toPlainText() if self._editor else ""
        def _fp(q, p):
            i = p.find(q)
            if i >= 0:
                return (i, i + len(q))
            import re as _r2
            c = _r2.sub('[，。！？、；：""''「」【】（）《》]', '', q)
            pc = _r2.sub('[，。！？、；：""''「」【】（）《》]', '', p)
            i = pc.find(c)
            return (i, i + len(c)) if i >= 0 else (-1, -1)

        pat = r'\[ANNOTATION:(\w+):([^\]]+)\]\n?(.*?)\n?\[/ANNOTATION\]'
        ms = _re.findall(pat, response, _re.DOTALL)
        ok = False
        for t, ti, tc in ms:
            t, ti, tc = t.strip(), ti.strip(), (tc.strip() or response[:200])
            tp = ht = ""; sp = ep = -1
            if t == "chapter":
                tp = cp or ""
                qs = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', tc, _re.DOTALL)
                if qs:
                    ht = qs[0].strip(); sp, ep = _fp(ht, pl)
            elif t == "character" and cm:
                def _fc(ns):
                    for n in ns:
                        if not n.is_group and n.name == ti:
                            return n.id
                        if n.children:
                            r = _fc(n.children)
                            if r:
                                return r
                    return ""
                tp = _fc(cm.nodes)
            elif t == "outline" and om:
                def _fo(ns):
                    for e in ns:
                        if e.title == ti:
                            return e.id
                        if e.children:
                            r = _fo(e.children)
                            if r:
                                return r
                    return ""
                tp = _fo(om.entries)
            elif t == "timeline" and tm:
                for e in tm.events:
                    if e.title == ti:
                        tp = e.id; break
            if t in ("chapter", "character", "outline", "timeline"):
                self.annotation_mgr.add_annotation(target_type=t, target_path=tp or ti,
                    target_title=ti, suggestion=tc, highlight_text=ht, start_pos=sp, end_pos=ep)
                ok = True
        if not ok and cp:
            qs = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', response, _re.DOTALL)
            qt = qs[0].strip() if qs else ""
            sp, ep = _fp(qt, pl) if qt else (-1, -1)
            self.annotation_mgr.add_annotation(target_type="chapter", target_path=cp,
                target_title="当前章节", suggestion=response[:500], highlight_text=qt, start_pos=sp, end_pos=ep)
        self.annotation_mgr.save()
        self.annotation_panel.refresh()
        if self._editor and cp:
            self._editor.set_annotations(self.annotation_mgr.get_chapter_annotations(cp))

    def _on_chat_message(self, message: str, scope: str):
        if not self.agent.is_configured():
            self.chat_panel.add_message("assistant", "请先配置 AI 服务：菜单 -> 文件 -> 设置 -> AI 助手")
            self.chat_panel.enable_send()
            return
        ctx = self.get_context(scope)
        import os as _os
        if hasattr(self, 'work_path'):
            _os.environ["REWRITE_CURRENT_WORK"] = self.work_path.name
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, ctx))

    def _do_chat(self, message: str, context: str):
        from .worker import ToolProposalWorker

        # 走工具提案路径（含工具定义）
        self._proposal_worker = ToolProposalWorker(self.agent, message, context)
        self._proposal_worker.proposals_ready.connect(self._on_tool_proposals)
        self._proposal_worker.text_response.connect(self._on_ai_response)
        self._proposal_worker.reasoning_ready.connect(self._set_loading_reasoning)
        self._proposal_worker.api_error.connect(self._on_ai_error)
        self._proposal_worker.start()

    def _set_loading_reasoning(self, text: str):
        """在加载气泡中显示推理内容。"""
        if hasattr(self.chat_panel, '_loading_bubble') and self.chat_panel._loading_bubble:
            self.chat_panel._loading_bubble.set_reasoning(text)

    def _on_tool_proposals(self, tool_calls, before, after, system):
        """AI 返回了工具调用提案，在聊天气泡中嵌入确认按钮。"""
        from .skills.registry import get_skill, execute_skill
        from .providers import _ensure_work_args, _describe_tool
        import json as _j

        # 构建描述
        descs = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = _j.loads(tc.get("function", {}).get("arguments", "{}"))
            except Exception:
                args = {}
            _ensure_work_args(name, args)
            skill = get_skill(name)
            if skill and hasattr(skill, "summarize"):
                descs.append(skill.summarize({"success": True}, args))
            else:
                descs.append(f"执行 {name}")

        # 嵌入确认气泡
        bubble = self.chat_panel.add_confirm_bubble(descs, tool_calls)
        bubble.confirmed.connect(
            lambda tcs: self._execute_and_continue(tcs, after, system))
        bubble.cancelled.connect(self._on_cancel)

    def _on_cancel(self):
        """用户取消了操作。"""
        self.chat_panel.enable_send()

    def _show_diff_dialog(self, old_text: str, new_text: str, chapter_path: str) -> bool:
        """显示章节修改 diff 对比框。返回 True=接受 False=拒绝。"""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                       QPushButton, QSplitter, QTextBrowser, QApplication as _QA)
        from PySide6.QtCore import Qt as _Qt

        dialog = QDialog(_QA.activeWindow())
        dialog.setWindowTitle("确认章节修改")
        dialog.setMinimumSize(700, 450)
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)

        title = QLabel(f"章节修改确认: {chapter_path}")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px 0;")
        layout.addWidget(title)

        splitter = QSplitter(_Qt.Orientation.Horizontal)

        # 旧版（红）
        old_widget = QTextBrowser()
        old_widget.setHtml(old_text)
        old_widget.setStyleSheet("""
            QTextBrowser { background-color: #FFF5F5; border: 1px solid #FFCDD2;
                padding: 12px; font-size: 13px; line-height: 1.8; }
        """)
        old_label = QLabel("旧版")
        old_label.setStyleSheet("color: #C62828; font-weight: bold; font-size: 11px;")
        old_vbox = QVBoxLayout()
        old_vbox.addWidget(old_label)
        old_vbox.addWidget(old_widget)
        old_container = QWidget()
        old_container.setLayout(old_vbox)
        splitter.addWidget(old_container)

        # 新版（绿）
        new_widget = QTextBrowser()
        new_widget.setHtml(new_text)
        new_widget.setStyleSheet("""
            QTextBrowser { background-color: #F1F8E9; border: 1px solid #C8E6C9;
                padding: 12px; font-size: 13px; line-height: 1.8; }
        """)
        new_label = QLabel("新版")
        new_label.setStyleSheet("color: #2E7D32; font-weight: bold; font-size: 11px;")
        new_vbox = QVBoxLayout()
        new_vbox.addWidget(new_label)
        new_vbox.addWidget(new_widget)
        new_container = QWidget()
        new_container.setLayout(new_vbox)
        splitter.addWidget(new_container)

        layout.addWidget(splitter, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reject_btn = QPushButton("拒绝")
        reject_btn.setStyleSheet("padding: 8px 24px; border: 1px solid #EF5350; color: #C62828; border-radius: 4px;")
        reject_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(reject_btn)
        accept_btn = QPushButton("接受修改")
        accept_btn.setStyleSheet("padding: 8px 24px; background: #4CAF50; color: white; font-weight: bold; border-radius: 4px;")
        accept_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(accept_btn)
        layout.addLayout(btn_row)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _execute_and_continue(self, tool_calls, after, system):
        """用户确认后执行工具，然后继续 AI 循环。"""
        from .skills.registry import execute_skill
        from .providers import _ensure_work_args, _describe_tool
        from .skills.chapter_skills import UpdateChapterSkill
        import json as _j
        from PySide6.QtWidgets import QApplication as _QA

        _QA.processEvents()

        msgs = list(after)
        if msgs and msgs[-1].get("role") == "tool" and msgs[-1].get("tool_call_id") == "pending":
            msgs.pop()
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                a = _j.loads(tc.get("function", {}).get("arguments", "{}"))
            except Exception:
                a = {}
            _ensure_work_args(name, a)

            if name == "update_chapter":
                # 章节修改需要 diff 确认
                skill = UpdateChapterSkill()
                # 先读取旧内容
                from .skills._shared import _work_path as _wp
                work = _wp(a.get("work", ""))
                chapter = a.get("chapter", "")
                chapters_dir = work / "chapters"
                old_content = ""
                target_path = None
                if chapters_dir.exists():
                    for f in chapters_dir.iterdir():
                        display = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
                        if display == chapter or f.stem == chapter:
                            old_content = f.read_text(encoding="utf-8")
                            target_path = f
                            break

                new_content = a.get("content", "")
                if old_content and new_content and self._show_diff_dialog(old_content, new_content, str(target_path.name) if target_path else chapter):
                    # 接受修改，直接写文件
                    target_path.write_text(new_content, encoding="utf-8")
                    result = {"success": True, "chapter": chapter}
                else:
                    result = {"success": False, "error": "用户拒绝了修改"}
            else:
                result = execute_skill(name, a)

            msgs.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": _describe_tool(name, a, result)})
            # 显示执行结果
            from .markdown_render import markdown_to_html
            self.chat_panel.add_message("assistant",
                markdown_to_html(f"✅ {_describe_tool(name, a, result)}"))
            _QA.processEvents()

        # 立即刷新面板
        self._refresh_panels()

        # 继续 AI 循环
        self.chat_panel.show_loading()
        _QA.processEvents()
        self._tool_loop(msgs, system)

    def _tool_loop(self, messages: list, system: str):
        """把工具结果发给 AI，后台 HTTP 请求，不阻塞 UI。"""
        from PySide6.QtCore import QThread, Signal as _Sig
        from .providers import _make_chat_request, get_openai_tools

        agent_ref = self.agent
        module_ref = self

        class _LoopWorker(QThread):
            finished = _Sig(dict)
            error = _Sig(str)
            def run(self):
                try:
                    data = _make_chat_request(agent_ref, messages, system or "", get_openai_tools())
                    self.finished.emit(data)
                except urllib.error.HTTPError as e:
                    err = ""
                    try: err = e.read().decode("utf-8", errors="replace")[:200]
                    except Exception: pass
                    self.error.emit(f"API 错误 (HTTP {e.code}): {err}")
                except Exception as e:
                    self.error.emit(str(e))

        w = _LoopWorker()
        self._loop_worker = w

        def on_data(data):
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            c = msg.get("content") or ""
            tcs = msg.get("tool_calls", [])

            if not tcs:
                from .agent import save_chat_history
                agent_ref.history.append({"role": "assistant", "content": c})
                save_chat_history(agent_ref.work_name, agent_ref.history)
                module_ref._on_ai_response(c)
                return

            messages.append({"role": "assistant", "content": c,
                "tool_calls": [{"id": tc["id"], "type": "function",
                                "function": {"name": tc["function"]["name"],
                                             "arguments": tc["function"]["arguments"]}}
                               for tc in tcs]})

            from .skills.registry import get_skill
            from .providers import _ensure_work_args
            import json as _j
            module_ref.chat_panel.hide_loading()
            descs = []
            for tc in tcs:
                name = tc["function"]["name"]
                a = _j.loads(tc.get("function", {}).get("arguments", "{}")) if tc.get("function", {}).get("arguments") else {}
                _ensure_work_args(name, a)
                skill = get_skill(name)
                descs.append(skill.summarize({"success": True}, a) if skill and hasattr(skill, "summarize") else name)
            module_ref.chat_panel.add_confirm_bubble(descs, tcs).confirmed.connect(
                lambda tcs2: module_ref._execute_and_continue(tcs2, messages, system))

        w.finished.connect(on_data)
        w.error.connect(self._on_ai_error)
        w.start()


    def _on_ai_response(self, response: str):
        self.chat_panel.hide_loading()
        from .markdown_render import markdown_to_html
        self.chat_panel.add_message("assistant", markdown_to_html(response))
        self.chat_panel.enable_send()
        self.chat_panel.update_memory(len(self.agent.history))
        try:
            if self.agent.history and len(self.agent.history) >= 2:
                um = self.agent.history[-2].get("content", "")
                if isinstance(um, str) and any(k in um for k in ("分析", "批注", "建议", "评价")):
                    self._create_module_annotations(response)
        except Exception:
            pass
        self._refresh_panels()
        self._proposal_worker = None
        self._execute_worker = None

    def _on_ai_error(self, error_msg: str):
        self.chat_panel.hide_loading()
        self.chat_panel.add_message("assistant", f"[错误] {error_msg}")
        self.chat_panel.enable_send()
        self._proposal_worker = None
        self._execute_worker = None

    def _refresh_panels(self):
        """AI 可能通过工具修改了数据，刷新所有面板。"""
        p = self.parent()
        if not hasattr(p, 'modules'):
            return
        for mod_id, attr in [("characters", "_build_tree"), ("outline", "_build_tree"),
                              ("timeline", "_refresh"), ("worldview", "_build_tree")]:
            mod = p.modules.get(mod_id)
            if mod and hasattr(mod, 'load'):
                mod.load()
                dock = p.docks.get(mod_id)
                if dock and hasattr(dock, attr):
                    getattr(dock, attr)()

        # 单独处理章节：刷新侧栏列表 + 如果当前章节被改过则重载编辑器内容
        chap_mod = p.modules.get("chapters")
        if chap_mod and hasattr(chap_mod, 'load'):
            chap_mod.load()
            chap_list = getattr(p, 'chapter_list', None)
            if chap_list and hasattr(chap_list, '_refresh'):
                chap_list._refresh()
        # 重载当前编辑器内容（如果 AI 修改了当前章节）
        if self._editor:
            current_path = self._editor.current_chapter_path()
            if current_path and Path(current_path).exists():
                try:
                    new_html = Path(current_path).read_text(encoding="utf-8")
                    if new_html != self._editor.get_html():
                        cursor_pos = self._editor.textCursor().position()
                        self._editor.blockSignals(True)
                        self._editor.setHtml(new_html)
                        cursor = self._editor.textCursor()
                        cursor.setPosition(min(cursor_pos, len(new_html)))
                        self._editor.setTextCursor(cursor)
                        self._editor.blockSignals(False)
                except OSError:
                    pass

    def _on_analyze(self):
        if not self.agent.is_configured():
            QMessageBox.information(self.parent(), "提示", "请先在设置中配置 AI 服务")
            return
        ctx = self.get_context("current_chapter,outline,characters")
        msg = "请从情节、人物、节奏、语言等角度全面分析这章内容，给出具体的改进建议。"
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(msg, ctx))
