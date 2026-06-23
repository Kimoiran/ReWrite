"""AI 助手模块 — 两个独立 Dock：对话 + 批注，均支持多模块。"""

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDockWidget, QMessageBox

from ..base_module import BaseModule
from .agent import AIAgent
from .annotation_manager import AnnotationManager, Annotation
from .ui.chat_panel import ChatPanel
from .ui.annotation_list import AnnotationListPanel

from src.settings.ai_config import load_ai_config


class AIAssistantModule(BaseModule):
    """AI 写作助手模块。管理对话面板 + 跨模块批注系统。"""

    module_id = "ai_assistant"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.config = load_ai_config()
        work_name = work_path.name
        self.agent = AIAgent(self.config, work_name=work_name)
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
        current_html = ""
        current_selection = ""
        if self._editor:
            current_html = self._editor.get_html()
            cursor = self._editor.textCursor()
            if cursor.hasSelection():
                current_selection = cursor.selection().toHtml()
        parent = self.parent()
        work_meta = {}
        if hasattr(parent, '_work_meta') and parent._work_meta:
            meta = parent._work_meta
            work_meta = {
                "title": getattr(meta, 'title', ''),
                "work_type": getattr(meta, 'work_type', ''),
                "tags": getattr(meta, 'tags', []),
                "total_words": getattr(meta, 'total_words', 0),
            }
        return collect_context(
            scope=scope.split(","),
            current_html=current_html,
            current_selection=current_selection,
            chapter_module=self._get_module("chapters"),
            character_module=self._get_module("characters"),
            outline_module=self._get_module("outline"),
            timeline_module=self._get_module("timeline"),
            work_meta=work_meta,
        )

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
        self.chat_panel.update_memory(len(self.agent.history))
        self.chat_panel.clear_btn.clicked.disconnect()
        self.chat_panel.clear_btn.clicked.connect(self._on_clear_memory)
        return self.chat_panel

    def _on_clear_memory(self):
        self.agent.clear_history()
        self.chat_panel._on_clear()
        self.chat_panel.update_memory(0)

    def _make_annotation_dock(self) -> QDockWidget:
        self.annotation_panel = AnnotationListPanel(self.annotation_mgr)
        self.annotation_panel.annotation_clicked.connect(self._on_annotation_clicked)
        return self.annotation_panel

    def _on_annotation_clicked(self, ann_id: str):
        """点击批注跳转到对应模块。"""
        for ann in self.annotation_mgr.annotations:
            if ann.id == ann_id:
                if ann.target_type == "character":
                    # 打开人物卡面板并选中角色
                    dock = self.parent().docks.get("characters") if hasattr(self.parent(), 'docks') else None
                    if dock:
                        dock.show()
                        dock.raise_()
                elif ann.target_type == "outline":
                    dock = self.parent().docks.get("outline") if hasattr(self.parent(), 'docks') else None
                    if dock:
                        dock.show()
                        dock.raise_()
                elif ann.target_type == "timeline":
                    dock = self.parent().docks.get("timeline") if hasattr(self.parent(), 'docks') else None
                    if dock:
                        dock.show()
                        dock.raise_()
                else:
                    # 正文批注，跳转到章节
                    pass
                break

    def _create_module_annotations(self, response: str):
        """从 AI 回复中提取针对各模块的批注。"""
        lower = response.lower()

        # 正文批注
        current_path = self._editor.current_chapter_path() if self._editor else None
        if current_path and ("章节" in response or "正文" in response or "情节" in response or "节奏" in response):
            self.annotation_mgr.add_annotation(
                target_type="chapter",
                target_path=current_path,
                target_title="当前章节",
                suggestion=response,
            )

        # 人物批注：如果回复提到角色名
        char_mod = self._get_module("characters")
        if char_mod and ("人物" in lower or "角色" in lower):
            for c in char_mod.characters:
                if c.name and c.name in response:
                    self.annotation_mgr.add_annotation(
                        target_type="character",
                        target_path=c.id,
                        target_title=c.name,
                        suggestion=response,
                    )

        # 大纲批注
        outline_mod = self._get_module("outline")
        if outline_mod and ("大纲" in lower or "结构" in lower):
            def _check_entries(entries):
                for e in entries:
                    if e.title and e.title in response:
                        self.annotation_mgr.add_annotation(
                            target_type="outline",
                            target_path=e.id,
                            target_title=e.title,
                            suggestion=response,
                        )
                    _check_entries(e.children)
            _check_entries(outline_mod.entries)

        # 时间线批注
        timeline_mod = self._get_module("timeline")
        if timeline_mod and "时间线" in lower:
            for ev in timeline_mod.events:
                if ev.title and ev.title in response:
                    self.annotation_mgr.add_annotation(
                        target_type="timeline",
                        target_path=ev.id,
                        target_title=ev.title,
                        suggestion=response,
                    )

        self.annotation_mgr.save()
        self.annotation_panel.refresh()

    # ── 交互逻辑 ──

    def _on_chat_message(self, message: str, scope: str):
        if not self.agent.is_configured():
            self.chat_panel.add_message("assistant", "请先在「文件 → 设置 → AI 助手」中配置 API Key")
            self.chat_panel.enable_send()
            return
        context = self.get_context(scope)
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, context))

    def _do_chat(self, message: str, context: str):
        response = self.agent.send_message(message, current_context=context)
        self.chat_panel.hide_loading()
        self.chat_panel.add_message("assistant", response)
        self.chat_panel.enable_send()
        self.chat_panel.update_memory(len(self.agent.history))

        # 从回复中提取所有模块的批注
        self._create_module_annotations(response)

    def _on_analyze(self):
        if not self.agent.is_configured():
            QMessageBox.information(self.parent(), "提示", "请先在「文件 → 设置 → AI 助手」中配置 API Key")
            return
        context = self.get_context("current_chapter,outline,characters")
        message = "请从情节、人物、节奏、语言等角度全面分析这章内容，给出具体的改进建议。"
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, context))
