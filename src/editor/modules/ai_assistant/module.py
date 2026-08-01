"""AI 助手模块 — Qt 前端与 AI 后端的桥接层。"""

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDockWidget, QMessageBox

from ..base_module import BaseModule
from .agent import AIAgent
from .annotation_manager import AnnotationManager
from .orchestrator import AIOrchestrator
from .rag import RAGEngine
from .skills.rag_skills import SearchChaptersSkill
from .undo_stack import AIUndoStack
from .ui.chat_panel import ChatPanel
from .ui.annotation_list import AnnotationListPanel
from .memory_editor import MemoryEditor

from src.settings.ai_config import load_ai_config

logger = logging.getLogger("rewrite.ai")


class AIAssistantModule(BaseModule):
    """AI 助手模块 — 连接 Qt UI 和 AI 流程控制器。"""

    module_id = "ai_assistant"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.config = load_ai_config()
        self.agent = AIAgent(self.config, work_name=work_path.name)
        self.annotation_mgr = AnnotationManager(work_path)
        self.annotation_mgr.load()
        self._editor = None
        self._rag = RAGEngine()
        self._orchestrator = None
        self._proposal_worker = None
        self._loop_worker = None
        # 流式显示状态
        self._streaming_bubble = None
        self._streaming_text = ""
        # AI 写操作撤销栈 + 「全部允许」标志
        self._undo_stack = AIUndoStack()
        # 本轮对话开始前的快照栈深度(撤回时整轮回滚)
        self._undo_mark = 0
        self._auto_confirm = False

    # ── 生命周期 ──

    def load(self):
        self.annotation_mgr.load()
        chap_mod = self._get_module("chapters")
        if chap_mod:
            self._rag.build_index(chap_mod)
            SearchChaptersSkill.set_engine(self._rag)

    def save(self):
        self.annotation_mgr.save()

    def set_editor(self, editor):
        self._editor = editor

    def _get_module(self, mod_id):
        if self.parent() and hasattr(self.parent(), "modules"):
            return self.parent().modules.get(mod_id)
        return None

    # ── Orchestrator 初始化 ──

    def _init_orchestrator(self):
        """延迟初始化编排器（需要 chat_panel 已创建）。"""
        if self._orchestrator:
            return
        from .skills.registry import execute_skill, get_skill
        from .providers import _ensure_work_args, _describe_tool, _make_chat_request, get_openai_tools
        from .agent import save_chat_history

        self._orchestrator = AIOrchestrator(
            agent=self.agent,
            get_context_fn=self.get_context,
            execute_skill_fn=execute_skill,
            get_skill_fn=get_skill,
            ensure_work_args_fn=_ensure_work_args,
            describe_tool_fn=_describe_tool,
            make_chat_request_fn=_make_chat_request,
            get_tools_fn=get_openai_tools,
            save_history_fn=save_chat_history,
        )

    # ── 上下文 ──

    def get_context(self, scope: str) -> str:
        from .contexts import collect_context
        md = ""; sel = ""
        if self._editor:
            md = self._editor.get_markdown()
            cursor = self._editor.textCursor()
            if cursor.hasSelection():
                sel = cursor.selection().toHtml()
        wm = {}
        p = self.parent()
        if p and hasattr(p, '_work_meta') and p._work_meta:
            m = p._work_meta
            wm = {"title": getattr(m, 'title', ''), "work_type": getattr(m, 'work_type', ''),
                  "tags": getattr(m, 'tags', []), "total_words": getattr(m, 'total_words', 0),
                  "date_era": getattr(m, 'date_era', '')}
        return collect_context(
            scope=scope.split(","), current_md=md, current_selection=sel,
            chapter_module=self._get_module("chapters"),
            character_module=self._get_module("characters"),
            outline_module=self._get_module("outline"),
            timeline_module=self._get_module("timeline"),
            worldview_module=self._get_module("worldview"),
            map_module=self._get_module("map"),
            work_meta=wm)

    # ── Dock ──

    def create_dock_widget(self) -> QDockWidget:
        return self._make_chat_dock()

    def get_extra_docks(self) -> list[QDockWidget]:
        return [self._make_annotation_dock()]

    def _make_chat_dock(self) -> QDockWidget:
        self.chat_panel = ChatPanel()
        self.chat_panel.send_message_signal.connect(self._on_chat_message)
        self.chat_panel.set_analyze_callback(self._on_analyze)
        for msg in self.agent.history:
            r = msg.get("role", "user"); c = msg.get("content", "")
            if c:
                # track=False:历史回放不记录会话起点,避免启动后撤回清空全部历史气泡
                self.chat_panel.add_message(r, AIOrchestrator.render_message(c), track=False)
        self.chat_panel.update_memory(len(self.agent.history))
        self.chat_panel.set_undo_enabled(len(self.agent.history) >= 2)
        self.chat_panel.clear_requested.connect(self._on_clear_memory)
        self.chat_panel.undo_requested.connect(self._on_undo)
        self.chat_panel.edit_memory_requested.connect(lambda: MemoryEditor(self.agent, self.chat_panel).exec(self.parent()))
        self.chat_panel.compress_memory_requested.connect(self._on_compress_memory)
        self._init_orchestrator()
        return self.chat_panel

    def _make_annotation_dock(self) -> QDockWidget:
        self.annotation_panel = AnnotationListPanel(self.annotation_mgr)
        self.annotation_panel.annotation_clicked.connect(self._on_annotation_clicked)
        return self.annotation_panel

    # ── 记忆操作 ──

    def _on_clear_memory(self):
        self.agent.clear_history()
        self.chat_panel._on_clear()
        self.chat_panel.update_memory(0)
        self.chat_panel.set_undo_enabled(False)

    def _on_undo(self):
        restored_count = 0
        # 若有 AI 写操作快照,先询问是否回滚数据(整轮:从本轮对话开始前的深度起全部恢复)
        if len(self._undo_stack) > self._undo_mark:
            reply = QMessageBox.question(
                self.parent(), "撤回",
                "AI 最近修改过作品数据。撤回将:① 恢复数据到修改前(若 AI 新建了章节文件也会删除) ② 撤回对应对话。继续?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                while len(self._undo_stack) > self._undo_mark:
                    info = self._undo_stack.pop_restore()
                    if info:
                        restored_count += len(info.get("restored", []))
                self._refresh_panels(None)
            else:
                # 用户拒绝回滚:丢弃本轮全部快照,避免后续纯对话撤回反复弹窗
                while len(self._undo_stack) > self._undo_mark:
                    self._undo_stack.pop_rollback()
        if self.agent.undo_last_message():
            self.chat_panel.remove_session()
            self.chat_panel.update_memory(len(self.agent.history))
            self.chat_panel.set_undo_enabled(len(self.agent.history) >= 2)
        # 先撤对话气泡,再补回滚提示,避免提示被 remove_session 一并删除
        if restored_count:
            self.chat_panel.add_message(
                "assistant",
                f"↩ 已回滚 AI 的数据修改（{restored_count} 个文件恢复到修改前）",
                track=False)
        # 撤回后更新标记,使更早轮的快照可被继续撤回
        self._undo_mark = len(self._undo_stack)

    def _on_compress_memory(self):
        """用独立 API 整理压缩记忆。"""
        from PySide6.QtCore import QThread, Signal

        h = self.agent.history
        if len(h) < 6:
            QMessageBox.information(self.parent(), "压缩记忆", "条数较少（<6），无需压缩")
            return

        reply = QMessageBox.question(
            self.parent(), "压缩记忆",
            f"将 {len(h)} 条记忆发给 AI 压缩（独立 API，不影响对话）。继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.chat_panel.show_loading()
        history_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else 'AI'}: {m.get('content', '')[:500]}"
            for m in h)

        class _CompressWorker(QThread):
            finished = Signal(str); error = Signal(str)

            def __init__(self, config, history_text, parent=None):
                super().__init__(parent)
                self._config = config
                self._history_text = history_text

            def run(self):
                try:
                    import urllib.request
                    import json as _json
                    config = self._config
                    provider = config.get("provider", "")
                    api_key = config.get("api_key", "")
                    api_url = config.get("api_url", "") or (
                        "https://api.deepseek.com/v1" if provider in ("deepseek", "")
                        else "https://api.openai.com/v1")
                    model = config.get("model", "") or (
                        "deepseek-chat" if provider in ("deepseek", "")
                        else "gpt-4o-mini")
                    body = _json.dumps({
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "你是对话整理助手。请压缩以下对话为精炼摘要，保留所有重要信息。"},
                            {"role": "user", "content": self._history_text},
                        ],
                        "max_tokens": 4096,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"{api_url}/chat/completions", data=body,
                        headers={"Authorization": f"Bearer {api_key}",
                                 "Content-Type": "application/json", "User-Agent": "ReWrite/1.0"})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        data = _json.loads(resp.read().decode("utf-8"))
                        self.finished.emit(data["choices"][0]["message"]["content"])
                except Exception as e:
                    self.error.emit(str(e))

        agent_ref = self.agent
        module_ref = self
        w = _CompressWorker(self.agent.config, history_text)
        # 持有引用,防止 QThread 被 GC 时仍在运行导致崩溃/信号丢失
        self._compress_worker = w
        w.finished.connect(lambda s: _on_done(s))
        w.error.connect(lambda e: (module_ref.chat_panel.hide_loading(),
                                    QMessageBox.critical(module_ref.parent(), "错误", f"压缩失败: {e}")))
        w.start()

        def _on_done(summary):
            self.chat_panel.hide_loading()
            agent_ref.history = [{"role": "user", "content": f"历史对话摘要：\n\n{summary}"}]
            agent_ref._persist()
            self.chat_panel._on_clear()
            self.chat_panel.add_message("assistant",
                AIOrchestrator.render_message(f"✅ 记忆已压缩。\n\n{summary}"))
            self.chat_panel.update_memory(len(agent_ref.history))
            QMessageBox.information(self.parent(), "完成", "记忆已压缩为摘要。")

    # ── 主对话流程 ──

    def _on_chat_message(self, message: str, scope: str):
        if not self.agent.is_configured():
            self.chat_panel.add_message("assistant", "请先配置 AI 服务：菜单 -> 文件 -> 设置 -> AI 助手")
            self.chat_panel.enable_send()
            return
        # 记录本轮对话开始前的快照深度,撤回时整轮回滚
        self._undo_mark = len(self._undo_stack)
        self._orchestrator.set_work_name(self.work_path.name)
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, self.get_context(scope)))

    def _do_chat(self, message: str, context: str):
        from .worker import StreamingProposalWorker
        self._streaming_bubble = None
        self._streaming_text = ""

        self._proposal_worker = StreamingProposalWorker(self.agent, message, context)
        self._proposal_worker.text_chunk.connect(self._on_stream_chunk)
        self._proposal_worker.reasoning_chunk.connect(self._set_loading_reasoning)
        self._proposal_worker.proposals_ready.connect(self._on_tool_proposals)
        self._proposal_worker.text_response.connect(self._on_ai_response)
        self._proposal_worker.api_error.connect(self._on_ai_error)
        self._proposal_worker.start()

    def _set_loading_reasoning(self, text: str):
        if hasattr(self.chat_panel, '_loading_bubble') and self.chat_panel._loading_bubble:
            self.chat_panel._loading_bubble.set_reasoning(text)

    def _on_stream_chunk(self, text: str):
        """收到 AI 流式正文片段 → 实时更新聊天气泡。"""
        self._streaming_text += text
        if self._streaming_bubble is None:
            self._streaming_bubble = self.chat_panel.begin_streaming_message()
        self.chat_panel.update_streaming(self._streaming_bubble, self._streaming_text)

    # 工具名子串 → 影响的模块 id(按需刷新面板用)
    _TOOL_MODULE_MAP = [
        ("character", "characters"),
        ("outline", "outline"),
        ("timeline", "timeline"),
        ("worldview", "worldview"),
        ("map", "map"),
        ("chapter", "chapters"),
    ]

    @staticmethod
    def _is_read_tool(name: str) -> bool:
        """读工具(只读,不弹确认)。"""
        return name.startswith(("get_", "read_", "search_", "list_"))

    def _module_for_tool(self, name: str) -> set:
        for prefix, mod in self._TOOL_MODULE_MAP:
            if name.startswith(prefix):
                return {mod}
        return set()

    @staticmethod
    def _parse_tool_args(tc) -> dict | None:
        """解析工具参数;失败返回 None(调用方应跳过执行并回传错误)。"""
        import json as _j
        raw = tc.get("function", {}).get("arguments", "{}") or "{}"
        try:
            a = _j.loads(raw)
            return a if isinstance(a, dict) else None
        except Exception:
            return None

    def _on_tool_proposals(self, tool_calls, before, after, system):
        # 清除流式气泡（工具调用不需要显示中途文本）
        self._streaming_bubble = None
        self._streaming_text = ""
        self._handle_tool_calls(tool_calls, after, system)

    def _on_cancel(self):
        self.chat_panel.enable_send()
        logger.info("用户取消工具操作")

    def _handle_tool_calls(self, tool_calls, after, system):
        """统一处理一轮工具调用:读工具立即执行;写工具弹确认(或「全部允许」后直接执行)。"""
        from PySide6.QtWidgets import QApplication as _QA
        from .markdown_render import markdown_to_html

        self.chat_panel.hide_loading()
        _QA.processEvents()

        msgs = self._orchestrator.prepare_after_messages(tool_calls, after)

        reads, writes = [], []
        for tc in tool_calls:
            name = tc["function"]["name"]
            if self._is_read_tool(name):
                reads.append(tc)
            else:
                writes.append(tc)

        # 1) 读工具:免确认直接执行
        for tc in reads:
            name = tc["function"]["name"]
            a = self._parse_tool_args(tc)
            if a is None:
                result = {"success": False, "error": "工具参数解析失败(JSON 格式错误),请重新生成正确的参数"}
                desc = f"❌ {name} 参数解析失败,请重新调用"
            else:
                from .providers import _ensure_work_args
                from .skills.registry import execute_skill
                _ensure_work_args(name, a)
                result = execute_skill(name, a)
                desc = self._orchestrator._describe_tool(name, a, result)
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": desc})
            self.chat_panel.add_message("assistant", markdown_to_html(f"📖 {desc}"))
            _QA.processEvents()

        # 2) 写工具:确认(或自动)后执行
        if not writes:
            self._tool_loop(msgs, system)
            return

        if self._auto_confirm:
            touched = set()
            msgs = self._execute_writes(writes, msgs, touched)
            self._finish_after_writes(msgs, system, touched)
            return

        descs = self._orchestrator.resolve_proposals(writes)
        bubble = self.chat_panel.add_confirm_bubble([d[2] for d in descs], writes)
        bubble.confirmed.connect(lambda tcs: self._on_write_confirmed(tcs, msgs, system))
        bubble.auto_confirmed.connect(lambda tcs: self._on_write_confirmed(tcs, msgs, system, auto=True))
        bubble.cancelled.connect(self._on_cancel)
        logger.info(f"工具提案: {len(writes)} 个写操作 → 等待确认")

    def _on_write_confirmed(self, tool_calls, msgs, system, auto=False):
        if auto:
            self._auto_confirm = True
        touched = set()
        msgs = self._execute_writes(tool_calls, msgs, touched)
        self._finish_after_writes(msgs, system, touched)

    def _execute_writes(self, tool_calls, msgs, touched):
        """执行写工具:先快照文件(供回滚),再执行。返回更新后的 msgs。"""
        from PySide6.QtWidgets import QApplication as _QA
        from .markdown_render import markdown_to_html
        from .providers import _ensure_work_args
        from .skills.registry import execute_skill

        for tc in tool_calls:
            name = tc["function"]["name"]
            a = self._parse_tool_args(tc)
            if a is None:
                result = {"success": False, "error": "工具参数解析失败(JSON 格式错误),请重新生成正确的参数"}
                desc = f"❌ {name} 参数解析失败,请重新调用"
            else:
                _ensure_work_args(name, a)
                logger.info(f"执行工具: {name} args={a}")
                # 写操作前快照,供「撤回」回滚(读工具不经过此路径,防御性跳过)
                pushed = not self._is_read_tool(name)
                if pushed:
                    self._undo_stack.push(name, a, self.work_path)
                if name == "update_chapter":
                    result = self._do_chapter_diff(a)
                else:
                    result = execute_skill(name, a)
                if isinstance(result, dict) and result.get("success") is False and pushed:
                    # 执行失败:丢弃快照,避免后续「撤回」误回滚未生效的操作
                    self._undo_stack.pop_rollback()
                elif pushed and isinstance(result, dict):
                    # 关联实际创建/重命名的文件路径,供撤回精确删除(不误伤手动文件)
                    self._undo_stack.attach_result(result)
                desc = self._orchestrator._describe_tool(name, a, result)
            touched.update(self._module_for_tool(name))
            logger.info(f"工具结果: {name} → success={result.get('success') if isinstance(result, dict) else '?'} "
                        f"error={result.get('error', '') if isinstance(result, dict) else str(result)[:200]}")
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": desc})
            self.chat_panel.add_message("assistant", markdown_to_html(f"✅ {desc}"))
            _QA.processEvents()
        return msgs

    def _finish_after_writes(self, msgs, system, touched):
        from PySide6.QtWidgets import QApplication as _QA
        self._refresh_panels(touched)
        self.chat_panel._scroll_to_bottom()
        self.chat_panel.show_loading()
        # 重置流式状态（tool_loop 会创建新的流式气泡）
        self._streaming_bubble = None
        self._streaming_text = ""
        _QA.processEvents()
        self._tool_loop(msgs, system)

    def _do_chapter_diff(self, args: dict) -> dict:
        """章节修改走 diff 确认。

        安全:固定使用当前作品目录(self.work_path),不信任 AI 提供的 work
        参数(防路径穿越);章节匹配限定 .md/.html 后缀。
        """
        work = self.work_path
        chapter = str(args.get("chapter", ""))
        cd = work / "chapters"; old_c = ""; tp = None
        if cd.exists():
            try:
                for f in cd.iterdir():
                    if f.suffix.lower() not in (".md", ".html"):
                        continue
                    d = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
                    if d == chapter or f.stem == chapter:
                        old_c = f.read_text(encoding="utf-8"); tp = f; break
            except OSError as e:
                return {"success": False, "error": f"读取章节失败: {e}"}
        new_c = args.get("content", "")
        cn = str(tp.name) if tp else chapter
        if tp is None:
            # 真实错误:未找到章节(而非误导性的「用户拒绝」),附现有章节名供 AI 自修正
            existing = []
            if cd.exists():
                try:
                    existing = sorted(
                        (f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem)
                        for f in cd.iterdir()
                        if not f.name.startswith(".") and f.suffix.lower() in (".md", ".html"))
                except OSError:
                    pass
            return {"success": False, "error": f"未找到章节: {chapter}",
                    "existing_chapters": existing}
        if new_c and self._show_diff_dialog(old_c, new_c, cn):
            try:
                tp.write_text(new_c, encoding="utf-8")
            except OSError as e:
                return {"success": False, "error": f"写入章节失败: {e}"}
            logger.info(f"章节 diff 确认: {cn}")
            return {"success": True, "chapter": chapter}
        logger.info("章节 diff 被拒绝")
        return {"success": False, "error": "用户拒绝了修改"}

    def _tool_loop(self, messages: list, system: str):
        from .worker import StreamingLoopWorker

        agent_ref = self.agent; module_ref = self; orch = self._orchestrator

        # 重置流式状态（准备接收续写回复的流式输出）
        self._streaming_bubble = None
        self._streaming_text = ""

        w = StreamingLoopWorker(agent_ref, messages, system or "")
        self._loop_worker = w

        def on_data(data):
            choice = data.get("choices", [{}])[0]; msg = choice.get("message", {})
            c = msg.get("content") or ""; tcs = msg.get("tool_calls", [])
            if not tcs:
                agent_ref.history.append({"role": "assistant", "content": c})
                agent_ref._persist()
                module_ref._on_ai_response(c); return

            # 还有工具调用 → 继续循环(读免确认/写确认由 _handle_tool_calls 统一处理)
            messages.append({"role": "assistant", "content": c,
                "tool_calls": [{"id": t["id"], "type": "function",
                                "function": {"name": t["function"]["name"],
                                             "arguments": t["function"]["arguments"]}}
                               for t in tcs]})
            module_ref._handle_tool_calls(tcs, messages, system)

        w.text_chunk.connect(self._on_stream_chunk)
        w.finished.connect(on_data)
        w.error.connect(self._on_ai_error)
        w.start()

    # ── 响应处理 ──

    def _on_ai_response(self, response: str):
        self.chat_panel.hide_loading()
        # 如果之前有流式气泡，用渲染后的最终内容替换它
        if self._streaming_bubble is not None:
            self._streaming_bubble.set_content(AIOrchestrator.render_message(response))
            self._streaming_bubble = None
            self._streaming_text = ""
        else:
            self.chat_panel.add_message("assistant", AIOrchestrator.render_message(response))
        self.chat_panel.enable_send()
        self.chat_panel.update_memory(len(self.agent.history))
        try:
            if self.agent.history and len(self.agent.history) >= 2:
                um = self.agent.history[-2].get("content", "")
                if isinstance(um, str) and any(k in um for k in ("分析", "批注", "建议", "评价")):
                    self._create_module_annotations(response)
        except Exception:
            pass
        self.chat_panel._scroll_to_bottom()
        self._proposal_worker = None

    def _on_ai_error(self, error_msg: str):
        self.chat_panel.hide_loading()
        self.chat_panel.add_message("assistant", f"[错误] {error_msg}")
        self.chat_panel.enable_send()
        # 清理未完成的流式气泡状态
        self._streaming_bubble = None
        self._streaming_text = ""
        self._proposal_worker = None

    # ── 面板刷新 ──

    def _refresh_panels(self, touched=None):
        """刷新面板。touched: 需要刷新的模块 id 集合;None 表示全量刷新。"""
        p = self.parent()
        if not p or not hasattr(p, 'modules'):
            return
        if not touched:
            # 空集(未知工具)按全量刷新处理,保证面板与数据一致
            touched = {"characters", "outline", "timeline", "worldview", "map", "chapters"}
        for mod_id, attr in [("characters", "_build_tree"), ("outline", "_build_tree"),
                              ("timeline", "_refresh"), ("worldview", "_build_tree"),
                              ("map", "_refresh")]:
            if mod_id not in touched:
                continue
            mod = p.modules.get(mod_id)
            if mod and hasattr(mod, 'load'):
                mod.load()
                dock = p.docks.get(mod_id)
                if dock and hasattr(dock, attr):
                    getattr(dock, attr)()

        chap_mod = p.modules.get("chapters")
        if "chapters" in touched and chap_mod and hasattr(chap_mod, 'load'):
            chap_mod.load()
            chap_list = getattr(p, 'chapter_list', None)
            if chap_list and hasattr(chap_list, '_refresh'):
                chap_list._refresh()
        if "chapters" in touched and self._editor:
            cp = self._editor.current_chapter_path()
            if cp and Path(cp).exists():
                try:
                    nmd = Path(cp).read_text(encoding="utf-8")
                    if nmd != self._editor.get_markdown():
                        pos = self._editor.textCursor().position()
                        self._editor.blockSignals(True)
                        try:
                            self._editor.setMarkdown(nmd)
                            c = self._editor.textCursor(); c.setPosition(min(pos, len(nmd)))
                            self._editor.setTextCursor(c)
                        finally:
                            self._editor.blockSignals(False)
                except OSError:
                    pass
        # RAG 索引仅在章节内容变化后重建(全量刷新时也重建)
        if chap_mod and ("chapters" in touched):
            self._rag.build_index(chap_mod)

    # ── 批注 ──

    def _on_annotation_clicked(self, ann_id: str):
        for ann in self.annotation_mgr.annotations:
            if ann.id == ann_id:
                dk = self.parent().docks if hasattr(self.parent(), 'docks') else {}
                if ann.target_type in dk:
                    dk[ann.target_type].show(); dk[ann.target_type].raise_()
                break

    def _create_module_annotations(self, response: str):
        cm = self._get_module("characters"); om = self._get_module("outline")
        tm = self._get_module("timeline")
        cp = self._editor.current_chapter_path() if self._editor else None
        pl = self._editor.toPlainText() if self._editor else ""
        def _fp(q, p):
            i = p.find(q)
            if i >= 0: return (i, i + len(q))
            import re as _r2
            c2 = _r2.sub('[，。！？、；：""''「」【】（）《》]', '', q)
            pc2 = _r2.sub('[，。！？、；：""''「】）《》]', '', p)
            i = pc2.find(c2)
            return (i, i + len(c2)) if i >= 0 else (-1, -1)

        pat = r'\[ANNOTATION:(\w+):([^\]]+)\]\n?(.*?)\n?\[/ANNOTATION\]'
        ms = _re.findall(pat, response, _re.DOTALL)
        ok = False
        for t, ti, tc in ms:
            t, ti, tc = t.strip(), ti.strip(), (tc.strip() or response[:200])
            tp = ht = ""; sp = ep = -1
            if t == "chapter":
                tp = cp or ""
                qs2 = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', tc, _re.DOTALL)
                if qs2: ht = qs2[0].strip(); sp, ep = _fp(ht, pl)
            elif t == "character" and cm:
                def _fc(ns):
                    for n in ns:
                        if not n.is_group and n.name == ti: return n.id
                        if n.children: r = _fc(n.children); return r
                    return ""
                tp = _fc(cm.nodes)
            elif t == "outline" and om:
                def _fo(ns):
                    for e in ns:
                        if e.title == ti: return e.id
                        if e.children: r = _fo(e.children); return r
                    return ""
                tp = _fo(om.entries)
            elif t == "timeline" and tm:
                def _ft(ns):
                    for e in ns:
                        if e.title == ti: return e.id
                        if e.children: r = _ft(e.children); return r
                    return ""
                tp = _ft(tm.events)
            if t in ("chapter","character","outline","timeline"):
                self.annotation_mgr.add_annotation(target_type=t, target_path=tp or ti,
                    target_title=ti, suggestion=tc, highlight_text=ht, start_pos=sp, end_pos=ep); ok = True
        if not ok and cp:
            qs = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', response, _re.DOTALL)
            qt = qs[0].strip() if qs else ""; sp, ep = _fp(qt, pl) if qt else (-1, -1)
            self.annotation_mgr.add_annotation(target_type="chapter", target_path=cp,
                target_title="当前章节", suggestion=response[:500], highlight_text=qt, start_pos=sp, end_pos=ep)
        self.annotation_mgr.save(); self.annotation_panel.refresh()
        if self._editor and cp:
            self._editor.set_annotations(self.annotation_mgr.get_chapter_annotations(cp))

    # ── Diff 对话框 ──

    @staticmethod
    def _diff_html(old_text: str, new_text: str, side: str) -> str:
        """生成行级 diff HTML。side='old':删除行红色删除线;side='new':新增行绿色。未变行灰色。"""
        import difflib
        import html as _html
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        out = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                lines = old_lines[i1:i2] if side == "old" else new_lines[j1:j2]
                for line in lines:
                    out.append(f'<span style="color:#9aa5b1;">{_html.escape(line)}</span>')
            elif tag == "delete":
                if side == "old":
                    for line in old_lines[i1:i2]:
                        out.append(f'<span style="background:#FFEBEE;color:#C62828;text-decoration:line-through;">{_html.escape(line)}</span>')
            elif tag == "insert":
                if side == "new":
                    for line in new_lines[j1:j2]:
                        out.append(f'<span style="background:#E8F5E9;color:#2E7D32;">{_html.escape(line)}</span>')
            elif tag == "replace":
                if side == "old":
                    for line in old_lines[i1:i2]:
                        out.append(f'<span style="background:#FFEBEE;color:#C62828;text-decoration:line-through;">{_html.escape(line)}</span>')
                else:
                    for line in new_lines[j1:j2]:
                        out.append(f'<span style="background:#E8F5E9;color:#2E7D32;">{_html.escape(line)}</span>')
        return ('<pre style="font-family:Consolas,Monaco,monospace;font-size:12px;'
                'line-height:1.6;white-space:pre-wrap;">' + "".join(out) + "</pre>")

    def _show_diff_dialog(self, old_text: str, new_text: str, chapter_path: str) -> bool:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                       QPushButton, QSplitter, QTextBrowser, QApplication as _QA, QWidget)
        from PySide6.QtCore import Qt as _Qt
        d = QDialog(_QA.activeWindow()); d.setWindowTitle("确认章节修改")
        d.setMinimumSize(700, 450); d.resize(900, 600)
        lo = QVBoxLayout(d)
        lo.addWidget(QLabel(f"章节修改确认: {chapter_path}   （红=删除行  绿=新增行  灰=未变）"))
        sp = QSplitter(_Qt.Orientation.Horizontal)
        for label, color, text, side in [("旧版", "#C62828", old_text, "old"),
                                         ("新版", "#2E7D32", new_text, "new")]:
            w = QTextBrowser()
            w.setHtml(self._diff_html(old_text, new_text, side))
            w.setStyleSheet(
                f"QTextBrowser{{background-color:{'#FFF5F5' if label=='旧版' else '#F1F8E9'};"
                f"border:1px solid {'#FFCDD2' if label=='旧版' else '#C8E6C9'};padding:12px;}}")
            lbl = QLabel(label); lbl.setStyleSheet(f"color:{color};font-weight:bold;font-size:11px;")
            vbox = QVBoxLayout(); vbox.addWidget(lbl); vbox.addWidget(w)
            c = QWidget(); c.setLayout(vbox); sp.addWidget(c)
        lo.addWidget(sp, 1)
        br = QHBoxLayout(); br.addStretch()
        rj = QPushButton("拒绝"); rj.setStyleSheet("padding:8px 24px;border:1px solid #EF5350;color:#C62828;border-radius:4px;")
        rj.clicked.connect(d.reject); br.addWidget(rj)
        ac = QPushButton("接受修改"); ac.setStyleSheet("padding:8px 24px;background:#4CAF50;color:#fff;font-weight:bold;border-radius:4px;")
        ac.clicked.connect(d.accept); br.addWidget(ac); lo.addLayout(br)
        return d.exec() == QDialog.DialogCode.Accepted

    # ── 分析 ──

    def _on_analyze(self):
        if not self.agent.is_configured():
            QMessageBox.information(self.parent(), "提示", "请先配置 AI 服务"); return
        ctx = self.get_context("current_chapter,outline,characters")
        msg = "请从情节、人物、节奏、语言等角度全面分析这章内容，给出具体的改进建议。"
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(msg, ctx))

    def search(self, query: str) -> list:
        q = query.lower(); results = []
        for ann in self.annotation_mgr.annotations:
            if q in ann.suggestion.lower() or q in ann.target_title.lower():
                tag = "已采纳" if ann.status == "accepted" else ("已忽略" if ann.status == "ignored" else "待处理")
                results.append((f"{ann.type_icon} {ann.target_title[:20]}", f"批注 ({ann.type_label})", ann.id))
        return results
