"""AI 助手模块 — 两个独立 Dock：对话 + 批注，均支持多模块。"""

from pathlib import Path

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

        self._proposal_worker = ToolProposalWorker(self.agent, message, context)
        self._proposal_worker.proposals_ready.connect(self._on_tool_proposals)
        self._proposal_worker.text_response.connect(self._on_ai_response)
        self._proposal_worker.api_error.connect(self._on_ai_error)
        self._proposal_worker.start()

    def _on_tool_proposals(self, tool_calls, before, after, system):
        """AI 返回了工具调用提案，在主线程弹出确认对话框。"""
        from PySide6.QtWidgets import QMessageBox, QApplication as _QA
        from .skills.registry import get_skill, execute_skill
        from .providers import get_final_response
        import json as _j

        # 构建描述信息
        descriptions = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = _j.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            from .providers import _ensure_work_args
            _ensure_work_args(name, args)
            skill = get_skill(name)
            if skill and hasattr(skill, "summarize"):
                desc = skill.summarize({"success": True}, args)
            else:
                desc = f"执行 {name}"
            descriptions.append(desc)

        # 确认对话框
        lines = ["AI 提议以下操作，是否允许？\n"]
        for d in descriptions:
            lines.append(f"  • {d}")
        lines.append("")

        reply = QMessageBox.question(
            _QA.activeWindow(), "确认 AI 操作",
            "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            self.chat_panel.hide_loading()
            self.chat_panel.add_message("assistant", "已取消 AI 操作")
            self.chat_panel.enable_send()
            return

        # 执行工具（主线程）
        self.chat_panel.show_loading()
        _QA.processEvents()

        after = list(after)
        after.pop()  # 移除占位符
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = _j.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            _ensure_work_args(name, args)
            result = execute_skill(name, args)
            from .providers import _describe_tool
            result_text = _describe_tool(name, args, result)
            # 注入 tool result
            after.append({"role": "tool", "tool_call_id": tc["id"], "content": result_text})

        # 第二轮：发给 AI 生成最终回复
        from .worker import ToolExecuteWorker
        self._execute_worker = ToolExecuteWorker(self.agent, after, system)
        self._execute_worker.finished.connect(self._on_ai_response)
        self._execute_worker.error.connect(self._on_ai_error)
        self._execute_worker.start()

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
                              ("timeline", "_refresh")]:
            mod = p.modules.get(mod_id)
            if mod and hasattr(mod, 'load'):
                mod.load()
                dock = p.docks.get(mod_id)
                if dock and hasattr(dock, attr):
                    getattr(dock, attr)()

    def _on_analyze(self):
        if not self.agent.is_configured():
            QMessageBox.information(self.parent(), "提示", "请先在设置中配置 AI 服务")
            return
        ctx = self.get_context("current_chapter,outline,characters")
        msg = "请从情节、人物、节奏、语言等角度全面分析这章内容，给出具体的改进建议。"
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(msg, ctx))
