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
from mcp.tools import call_tool, list_works


class AIAssistantModule(BaseModule):
    """AI 写作助手模块。管理对话面板 + 跨模块批注系统。"""

    module_id = "ai_assistant"

    _EDIT_MODULE_MAP = {
        "character": "characters",
        "outline": "outline",
        "timeline": "timeline",
        "worldview": "worldview",
    }

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
            worldview_module=self._get_module("worldview"),
            work_meta=work_meta,
        )

    def _get_module(self, mod_id):
        if self.parent() and hasattr(self.parent(), "modules"):
            return self.parent().modules.get(mod_id)
        return None

    def _get_edit_module(self, edit_type: str):
        """根据 AI 编辑类型获取模块实例。"""
        mod_id = self._EDIT_MODULE_MAP.get(edit_type)
        return self._get_module(mod_id) if mod_id else None

    def _get_old_value(self, edit_type, target, field):
        """获取修改前的旧值。"""
        mod = self._get_edit_module(edit_type)
        if not mod:
            return ""
        try:
            if edit_type == "character":
                def _find(nodes):
                    for n in nodes:
                        if not n.is_group and n.name == target:
                            return getattr(n, field, "")
                        if n.children:
                            v = _find(n.children)
                            if v:
                                return v
                    return ""
                return _find(mod.nodes)
            elif edit_type == "outline":
                def _find(entries):
                    for e in entries:
                        if e.title == target:
                            return getattr(e, field, "")
                        if e.children:
                            v = _find(e.children)
                            if v:
                                return v
                    return ""
                return _find(mod.entries)
            elif edit_type == "timeline":
                for e in mod.events:
                    if e.title == target:
                        return getattr(e, field, "")
                return ""
            elif edit_type == "worldview":
                def _find(entries):
                    for e in entries:
                        if e.title == target:
                            return getattr(e, field, "")
                        if e.children:
                            v = _find(e.children)
                            if v:
                                return v
                    return ""
                return _find(mod.entries)
        except:
            return ""

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
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                self.chat_panel.add_message(role, markdown_to_html(content))

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
        """撤回上一条对话。"""
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
                if ann.target_type == "character":
                    dock = self.parent().docks.get("characters") if hasattr(self.parent(), 'docks') else None
                    if dock: dock.show(); dock.raise_()
                elif ann.target_type == "outline":
                    dock = self.parent().docks.get("outline") if hasattr(self.parent(), 'docks') else None
                    if dock: dock.show(); dock.raise_()
                elif ann.target_type == "timeline":
                    dock = self.parent().docks.get("timeline") if hasattr(self.parent(), 'docks') else None
                    if dock: dock.show(); dock.raise_()
                break

    def _create_module_annotations(self, response: str):
        import re as _re
        char_mod = self._get_module("characters")
        outline_mod = self._get_module("outline")
        timeline_mod = self._get_module("timeline")
        current_path = self._editor.current_chapter_path() if self._editor else None
        current_plain = self._editor.toPlainText() if self._editor else ""

        def _find_pos(quote, plain):
            idx = plain.find(quote)
            if idx >= 0:
                return (idx, idx + len(quote))
            import re as _re2
            clean = _re2.sub('[，。！？、；：""''「」【】（）《》]', '', quote)
            plain_clean = _re2.sub('[，。！？、；：""''「」【】（）《》]', '', plain)
            idx = plain_clean.find(clean)
            return (idx, idx + len(clean)) if idx >= 0 else (-1, -1)

        pattern = r'\[ANNOTATION:(\w+):([^\]]+)\]\n?(.*?)\n?\[/ANNOTATION\]'
        matches = _re.findall(pattern, response, _re.DOTALL)
        created_any = False

        for ann_type, ann_title, ann_content in matches:
            ann_type = ann_type.strip()
            ann_title = ann_title.strip()
            ann_content = ann_content.strip() or response[:200]
            target_path = ""
            highlight_text = ""
            start_pos = end_pos = -1

            if ann_type == "chapter":
                target_path = current_path or ""
                quotes = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', ann_content, _re.DOTALL)
                if quotes:
                    highlight_text = quotes[0].strip()
                    start_pos, end_pos = _find_pos(highlight_text, current_plain)
            elif ann_type == "character" and char_mod:
                def _find_char(nodes):
                    for n in nodes:
                        if not n.is_group and n.name == ann_title:
                            return n.id
                        if n.children:
                            found = _find_char(n.children)
                            if found:
                                return found
                    return ""
                target_path = _find_char(char_mod.nodes)
            elif ann_type == "outline" and outline_mod:
                def _find_outline(entries):
                    for e in entries:
                        if e.title == ann_title:
                            return e.id
                        if e.children:
                            found = _find_outline(e.children)
                            if found:
                                return found
                    return ""
                target_path = _find_outline(outline_mod.entries)
            elif ann_type == "timeline" and timeline_mod:
                for ev in timeline_mod.events:
                    if ev.title == ann_title:
                        target_path = ev.id
                        break

            if ann_type in ("chapter", "character", "outline", "timeline"):
                self.annotation_mgr.add_annotation(
                    target_type=ann_type, target_path=target_path or ann_title,
                    target_title=ann_title, suggestion=ann_content,
                    highlight_text=highlight_text, start_pos=start_pos, end_pos=end_pos)
                created_any = True

        if not created_any and current_path:
            quotes = _re.findall(r'\[QUOTE\](.*?)\[/QUOTE\]', response, _re.DOTALL)
            qt = quotes[0].strip() if quotes else ""
            sp, ep = _find_pos(qt, current_plain) if qt else (-1, -1)
            self.annotation_mgr.add_annotation(
                target_type="chapter", target_path=current_path, target_title="当前章节",
                suggestion=response[:500], highlight_text=qt, start_pos=sp, end_pos=ep)

        self.annotation_mgr.save()
        self.annotation_panel.refresh()

        if self._editor and current_path:
            self._editor.set_annotations(self.annotation_mgr.get_chapter_annotations(current_path))

    def _apply_ai_edits(self, response: str):
        """解析 [EDIT]，弹出确认对话框，执行修改。"""
        import re as _re
        pattern = r'\[EDIT:(\w+):([^\]]+)\]\n(.*?)\n\[/EDIT\]'
        matches = _re.findall(pattern, response, _re.DOTALL)
        if not matches:
            return

        edits = []
        for et, target, body in matches:
            et = et.strip(); target = target.strip()
            for line in body.strip().split("\n"):
                line = line.strip()
                if "=" not in line:
                    continue
                field, _, value = line.partition("=")
                field = field.strip()
                value = value.strip().strip('"').strip("'")
                old = self._get_old_value(et, target, field)
                edits.append((et, target, field, old[:80] if old else "", value[:80]))

        if not edits:
            return

        lines = ["AI 提议以下修改，是否执行？\n"]
        icon_map = {"character": "👤", "outline": "📋", "timeline": "📅", "worldview": "🌍"}
        for et, target, field, old, new in edits:
            icon = icon_map.get(et, "📌")
            lines.append(f"{icon} {target}.{field}:")
            if old:
                lines.append(f"   旧: {old}")
            lines.append(f"   新: {new}")
            lines.append("")

        from PySide6.QtWidgets import QMessageBox as _QMB
        reply = _QMB.question(self.parent(), "确认 AI 修改",
            "\n".join(lines),
            _QMB.StandardButton.Yes | _QMB.StandardButton.No,
            _QMB.StandardButton.No)

        if reply != _QMB.StandardButton.Yes:
            self.chat_panel.add_message("assistant", "已取消 AI 修改")
            return

        results = []
        for et, target, body in matches:
            et = et.strip(); target = target.strip()
            mod = self._get_edit_module(et)
            if not mod or not hasattr(mod, "apply_edit"):
                results.append(f"{et} 模块不可编辑")
                continue
            for line in body.strip().split("\n"):
                line = line.strip()
                if "=" not in line:
                    continue
                field, _, value = line.partition("=")
                field = field.strip()
                value = value.strip().strip('"').strip("'")
                ok, msg = mod.apply_edit(target, field, value)
                results.append(f"  {target}.{field}: {'✅' if ok else '❌'} {msg}")

        self.chat_panel.add_message("assistant",
            f"<p><b>✅ AI 修改已执行：</b></p><pre>{chr(10).join(results)}</pre>")

    def _apply_mcp_tools(self, response: str):
        """解析 [MCP:tool:args] 标记并直接调用工具函数。"""
        import re as _re, json as _json
        pattern = r'\[MCP:(\w+):(.*?)\]'
        matches = _re.findall(pattern, response, _re.DOTALL)
        if not matches:
            return

        work_name = self.work_path.name if hasattr(self, 'work_path') else ""
        results = []

        for tool_name, args_json in matches:
            tool_name = tool_name.strip()
            try:
                args = _json.loads(args_json.strip()) if args_json.strip() else {}
            except json.JSONDecodeError:
                results.append(f"  {tool_name}: 参数解析失败")
                continue

            # 自动注入 work 参数
            if tool_name != "list_works" and "work" not in args:
                args["work"] = work_name

            result = call_tool(tool_name, args)
            success = result.get("success", True) if isinstance(result, dict) else True
            icon = "✅" if success else "❌"
            summary = _json.dumps(result, ensure_ascii=False)[:100]
            results.append(f"  {icon} {tool_name}: {summary}")

        if results:
            self.chat_panel.add_message("assistant",
                f"<p><b>🔧 MCP 工具执行结果：</b></p><pre>{chr(10).join(results)}</pre>")

    def _intercept_and_execute(self, message: str) -> str:
        """拦截用户消息，检测修改意图，直接用 MCP 工具执行。
        返回注入上下文文本（空串表示无需注入）。"""
        import re as _re
        work_name = self.work_path.name if hasattr(self, 'work_path') else ""
        results = []

        # 创建/修改角色
        m = _re.search(r'(?:创建|新建|添加|加个)(?:角色|人物)\s*(.+?)(?:，|$|\n)', message)
        if m:
            name = m.group(1).strip()
            r = call_tool("create_character", {"work": work_name, "name": name})
            results.append(f"[系统] 已创建角色「{name}」: {r.get('id', '')}")

        # 创建分组
        m = _re.search(r'(?:创建|新建|添加|加个)分组\s*(.+?)(?:，|$|\n)', message)
        if m:
            name = m.group(1).strip()
            r = call_tool("add_group", {"work": work_name, "name": name})
            results.append(f"[系统] 已创建分组「{name}」")

        # 修改角色字段：「把A的xx改成/设为/变成B」
        m = _re.search(r'把\s*(.+?)\s*的\s*(.+?)\s*(?:改成?|设为|变为|改为)\s*(.+?)(?:$|，|。)', message)
        if m:
            char_name, field_zh, value = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            field_map = {"性格": "personality", "年龄": "age", "性别": "gender",
                         "外貌": "appearance", "背景": "background", "目标": "goals",
                         "备注": "notes", "职业": "occupation", "身份": "occupation",
                         "姓名": "name", "别名": "aliases"}
            field = field_map.get(field_zh, field_zh)
            r = call_tool("update_character", {"work": work_name, "name": char_name, "field": field, "value": value})
            status = "✅" if r.get("success") else "❌"
            old = r.get("old", "")
            results.append(f"[系统] {status} 修改{char_name}.{field}: {old} → {value}")

        # 删除角色
        m = _re.search(r'(?:删除|移除)\s*(?:角色|人物)\s*(.+?)(?:$|，|。)', message)
        if m:
            name = m.group(1).strip()
            results.append(f"[系统] 删除角色需确认: {name}")

        # 批量创建：检测 AI 输出的结构化格式（age:xxx 性别:xxx 等）
        lines = message.split('\n')
        current_char = None
        for line in lines:
            stripped = line.strip()
            # 📁 分组: xxx
            grp = _re.match(r'📁\s*分组[：:]\s*(.+)', stripped)
            if grp:
                name = grp.group(1).strip()
                call_tool("add_group", {"work": work_name, "name": name})
                results.append(f"[系统] 已创建分组「{name}」")
                continue
            # 👤 人物: xxx 或 👤 xxx
            char = _re.match(r'👤\s*[：:]?\s*(.+)', stripped)
            if char:
                name = char.group(1).strip().split('（')[0].strip()  # 去掉括号备注
                current_char = name
                call_tool("create_character", {"work": work_name, "name": name})
                results.append(f"[系统] 已创建角色「{name}」")
                continue
            # 字段行: age:xxx 或 年龄:xxx 或 age=xxx
            if current_char:
                fld = _re.match(r'\s*(age|年龄|gender|性别|occupation|身份|职业|appearance|外貌|personality|性格|background|背景|goals|目标|notes|备注|aliases|别名)[：:＝=]\s*(.+)', stripped)
                if fld:
                    field_zh = fld.group(1).strip()
                    value = fld.group(2).strip()
                    field_map = {"年龄":"age","age":"age","性别":"gender","gender":"gender",
                                 "身份":"occupation","职业":"occupation","occupation":"occupation",
                                 "外貌":"appearance","appearance":"appearance","性格":"personality",
                                 "personality":"personality","背景":"background","background":"background",
                                 "目标":"goals","goals":"goals","备注":"notes","notes":"notes","别名":"aliases","aliases":"aliases"}
                    field = field_map.get(field_zh, field_zh)
                    call_tool("update_character", {"work": work_name, "name": current_char, "field": field, "value": value})
                    results.append(f"[系统] 已设置{current_char}.{field}")

        if not results:
            return ""

        summary = "\n".join(results)
        self.chat_panel.add_message("assistant",
            f"<p><b>🔧 已自动执行：</b></p><pre>{summary}</pre>")
        return f"\n\n[系统已自动执行以下操作，请直接回应结果，不要重复执行: \n{summary}]"

    def _on_chat_message(self, message: str, scope: str):
        if not self.agent.is_configured():
            self.chat_panel.add_message("assistant", "请先配置 AI 服务：菜单 → 文件 → 设置 → AI 助手，填入 API Key 后即可使用。")
            self.chat_panel.enable_send()
            return

        # 拦截用户消息，预执行 MCP 工具
        inject = self._intercept_and_execute(message)
        context = self.get_context(scope) + inject
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, context))

    def _do_chat(self, message: str, context: str):
        from .worker import AIWorker
        # 设置当前作品名供 _execute_tool 使用
        import os as _os
        _os.environ["REWRITE_CURRENT_WORK"] = self.work_path.name if hasattr(self, 'work_path') else ""
        # enable_tools=True 让 AI 通过 function calling 直接调用 MCP 工具
        self._worker = AIWorker(self.agent, message, context, enable_tools=True)
        self._worker.finished.connect(self._on_ai_response)
        self._worker.error.connect(self._on_ai_error)
        self._worker.start()

    def _on_ai_response(self, response: str):
        self.chat_panel.hide_loading()
        from .markdown_render import markdown_to_html
        self.chat_panel.add_message("assistant", markdown_to_html(response))
        self.chat_panel.enable_send()
        self.chat_panel.update_memory(len(self.agent.history))
        # 只在用户明确要求分析/批注时生成批注，避免工具调用的回复乱塞批注
        try:
            user_msg = ""
            if self.agent.history and len(self.agent.history) >= 2:
                prev = self.agent.history[-2]
                if isinstance(prev, dict):
                    user_msg = prev.get("content", "")
                    if isinstance(user_msg, list):
                        user_msg = " ".join(b.get("text", "") for b in user_msg if isinstance(b, dict))
                elif isinstance(prev, str):
                    user_msg = prev
            if isinstance(user_msg, str) and any(kw in user_msg for kw in ("分析", "批注", "建议", "评价")):
                self._create_module_annotations(response)
        except Exception:
            pass
        self._apply_ai_edits(response)
        self._apply_mcp_tools(response)

        # 刷新模块面板（AI 通过工具修改了文件，需要从磁盘重载）
        parent = self.parent()
        if hasattr(parent, 'modules') and parent.modules:
            chars = parent.modules.get("characters")
            if chars and hasattr(chars, 'load'):
                chars.load()
                dock = parent.docks.get("characters")
                if dock and hasattr(dock, '_build_tree'):
                    dock._build_tree()
            outline = parent.modules.get("outline")
            if outline and hasattr(outline, 'load'):
                outline.load()
                dock2 = parent.docks.get("outline")
                if dock2 and hasattr(dock2, '_build_tree'):
                    dock2._build_tree()
            timeline = parent.modules.get("timeline")
            if timeline and hasattr(timeline, 'load'):
                timeline.load()
                dock3 = parent.docks.get("timeline")
                if dock3 and hasattr(dock3, '_refresh'):
                    dock3._refresh()

        self._worker = None

    def _on_ai_error(self, error_msg: str):
        self.chat_panel.hide_loading()
        self.chat_panel.add_message("assistant", f"[错误] {error_msg}")
        self.chat_panel.enable_send()
        self._worker = None

    def _on_analyze(self):
        if not self.agent.is_configured():
            QMessageBox.information(self.parent(), "提示", "请先在「文件 → 设置 → AI 助手」中配置 API Key")
            return
        context = self.get_context("current_chapter,outline,characters")
        message = "请从情节、人物、节奏、语言等角度全面分析这章内容，给出具体的改进建议。"
        self.chat_panel.show_loading()
        QTimer.singleShot(100, lambda: self._do_chat(message, context))
