"""AI 助手冒烟测试 — 验证易用性修复的关键路径。

运行方式(在项目根目录):
    .venv\\Scripts\\python.exe scripts\\test_ai_assistant.py

说明:
- 全部在临时目录运行,绝不触碰 works/(作品文件夹)
- 无 GUI 需求(自动使用 offscreen 平台)
- 退出码 0 = 全部通过
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication([])

        # ── 1. undo_stack:快照/回滚/失败丢弃 ──
        from src.editor.modules.ai_assistant.undo_stack import AIUndoStack
        work = tmp / "works" / "novel-test1"
        (work / "chapters").mkdir(parents=True)
        (work / "work.json").write_text('{"title": "测试作品", "work_type": "novel"}', encoding="utf-8")
        (work / "characters.json").write_text('{"nodes": [{"name": "张三", "is_group": false}]}', encoding="utf-8")
        (work / "chapters" / "0001_第一章.md").write_text("# 第一章\n\n正文", encoding="utf-8")

        stack = AIUndoStack()
        stack.push("update_character", {"name": "张三"}, work)
        (work / "characters.json").write_text('{"nodes": [{"name": "张三改", "is_group": false}]}', encoding="utf-8")
        info = stack.pop_restore()
        assert info and info["restored"][0].endswith("characters.json")
        assert "张三" in (work / "characters.json").read_text(encoding="utf-8")

        # 失败丢弃:pop_rollback 后栈为空
        stack.push("update_character", {"name": "张三"}, work)
        stack.pop_rollback()
        assert not stack.has_entries()

        # 章节快照(update_chapter 含 "chapter")
        stack.push("update_chapter", {"chapter": "第一章"}, work)
        (work / "chapters" / "0001_第一章.md").write_text("changed", encoding="utf-8")
        info = stack.pop_restore()
        assert info and len(info["restored"]) == 1
        assert (work / "chapters" / "0001_第一章.md").read_text(encoding="utf-8").startswith("# 第一章")

        # 新建文件回滚:create_chapter 撤回后删除 AI 实际创建的文件(精确路径),
        # 用户手动创建的章节(不同路径)不受影响
        stack.push("create_chapter", {"title": "新章"}, work)
        stack.attach_result({"path": "chapters/0002_新章.md"})  # 模拟 skill 返回的实际路径
        (work / "chapters" / "0002_新章.md").write_text("# 新章", encoding="utf-8")
        (work / "chapters" / "0003_手动笔记.md").write_text("# 手动", encoding="utf-8")
        info = stack.pop_restore()
        assert info and not (work / "chapters" / "0002_新章.md").exists(), info
        assert (work / "chapters" / "0003_手动笔记.md").exists(), "误删用户手动创建的章节"
        (work / "chapters" / "0003_手动笔记.md").unlink()  # 清理,避免影响后续用例

        # 非章节工具撤回不得误删其他数据文件(outline.json 等)
        (work / "outline.json").write_text('{"entries": []}', encoding="utf-8")
        stack.push("update_character", {"name": "张三"}, work)
        (work / "characters.json").write_text('{"nodes": [{"name": "张三改", "is_group": false}]}', encoding="utf-8")
        info = stack.pop_restore()
        assert (work / "outline.json").exists(), "非章节工具撤回误删了 outline.json"
        assert (work / "characters.json").read_text(encoding="utf-8").find("张三改") < 0
        print("[1] undo_stack OK")

        # ── 2. orchestrator 参数解析失败标记 ──
        from src.editor.modules.ai_assistant.orchestrator import AIOrchestrator
        noop = lambda *a, **k: None
        orch = AIOrchestrator(noop, noop, noop, noop, noop, noop, noop, noop, noop)
        descs = orch.resolve_proposals([{"function": {"name": "update_character", "arguments": "{bad"}}])
        assert descs[0][1].get("_parse_error") and "参数解析失败" in descs[0][2]
        assert not orch.resolve_proposals(
            [{"function": {"name": "get_characters", "arguments": "{}"}}])[0][1].get("_parse_error")
        print("[2] orchestrator OK")

        # ── 3. 读/写工具分类 ──
        from src.editor.modules.ai_assistant.module import AIAssistantModule
        assert AIAssistantModule._is_read_tool("get_characters")
        assert AIAssistantModule._is_read_tool("read_chapter")
        assert AIAssistantModule._is_read_tool("search_chapters")
        assert not AIAssistantModule._is_read_tool("delete_chapter")
        assert not AIAssistantModule._is_read_tool("create_timeline_event")
        print("[3] classify OK")

        # ── 4. diff 行级高亮 ──
        html_old = AIAssistantModule._diff_html("A\n旧行\nC", "A\n新行\nC", "old")
        assert "background:#FFEBEE" in html_old
        html_new = AIAssistantModule._diff_html("A\n旧行\nC", "A\n新行\nC", "new")
        assert "background:#E8F5E9" in html_new
        print("[4] diff OK")

        # ── 5. 假完成检测(含"已经修改") ──
        from src.editor.modules.ai_assistant.providers import _check_fake_completion
        assert _check_fake_completion("好的,我已经修改了")
        assert _check_fake_completion("✅ 已完成")
        assert not _check_fake_completion("这是对情节的分析")
        print("[5] fake OK")

        # ── 6. contexts 选中文本剥离 ──
        from src.editor.modules.ai_assistant.contexts import collect_context
        ctx = collect_context(["selected_text"], current_selection="<p>你好&nbsp;世界<br>第二行</p>")
        assert "世界" in ctx and "第二行" in ctx and "&nbsp;" not in ctx and "<p>" not in ctx
        print("[6] contexts OK")

        # ── 7. skills 真实读写(临时作品) ──
        os.environ["REWRITE_WORKS_DIR"] = str(tmp / "works")
        from src.editor.modules.ai_assistant.skills.registry import execute_skill
        from src.editor.modules.ai_assistant.skills.chapter_skills import GetChaptersSkill, RenameChapterSkill

        assert execute_skill("create_character", {"name": "李四", "age": "25"}, work_name="novel-test1").get("success")
        r = execute_skill("get_characters", {}, work_name="novel-test1")
        assert any(n.get("name") == "李四" for n in r["nodes"])
        assert execute_skill("create_chapter", {"title": "第二章"}, work_name="novel-test1").get("success")
        chaps = GetChaptersSkill().execute({}, "novel-test1")
        assert any(c["format"] == "md" for c in chaps["chapters"])  # .md 章节可见
        r = RenameChapterSkill().execute({"chapter": "第二章", "new_name": "第二章 转折"}, "novel-test1")
        assert r.get("success") and r.get("path", "").endswith(".md")  # 后缀不漂移
        r = execute_skill("update_chapter", {"chapter": "不存在", "content": "x"}, work_name="novel-test1")
        assert r.get("success") is False and "未找到章节" in r.get("error", "")  # 真实报错

        # update_chapter 直写路径:内容为真实 Markdown(不能用 JSON 序列化损坏章节),
        # 且经过规范化(标题后空行/尾随换行)
        r = execute_skill("update_chapter", {"chapter": "第一章", "content": "# 第一章\n\n新正文内容"},
                          work_name="novel-test1")
        assert r.get("success") is True, r
        content = (work / "chapters" / "0001_第一章.md").read_text(encoding="utf-8")
        assert content == "# 第一章\n\n新正文内容\n", repr(content)

        # 非法 work 名防御:无效作品目录直接报错,不创建隐藏目录
        r = execute_skill("create_chapter", {"title": "X"}, work_name="..\\evil")
        assert r.get("success") is False and "未找到作品" in r.get("error", ""), r
        # _work_path 拒绝绝对路径/盘符形式,回退到点前缀的无效名
        from src.editor.modules.ai_assistant.skills._shared import _work_path as _wp2
        assert str(_wp2("C:foo")).endswith(".__invalid_work_name__")
        assert str(_wp2("/etc/passwd")).endswith(".__invalid_work_name__")
        assert str(_wp2("../../x")).endswith(".__invalid_work_name__")
        print("[7] skills OK")

        # ── 8. chat_panel:会话级删除/clear 链路/菜单/历史回放 ──
        from src.editor.modules.ai_assistant.ui.chat_panel import ChatPanel, ConfirmBubble
        panel = ChatPanel()
        assert len(panel.scope_chips) == 8
        # 历史回放(track=False)不记录会话起点,避免启动后撤回清空全部历史
        panel.add_message("user", "历史1", track=False)
        panel.add_message("assistant", "历史2", track=False)
        assert panel._session_first_bubble is None, "历史回放不应记录会话起点"
        b1 = panel.add_message("user", "第一条(旧对话)")
        panel._session_first_bubble = None  # 模拟新一轮对话
        b2 = panel.add_message("user", "新问题")
        b3 = panel.add_message("assistant", "回复1")
        b4 = panel.add_message("assistant", "回复2")
        panel.remove_session()
        assert panel.messages_layout.indexOf(b1) >= 0   # 旧对话保留
        assert panel.messages_layout.indexOf(b2) < 0    # 本轮删除
        assert panel.messages_layout.indexOf(b4) < 0
        assert panel._session_first_bubble is None

        fired = []
        panel.clear_requested.connect(lambda: fired.append(1))
        # 按文本定位「清空记忆」菜单项(不依赖菜单项顺序)
        clear_act = next(a for a in panel.mem_menu_btn.menu().actions()
                         if a.text() == "清空记忆")
        clear_act.trigger()
        assert fired == [1], "clear_requested 未触发"
        panel.update_memory(3)
        assert "3" in panel.mem_menu_btn.text()

        # ── 8b. 紧凑侧边栏:宽度约束/芯片折叠/快捷指令菜单 ──
        assert panel.minimumWidth() == 300, "侧边栏最窄保护 300"
        assert panel.maximumWidth() >= 1000, "不锁定最大宽度(可拖宽到接近正文)"
        assert panel._extra_widget.isHidden(), "第二行芯片默认收起"
        assert panel._extra_widget.layout().count() == 5, "展开行含 4 芯片 + stretch"
        panel._more_btn.setChecked(True)
        assert not panel._extra_widget.isHidden(), "点 ⋯ 应展开第二行芯片"
        panel._more_btn.setChecked(False)
        assert panel._extra_widget.isHidden()
        assert hasattr(panel, "quick_menu_btn") and panel.quick_menu_btn.menu(), "快捷指令菜单"
        # 快捷指令菜单:实际 trigger「写作助手」应勾选对应芯片组合
        preset_actions = {a.text(): a for a in panel.quick_menu_btn.menu().actions()}
        preset_actions["写作助手"].trigger()
        assert panel.scope_chips["current_chapter"].isChecked()
        assert panel.scope_chips["characters"].isChecked()
        assert not panel.scope_chips["timeline"].isChecked()
        panel._apply_preset(["current_chapter", "outline"])
        assert panel.scope_chips["current_chapter"].isChecked()
        assert not panel.scope_chips["worldview"].isChecked()
        # 8c. 面板显示时自动滚动到最新消息(修复打开停在很早消息的问题)
        scroll_calls = []
        _orig_scroll = panel._scroll_to_bottom
        panel._scroll_to_bottom = lambda: scroll_calls.append(1)
        try:
            panel.show()
            for _ in range(10):
                app.processEvents()
            assert scroll_calls, "show 后应自动滚动到底部"
        finally:
            panel._scroll_to_bottom = _orig_scroll
            panel.hide()

        # 8d. AI 工作状态:锁定发言栏 + 思考中提示条
        panel.input_edit.setPlainText("测试")
        panel.set_busy(True)
        assert not panel.status_indicator.isHidden(), "busy 时应显示思考中提示"
        assert not panel.input_edit.isEnabled(), "busy 时输入框应禁用"
        assert not panel.send_btn.isEnabled(), "busy 时发送按钮应禁用"
        assert not panel.undo_btn.isEnabled(), "busy 时撤回按钮应禁用"
        panel.set_busy(False)
        assert panel.status_indicator.isHidden(), "空闲时提示条隐藏"
        assert panel.input_edit.isEnabled(), "空闲时输入框恢复"
        assert panel.send_btn.isEnabled(), "空闲时发送按钮按内容恢复"
        print("[8] chat_panel OK")

        # ── 9. ConfirmBubble 全部允许 ──
        b = ConfirmBubble(["操作"], [{"function": {"name": "x", "arguments": "{}"}}])
        got = []
        b.auto_confirmed.connect(lambda tcs: got.append(tcs))
        b._on_auto_confirm()
        assert got and not b.confirm_btn.isEnabled()
        print("[9] ConfirmBubble OK")

        # ── 10. compress worker:构造传参 + 内部 import(防 NameError/GC) ──
        import inspect
        from src.editor.modules.ai_assistant import module as mod_module
        src = inspect.getsource(mod_module)
        assert "def __init__(self, config, history_text, parent=None)" in src
        assert "import json as _json" in src
        assert "self._compress_worker = w" in src

        # ── 11. render_message:reasoning 内容需转义,防 HTML 注入 ──
        from src.editor.modules.ai_assistant.orchestrator import AIOrchestrator
        html = AIOrchestrator.render_message(
            "<!--REASONING-->\n<img src=x onerror=alert(1)>\n<!--/REASONING-->\n\n正文")
        assert "<img" not in html and "&lt;img" in html, html
        print("[10] compress worker OK")
        print("[11] reasoning escape OK")

        from src.editor.modules.outline import OutlineModule, OutlineDock
        om = OutlineModule(work)
        om.entries = [
            {"id": "e1", "title": "第一卷", "content": "", "children": [
                {"id": "e2", "title": "第一章", "content": "有内容的条目", "children": [], "status": "写作中"},
                {"id": "e3", "title": "第二章", "content": "", "children": [], "status": "已完成"},
            ], "status": "待写"},
        ]
        om.entries = [om._from_dict(e) for e in om.entries]
        dock = OutlineDock(om)

        # 树项文本:无 ▶/▼ 前缀,含状态图标(跳过隐藏占位子项)
        def _all_items(parent=None):
            n = parent.childCount() if parent else dock.tree.topLevelItemCount()
            out = []
            for i in range(n):
                it = parent.child(i) if parent else dock.tree.topLevelItem(i)
                if not it.flags():
                    continue  # 占位子项(NoItemFlags)
                out.append(it)
                out += _all_items(it)
            return out
        items = _all_items()
        assert len(items) == 3, len(items)
        for it in items:
            t = it.text(0)
            assert "▶" not in t and "▼" not in t, t
        # 状态着色:写作中条目为 PRIMARY_DARK 色
        by_id = {it.data(0, 256): it for it in items}
        assert by_id["e2"].foreground(0).color().name().upper() == "#1976D2", by_id["e2"].foreground(0).color().name()

        # 有内容无子项的条目 → 占位子项隐藏(折叠时无空白行)
        e2_item = by_id["e2"]
        assert e2_item.childCount() == 1
        ph = e2_item.child(0)
        assert ph.isHidden(), "占位子项应隐藏"
        assert not ph.flags(), "占位子项应无 flags"

        # 展开 → 编辑器出现且占位项可见;折叠 → 编辑器移除且占位项隐藏
        dock._on_item_expanded(e2_item)
        assert "e2" in dock._editor_widgets and not ph.isHidden()
        dock._on_item_collapsed(e2_item)
        assert "e2" not in dock._editor_widgets and ph.isHidden()

        # 详情区:选中条目后标题/状态 radio 同步
        dock.tree.setCurrentItem(e2_item)
        assert dock.detail_title.text() == "✏ 第一章"
        assert dock.status_radios["写作中"].isChecked()
        # 状态切换:点"已完成"→ 数据更新 + 树图标刷新
        dock._on_status_changed("已完成")
        assert om._find_entry(om.entries, "e2").status == "已完成"
        e2_items2 = [it for it in _all_items() if it.data(0, 256) == "e2"]
        assert e2_items2 and e2_items2[0].text(0).startswith("●"), e2_items2[0].text(0)

        # 展开编辑器编辑 → 切状态:详情区旧快照不得覆盖展开编辑器新内容(dirty 机制)
        om._find_entry(om.entries, "e2").content = "旧快照Z"
        e2_cur = [it for it in _all_items() if it.data(0, 256) == "e2"][0]
        dock.tree.setCurrentItem(e2_cur)  # 详情区填充旧快照,dirty=False
        assert dock._detail_dirty is False
        om._find_entry(om.entries, "e2").content = "展开新内容X"  # 模拟展开编辑器写回
        dock._on_status_changed("待写")
        assert om._find_entry(om.entries, "e2").content == "展开新内容X", \
            "详情区旧快照覆盖了展开编辑器新内容"
        # 用户实际编辑详情区 → dirty 置位并正常保存
        dock.detail_edit.setPlainText("用户编辑Y")
        assert dock._detail_dirty is True
        dock._on_status_changed("写作中")
        assert om._find_entry(om.entries, "e2").content == "用户编辑Y", \
            "用户编辑内容未保存"

        # 反方向:详情编辑 → 切状态:展开编辑器旧快照不得覆盖详情新内容(wrapper dirty)
        dock.tree.setCurrentItem(
            [it for it in _all_items() if it.data(0, 256) == "e2"][0])
        dock.detail_edit.setPlainText("详情新内容W")  # dirty=True
        from src.editor.modules.outline import ContentEditWrapper as _CEW
        dock._editor_widgets["e2"] = _CEW("e2", "展开旧快照", None)  # 展开编辑器未编辑
        assert dock._editor_widgets["e2"].is_dirty() is False
        dock._on_status_changed("已完成")
        assert om._find_entry(om.entries, "e2").content == "详情新内容W", \
            "展开编辑器旧快照覆盖了详情新内容"
        dock._editor_widgets.clear()  # 清理模拟 wrapper

        # 12b. 重建保留展开状态(更改条目后子条目不再自动收起)
        from PySide6.QtCore import Qt as _Qt12
        e1_item = dock.tree.topLevelItem(0)
        assert e1_item.data(0, _Qt12.ItemDataRole.UserRole) == "e1"
        e1_item.setExpanded(True)
        dock._build_tree()
        e1_item = dock.tree.topLevelItem(0)
        assert e1_item.isExpanded(), "重建后应保持展开"
        # 未展开的子条目保持收起(按 UserRole 定位,不依赖子项位置)
        for i in range(e1_item.childCount()):
            child = e1_item.child(i)
            if child.data(0, _Qt12.ItemDataRole.UserRole):
                assert not child.isExpanded(), "未展开的子条目保持收起"
        # 有内容条目展开 → 重建后编辑器重新挂载
        e2_item = next(e1_item.child(i) for i in range(e1_item.childCount())
                       if e1_item.child(i).data(0, _Qt12.ItemDataRole.UserRole) == "e2")
        e2_item.setExpanded(True)
        assert "e2" in dock._editor_widgets, "展开应挂载内容编辑器"
        dock._build_tree()
        e1_item = dock.tree.topLevelItem(0)
        assert e1_item.isExpanded(), "重建后 e1 仍展开"
        e2_new = next(e1_item.child(i) for i in range(e1_item.childCount())
                      if e1_item.child(i).data(0, _Qt12.ItemDataRole.UserRole) == "e2")
        assert e2_new.isExpanded(), "重建后 e2 仍展开"
        assert "e2" in dock._editor_widgets, "重建后编辑器应重新挂载"
        dock._editor_widgets.clear()

        # ── 13. 大纲文档视图往返:内容行归属,to_text→from_text 内容不丢 ──
        # 文档文本:标题行 + 无 # 前缀的内容行
        doc_text = "# [ ] 第一卷\n  第一卷第1行\n  第一卷第2行\n## [x] 第一章\n  第一章内容"
        om2 = OutlineModule(work)
        om2.from_text(doc_text)
        assert len(om2.entries) == 1 and om2.entries[0].title == "第一卷"
        assert om2.entries[0].content == "第一卷第1行\n第一卷第2行", om2.entries[0].content
        assert len(om2.entries[0].children) == 1
        assert om2.entries[0].children[0].content == "第一章内容"
        # 往返:to_text → from_text 内容保留
        text1 = om2.to_text()
        om3 = OutlineModule(work)
        om3.from_text(text1)
        assert om3.entries[0].content == "第一卷第1行\n第一卷第2行"
        assert om3.entries[0].children[0].content == "第一章内容"
        # 空解析不动现有数据
        om3.from_text("")
        assert len(om3.entries) == 1, "空解析不应清空现有数据"
        # 原子写:save 后无 .tmp 残留
        om3.save()
        assert not (work / "outline.json.tmp").exists()
        print("[13] outline from_text OK")

        # ── 14. 世界观重构:统一 Markdown 存储/HTML 迁移/原子写/自动保存 ──
        from src.editor.modules.worldview import WorldviewModule, WorldviewDock
        wm = WorldviewModule(work)
        # 旧 HTML 数据 load 时自动迁移为纯文本
        wm.data_path.write_text(json.dumps({"entries": [{
            "id": "w1", "title": "世界设定",
            "content": "<p><b>神明</b>与人类</p><p>第二段</p>",
            "children": [{"id": "w2", "title": "地理", "content": "<p>大陆</p>"}],
        }]}, ensure_ascii=False), encoding="utf-8")
        wm.load()
        assert wm.entries[0].content == "神明与人类\n第二段", wm.entries[0].content
        assert wm.entries[0].children[0].content == "大陆"
        # 迁移后已落盘:再次 load 内容为纯文本(无 HTML 标签)
        wm2 = WorldviewModule(work)
        wm2.load()
        assert "<" not in wm2.entries[0].content
        # 原子写无 tmp 残留
        assert not (work / "worldview.json.tmp").exists()

        # Dock 编辑:富文本加载 → 保存导出(Markdown 无损往返)
        wdock = WorldviewDock(wm)
        wdock.tree.setCurrentItem(wdock.tree.topLevelItem(0))
        assert "神明与人类" in wdock.editor.toPlainText()
        assert "第二段" in wdock.editor.toPlainText()
        md_text = "**新内容** 与 *斜体*\n\n- 列表1\n\n|A|B|\n|-|-|\n|1|2|"
        wdock.editor.setPlainText(md_text)
        wdock._on_save_current()
        saved = wm.entries[0].content
        assert "**新内容**" in saved and "- 列表1" in saved, saved
        # 富文本格式化操作(所见即所得)
        wdock._toggle_bold()
        wdock._insert_table()
        wdock._on_save_current()
        # 自动保存真正落盘
        wdock._auto_save()
        wm3 = WorldviewModule(work)
        wm3.load()
        assert "列表1" in wm3.entries[0].content, "自动保存未落盘"

        # ── 15. 世界观所见即所得:富文本单窗编辑 + 无损 Markdown 导出 ──
        from src.editor.modules.md_document import (
            load_markdown_into, save_markdown_from, document_to_markdown)
        wdock.tree.setCurrentItem(wdock.tree.topLevelItem(0))
        # 加载:MD → 富文本渲染(粗体字符格式真实存在于文档)
        load_markdown_into(wdock.editor, "# 标题\n\n**加粗文本** 和 *斜体*")
        doc = wdock.editor.document()
        bold_found = False
        block = doc.begin()
        while block.isValid():
            for fr in block.textFormats():
                if fr.format.fontWeight() >= 700:
                    bold_found = True
            block = block.next()
        assert bold_found, "加载后编辑器未渲染粗体格式"
        # 保存:富文本 → 无损 Markdown(** 标记恢复)
        md_out = save_markdown_from(wdock.editor)
        assert "**加粗文本**" in md_out, md_out
        assert "# 标题" in md_out, md_out
        # 表格往返:渲染成真表格,导出还原
        wdock.editor.clear()
        load_markdown_into(wdock.editor, "|A|B|\n|-|-|\n|1|2|")
        md_out2 = save_markdown_from(wdock.editor)
        assert "| 1 | 2 |" in md_out2, md_out2
        # 列表往返
        wdock.editor.clear()
        load_markdown_into(wdock.editor, "- a\n- b")
        md_out3 = save_markdown_from(wdock.editor)
        assert "- a" in md_out3 and "- b" in md_out3, md_out3
        # 直接文档往返稳定性
        d = wdock.editor.document()
        md_a = document_to_markdown(d)
        assert md_a.strip(), "导出不应为空"

        # heading 即时渲染:直接字符格式(不依赖 Qt 样式表)——点 H2 立即变大加粗
        wdock.editor.setPlainText("普通段落")
        wdock._set_heading(2)
        c2 = wdock.editor.textCursor()
        c2.movePosition(c2.MoveOperation.StartOfBlock)
        c2.movePosition(c2.MoveOperation.Right, c2.MoveMode.KeepAnchor, 1)
        fmt = c2.charFormat()
        assert fmt.fontPointSize() == 15, f"H2 字号未即时生效: {fmt.fontPointSize()}"
        assert fmt.fontWeight() >= 700, "H2 未加粗"
        # 导出仍为 Markdown 标题
        md_out_h = save_markdown_from(wdock.editor)
        assert "## 普通段落" in md_out_h, md_out_h
        # 恢复正文:字号回到 14、不加粗
        wdock._set_heading(0)
        c3 = wdock.editor.textCursor()
        c3.movePosition(c3.MoveOperation.StartOfBlock)
        c3.movePosition(c3.MoveOperation.Right, c3.MoveMode.KeepAnchor, 1)
        fmt3 = c3.charFormat()
        assert fmt3.fontPointSize() == 14, f"正文字号未恢复: {fmt3.fontPointSize()}"
        assert fmt3.fontWeight() < 700, "正文不应加粗"
        # 空块场景:空行点 H2 后,后续输入按标题样式(当前默认格式生效)
        wdock.editor.insertPlainText("\n")
        wdock._set_heading(1)
        wdock.editor.insertPlainText("新标题文字")
        c4 = wdock.editor.textCursor()
        c4.movePosition(c4.MoveOperation.StartOfBlock)
        c4.movePosition(c4.MoveOperation.Right, c4.MoveMode.KeepAnchor, 2)
        fmt4 = c4.charFormat()
        assert fmt4.fontPointSize() == 17, f"空块后续输入未按标题样式: {fmt4.fontPointSize()}"
        md_out_h2 = save_markdown_from(wdock.editor)
        assert "# 新标题文字" in md_out_h2, md_out_h2

        # 选中块内部分文本点 H2 → 拆出独立标题块,其余保持正文
        # (经 load_markdown_into 加载,重置可能残留的当前字符格式)
        from src.editor.modules.md_document import load_markdown_into as _lmi2
        _lmi2(wdock.editor, "这是铜币描述,后面还有换算关系")
        c = wdock.editor.textCursor()
        c.setPosition(0)
        c.setPosition(2, c.MoveMode.KeepAnchor)  # 选中"这是"
        wdock.editor.setTextCursor(c)
        wdock._set_heading(2)
        md_split = save_markdown_from(wdock.editor)
        assert "## 这是\n\n铜币描述" in md_split, md_split
        assert md_split.count("##") == 1, md_split
        # 段首拆分无空块残留:标题块 + 正文块 = 2 块
        assert wdock.editor.document().blockCount() == 2, \
            f"段首拆分残留空块: {wdock.editor.document().blockCount()} 块"

        # 多块条目:选中第二段行首文字点 H2 → 仅该段拆出标题,第一段不受影响
        _lmi2(wdock.editor, "第一行内容\n\n铜币描述,后面还有换算关系")
        c = wdock.editor.textCursor()
        c.movePosition(c.MoveOperation.Start)
        c.movePosition(c.MoveOperation.Down)  # 第二段首(加载渲染为 2 块,无空分隔块)
        c.movePosition(c.MoveOperation.Right, c.MoveMode.KeepAnchor, 2)  # 选中"铜币"
        wdock.editor.setTextCursor(c)
        wdock._set_heading(2)
        md_multi = save_markdown_from(wdock.editor)
        assert "第一行内容" in md_multi, md_multi
        assert "## 铜币" in md_multi, md_multi
        assert "描述,后面还有换算关系" in md_multi and "## 描述" not in md_multi, md_multi
        # 结构:第一行 + 标题"铜币" + 正文"描述..." = 3 块(加载渲染无空分隔块)
        assert wdock.editor.document().blockCount() == 3, \
            f"多块拆分块数异常: {wdock.editor.document().blockCount()}"
        print("[15] worldview WYSIWYG OK")

        # 视图切换按钮与初始状态(offscreen 下用 isHidden 判断显式隐藏)
        assert dock.view_toggle.text() == "文档视图" and not dock.view_toggle.isChecked()
        assert dock.doc_edit.isHidden()  # 初始 doc 显式隐藏
        dock.view_toggle.setChecked(True)
        assert not dock.doc_edit.isHidden() and dock.tree.isHidden()
        dock.view_toggle.setChecked(False)
        assert not dock.tree.isHidden() and dock.doc_edit.isHidden()
        # ── 16. 主题系统:多主题切换 + Color 跟随 + 外观页选择/预览 ──
        from src.ui.theme import (Color, get_theme_names, get_theme_colors,
                                  get_current_theme, set_theme, apply_theme)
        assert len(get_theme_names()) >= 4, get_theme_names()
        assert {"light_blue", "paper", "dark", "sakura"} <= set(get_theme_names())
        # 切换主题:Color 类属性即时跟随(全部模块引用自动生效)
        set_theme("dark")
        assert Color.BG == "#1E222A" and Color.PRIMARY == "#5B9BD5"
        assert get_current_theme() == "dark"
        assert get_theme_colors("dark")["SURFACE"] == "#2B313D"
        # 恢复浅青蓝
        set_theme("light_blue")
        assert Color.BG == "#f0f6fa"
        # apply_theme 即时生效(palette + 全局 QSS)
        app2 = QApplication.instance()
        apply_theme("sakura", app2)
        assert Color.PRIMARY == "#E27396"
        # 外观页:卡片齐全、选中切换预览即时更新
        from src.settings.appearance_settings import AppearanceSettingsPage, ThemeCard
        ap = AppearanceSettingsPage()
        assert len(ap._cards) == len(get_theme_names())
        assert ap.current in get_theme_names(), ap.current
        # 4 主题 token 集合完整性(与 Color 大写 token 一致)
        color_tokens = {k for k in dir(Color) if k.isupper()}
        for name in get_theme_names():
            assert set(get_theme_colors(name).keys()) == color_tokens, name
        # ThemeCard 使用 objectName 选择器,选中态样式含主色
        card = ThemeCard("dark", get_theme_colors("dark"))
        assert card.objectName() == "themeCard"
        card.set_selected(True)
        assert Color.PRIMARY in card.styleSheet() or card.styleSheet().count("border") > 0
        ap._on_card_selected("dark")
        assert ap.current == "dark"
        assert ap.preview._colors["BG"] == "#1E222A", "预览未随主题更新"
        # 预览重建后布局有效(blocking 修复验证)
        ap.preview.set_theme("sakura")
        assert ap.preview.layout().count() > 0, "预览重建后布局为空"
        assert ap.preview._colors["PRIMARY"] == "#E27396"
        ap._on_card_selected("light_blue")
        assert ap.current == "light_blue"
        # 恢复默认主题,避免影响后续状态
        set_theme("light_blue")

        # ── 17. 启动页/框架主题化:创建时跟随 + refresh_theme 即时刷新 ──
        from src.storage.workspace import Workspace
        from src.launcher.window import LauncherWindow
        ws = Workspace(tmp / "works")  # 空 works,scan 返回空列表
        lw = LauncherWindow(ws)
        # 按钮样式已 token 化(含具体色值)
        assert "#f0f6fa" in lw.styleSheet(), "启动页初始背景非主题色"
        # 深色主题 → refresh_theme 即时刷新背景、按钮与标题栏
        apply_theme("dark", app2)
        lw.refresh_theme()
        assert "#1E222A" in lw.styleSheet(), "启动页背景未随主题刷新"
        assert "#5B9BD5" in lw.new_btn.styleSheet(), "启动页按钮未随主题刷新"
        assert "#2B313D" in lw.title_bar.styleSheet(), "标题栏未随主题刷新"
        # 恢复浅青蓝
        apply_theme("light_blue", app2)
        lw.refresh_theme()
        assert "#f0f6fa" in lw.styleSheet(), "恢复浅青蓝失败"
        assert "#ffffff" in lw.title_bar.styleSheet(), "标题栏恢复失败"
        lw.close()

        # ── 18. 批注独立模块:锚点重定位/手动入口/边条/悬停提示 ──
        from src.editor.annotations.manager import AnnotationManager, Annotation, _find_text
        am = AnnotationManager(work)
        am.add_annotation("chapter", "chapters/0001_第一章.md", "第一章",
                          "建议改写", highlight_text="正文内容", start_pos=0, end_pos=4)
        # 锚点重定位:内容前插后位置漂移 → relocate 用 highlight_text 找回
        am.relocate_chapter("chapters/0001_第一章.md", "开头新增内容。正文内容后移")
        a = am.get_chapter_annotations("chapters/0001_第一章.md")[0]
        assert a.start_pos >= 0 and a.end_pos > a.start_pos, "relocate 未重定位"
        # 彻底找不到 → 位置 -1,批注与建议保留
        am.relocate_chapter("chapters/0001_第一章.md", "完全不同的文本")
        a2 = am.get_chapter_annotations("chapters/0001_第一章.md")[0]
        assert a2.start_pos == -1 and a2.suggestion == "建议改写"
        # 标点容错搜索(坐标映射回原文)
        assert _find_text("他走了,她哭了。", "他走了她哭了") != (-1, -1)
        sp, ep = _find_text("他走了,她哭了。", "她哭了")
        assert sp == 4 and ep == 7, (sp, ep)
        # 保存/加载往返(独立文件,不写入正文)
        am.save()
        am2 = AnnotationManager(work)
        am2.load()
        assert len(am2.annotations) == 1 and am2.annotations[0].target_title == "第一章"
        # 编辑器:手动批注信号 + 高亮悬停提示 + 右侧边条标记
        from src.editor.editor_widget import EditorWidget
        from src.editor.annotations.gutter import AnnotationGutter
        ew = EditorWidget()
        got = []
        ew.annotation_requested.connect(lambda t, s: got.append((t, s)))
        ann3 = Annotation(target_type="chapter", target_path="x", target_title="t",
                          suggestion="建议改写", highlight_text="第一章正文内容",
                          start_pos=0, end_pos=6)
        ew.setPlainText("第一章正文内容")
        ew.set_annotations([ann3])
        # 悬停 tooltip 含状态与建议
        c = ew.textCursor()
        c.movePosition(c.MoveOperation.Start)
        c.movePosition(c.MoveOperation.Right, c.MoveMode.KeepAnchor, 2)
        tip = c.charFormat().toolTip()
        assert "待处理" in tip and "建议改写" in tip, tip
        # 边条生成 1 个位置标记
        gutter = AnnotationGutter(ew)
        gutter._update_marks()
        assert len(gutter._marks) == 1, f"边条标记数: {len(gutter._marks)}"

        # ── 19. AI 批注端到端:解析/定位/保存/双击跳转 ──
        from src.editor.modules.ai_assistant.module import AIAssistantModule
        from PySide6.QtWidgets import QWidget
        # 独立 works 目录,避免 [18] 的批注残留干扰
        work19 = tmp / "works19"
        work19.mkdir(parents=True, exist_ok=True)
        (work19 / "work.json").write_text('{"title": "t"}', encoding="utf-8")
        ew2 = EditorWidget()
        ew2.setPlainText("克诺走在特因城的街道上,口袋里只有两枚铜币。")
        ew2.set_current_chapter("chapters/0001_第一章.md")
        fw = QWidget()
        fw.modules = {}
        fw.docks = {}
        fw._load_chapter_content = lambda p: ew2.set_current_chapter(p)
        amod = AIAssistantModule(work19, fw)
        amod.set_editor(ew2)
        amod.annotation_panel = None  # 测试环境无 dock,产品代码已 getattr 防御
        # AI 回复含 [ANNOTATION:chapter] + [QUOTE]
        response = ("分析如下:\n"
                    "[ANNOTATION:chapter:第一章]\n"
                    "[QUOTE]克诺走在特因城的街道上[/QUOTE]\n"
                    "建议:增加环境描写\n[/ANNOTATION]")
        amod._create_module_annotations(response)
        anns = amod.annotation_mgr.get_chapter_annotations("chapters/0001_第一章.md")
        assert len(anns) == 1, anns
        a = anns[0]
        assert a.start_pos == 0 and a.end_pos > 0, (a.start_pos, a.end_pos)
        assert a.suggestion == "建议:增加环境描写", a.suggestion
        # 保存+加载往返(独立文件持久)
        amod.annotation_mgr.save()
        amod2 = AIAssistantModule(work19, QWidget())
        amod2.annotation_mgr.load()
        assert len(amod2.annotation_mgr.annotations) == 1, "AI 批注未持久化"
        # 双击跳转:切换到该章节并定位光标到批注位置
        ew3 = EditorWidget()
        ew3.setPlainText("其他章节内容")
        fw3 = QWidget()
        fw3.modules = {}
        fw3.docks = {}
        fw3._load_chapter_content = lambda p: ew3.set_current_chapter(p)
        amod3 = AIAssistantModule(work19, fw3)
        amod3.set_editor(ew3)
        amod3.annotation_mgr.load()
        amod3._on_annotation_clicked(amod3.annotation_mgr.annotations[0].id)
        assert ew3.current_chapter_path() == "chapters/0001_第一章.md", \
            "双击批注未切换章节"
        c3 = ew3.textCursor()
        assert c3.position() == 0, f"双击批注未定位光标: {c3.position()}"
        # 人物批注双击 → 置前面板(复数 dock 键归一)
        from src.editor.annotations.manager import Annotation as _Ann
        class _FakeDock:
            def __init__(self):
                self.shown = 0
            def show(self):
                self.shown += 1
            def raise_(self):
                pass
        fd = _FakeDock()
        fw3.docks = {"characters": fd}
        amod3.annotation_mgr.annotations.append(
            _Ann(target_type="character", target_path="c1", target_title="克诺",
                 suggestion="s", source="manual"))
        amod3._on_annotation_clicked(amod3.annotation_mgr.annotations[-1].id)
        assert fd.shown == 1, "人物批注双击未置前面板"
        print("[19] AI annotations OK")

        # ── 20. 章节路径穿越防御 + 批注字段类型校验(security) ──
        from src.editor.modules.chapters import ChapterModule
        cm2 = ChapterModule(work)
        # 外部绝对路径被拒绝(读/写)
        assert cm2.read_chapter(Path("C:/Windows/win.ini")) == ""
        assert cm2.write_chapter(Path("C:/Windows/win.ini"), "x") is False
        # 作品内相对路径(基于作品根)可正常读取
        assert cm2.read_chapter(Path("chapters/0001_第一章.md")) != ""
        # 越界相对路径被拒绝
        assert cm2.read_chapter(Path("../outside.md")) == ""
        assert cm2.write_chapter(Path("../outside.md"), "x") is False
        # 非法字段类型:from_dict 返回 None 且 load 丢弃
        from src.editor.annotations.manager import Annotation as _Ann2
        assert _Ann2.from_dict({"target_type": "chapter", "start_pos": "bad"}) is None
        assert _Ann2.from_dict({"id": "x", "target_type": "chapter", "target_path": "p",
                                "target_title": "t", "suggestion": "s", "highlight_text": "h",
                                "start_pos": 0, "end_pos": 1, "status": "pending",
                                "source": "manual"}) is not None
        print("[20] security cases OK")

        # ── 21. 老格式绝对路径批注兼容 + ignored 不高亮 + 状态刷新 ──
        from src.editor.annotations.manager import AnnotationManager
        mgr21 = AnnotationManager(work)
        abs_path = str((work / "chapters" / "0001_第一章.md").resolve())
        mgr21.annotations = [
            _Ann(target_type="chapter", target_path=abs_path, target_title="第一章",
                 suggestion="旧格式绝对路径", highlight_text="克诺",
                 start_pos=0, end_pos=2, status="pending", source="manual"),
            _Ann(target_type="chapter", target_path="chapters/0001_第一章.md",
                 target_title="第一章", suggestion="已忽略", highlight_text="街上",
                 start_pos=3, end_pos=5, status="ignored", source="manual"),
        ]
        mgr21.save()
        mgr21.load()  # load 时应把绝对路径归一为相对路径
        assert mgr21.annotations[0].target_path == "chapters/0001_第一章.md", \
            mgr21.annotations[0].target_path
        got = mgr21.get_chapter_annotations("chapters/0001_第一章.md")
        assert len(got) == 2, f"老格式绝对路径批注扫描不到: {len(got)}"
        # ignored 批注不渲染高亮,pending 正常渲染
        ew21 = EditorWidget()
        ew21.setPlainText("克诺走在街上。")
        ew21.set_annotations(got)
        from PySide6.QtGui import QTextCursor
        c21 = ew21.textCursor()
        c21.setPosition(0); c21.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        assert c21.charFormat().background().color().name() == "#e8f5e9", "pending 批注未高亮"
        c21.setPosition(3); c21.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
        assert c21.charFormat().background().color().name() != "#e8f5e9", "ignored 批注不应高亮"
        # 先渲染后忽略:旧高亮应被清除(即时刷新场景)
        ew22 = EditorWidget()
        ew22.setPlainText("克诺走在街上。")
        ew22.set_annotations([a for a in got if a.status == "pending"])
        c22 = ew22.textCursor()
        c22.setPosition(0); c22.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        assert c22.charFormat().background().color().name() == "#e8f5e9", "首轮渲染未高亮"
        for a in got:
            if a.status == "pending":
                mgr21.update_status(a.id, "ignored")
        ew22.set_annotations(mgr21.get_chapter_annotations("chapters/0001_第一章.md"))
        c22.setPosition(0); c22.setPosition(1, QTextCursor.MoveMode.KeepAnchor)
        assert c22.charFormat().background().color().name() != "#e8f5e9", "忽略后旧高亮未清除"
        # 状态变更 → 刷新回调
        from PySide6.QtWidgets import QWidget as _QWidget
        class _FW(_QWidget):
            def __init__(self):
                super().__init__()
                self.called = 0
            def _refresh_chapter_annotations(self):
                self.called += 1
        fw21 = _FW()
        amod21 = AIAssistantModule(work19, fw21)
        amod21._on_annotation_status_changed("x")
        assert fw21.called == 1, "状态变更未触发高亮刷新"
        # panel.refresh() 覆盖 TextFormatRole 兼容(回归:PySide6 枚举缺失崩溃)
        from src.editor.annotations.panel import AnnotationListPanel
        pnl21 = AnnotationListPanel(mgr21)
        pnl21.refresh()  # 不抛 AttributeError 即通过
        assert pnl21.list_widget.count() == 2, f"列表项数: {pnl21.list_widget.count()}"
        print("[21] legacy path + status refresh OK")

        # ── 22. 浮动 dock 关闭后自动停靠回原位 ──
        from src.ui.dock_utils import DockCloseReturnFilter
        from PySide6.QtWidgets import QMainWindow, QDockWidget
        from PySide6.QtCore import Qt as _Qt22
        win22 = QMainWindow()
        dk22 = QDockWidget("测试面板")
        win22.addDockWidget(_Qt22.DockWidgetArea.RightDockWidgetArea, dk22)
        dk22.installEventFilter(DockCloseReturnFilter(win22))
        win22.show()
        dk22.setFloating(True)
        assert dk22.isFloating(), "前置:面板应处于浮动状态"
        dk22.close()  # 模拟点击浮动窗口关闭按钮
        assert not dk22.isFloating(), "浮动关闭后未停靠回 dock 位置"
        assert not dk22.isVisible(), "关闭后应隐藏"
        dk22.show()  # 重新打开
        assert dk22.isVisible() and not dk22.isFloating(), "重新打开应显示在 dock 位置"
        dk22.deleteLater()
        win22.deleteLater()
        print("[22] dock close return OK")

        # ── 23. 窗口过渡动画(fade_in/fade_out) ──
        from src.ui.animations import fade_in, fade_out
        from PySide6.QtCore import QEventLoop, QTimer as _QT23
        import time as _time23
        w23 = QMainWindow()
        w23.show()
        anims23 = fade_in(w23)
        assert len(anims23) >= 1
        assert w23.windowOpacity() == 0.0, "淡入起始应为 0"
        loop23 = QEventLoop()
        _QT23.singleShot(3000, loop23.quit)  # 超时保护
        anims23[0].finished.connect(loop23.quit)
        loop23.exec()
        assert w23.windowOpacity() == 1.0, f"淡入未完成: {w23.windowOpacity()}"
        # 处理 DeferredDelete,确保位移动画 C++ 对象已删除
        # (回归:悬空引用导致 fade_out 抛 RuntimeError,每次必现)
        for _ in range(20):
            app.processEvents()
        # 淡出 + 结束回调
        called23 = []
        fade_out(w23, 80, on_finished=lambda: called23.append(1))
        for _ in range(100):
            app.processEvents()
            if called23:
                break
            _time23.sleep(0.02)
        assert called23, "淡出回调未触发"
        assert w23.windowOpacity() < 0.1, f"淡出未完成: {w23.windowOpacity()}"
        w23.deleteLater()
        print("[23] window animations OK")

        # ── 24. RAG 惰性构建(打开作品不阻塞;搜索即时兑底) ──
        from src.editor.modules.ai_assistant.rag import RAGEngine
        from src.editor.modules.ai_assistant.skills.rag_skills import SearchChaptersSkill
        cm24 = ChapterModule(work)
        # 测试章节内容过短会被 RAG 段落过滤(min_len=20),补一个长章节
        long_md = "第一章 测试\n\n" + ("克诺走在特因城的街道上,口袋里只有两枚铜币。" * 20)
        (work / "chapters" / "0009_长章节测试.md").write_text(long_md, encoding="utf-8")
        cm24.load()
        r24 = RAGEngine()
        assert r24.needs_index() is False, "无章节模块时无需构建"
        r24.chapter_module = cm24
        assert r24.needs_index() is True, "有章节模块但未构建时应标记"
        SearchChaptersSkill.set_engine(r24)
        out24 = SearchChaptersSkill().execute({"query": "克诺"})
        assert out24.get("success") is True and out24.get("count", 0) > 0, out24
        assert r24._ready is True, "首次搜索应即时构建索引"
        print("[24] RAG lazy OK")

        # ── 25. 品牌过渡(BrandSplash + 收缩/张开) ──
        from src.ui.transition import (BrandSplash, collapse_to_center,
                                       expand_from_center)
        from PySide6.QtCore import QRect
        sp25 = BrandSplash()
        assert sp25.icon_label.pixmap() is not None, "标识卡应有图标"
        assert sp25.isVisible() is False
        # 非全屏小卡片(340×400 居中,而非铺满屏幕)
        assert sp25.width() <= 500, f"标识卡应是小卡片而非全屏: {sp25.width()}"
        assert sp25.height() <= 500, f"标识卡应是小卡片而非全屏: {sp25.height()}"
        sp25.play_in(hold_ms=400)
        assert sp25.isVisible(), "标识卡应显示"
        for _ in range(30):
            app.processEvents()
            _time23.sleep(0.01)
        assert sp25.windowOpacity() > 0.1, "标识卡应淡入"
        sp25.close()
        from PySide6.QtGui import QGuiApplication
        if QGuiApplication.platformName() == "offscreen":
            # offscreen 平台 widget.render() 原生崩溃(0xC0000409),
            # 快照缩放动画依赖真实窗口系统,此处跳过(真实环境由人工验证)
            print("[25] brand transition OK (offscreen: snapshot skipped)")
        else:
            # 收缩:窗口快照缩放(真实窗口隐藏,快照接管)
            w25 = QMainWindow()
            w25.setMinimumSize(300, 200)
            w25.resize(600, 400)
            w25.show()
            done25 = []
            collapse_to_center(w25, size=100, duration=80,
                               on_finished=lambda: done25.append(1))
            for _ in range(100):
                app.processEvents()
                if done25:
                    break
                _time23.sleep(0.02)
            assert done25, "收缩回调未触发"
            assert w25.isHidden(), "收缩后真实窗口应隐藏(快照接管)"
            # 张开:窗口从中心张开,showEvent 跳过 fade_in(_skip_fade_in)
            w26 = QMainWindow()
            w26.setMinimumSize(300, 200)
            w26.resize(600, 400)
            done26 = []
            expand_from_center(w26, size=100, duration=80,
                               on_finished=lambda: done26.append(1))
            for _ in range(100):
                app.processEvents()
                if done26:
                    break
                _time23.sleep(0.02)
            assert done26, "张开回调未触发"
            assert w26.isVisible(), "张开后窗口应可见"
            assert w26._skip_fade_in is False, "张开完成后应恢复 fade_in"
            assert w26.minimumSize().width() == 300, "张开后应恢复最小尺寸"
            w25.deleteLater()
            w26.deleteLater()
            print("[25] brand transition OK")

        # ── 26. 标题栏拖动:最大化拖动 → 还原窗口化跟随 ──
        from src.ui.titlebar import TitleBar
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent as _QEv, QPointF as _QPF, Qt as _Qt26
        w26b = QMainWindow()
        w26b.resize(800, 600)
        w26b.show()
        bar26 = TitleBar("t", w26b)
        # 模拟按压(窗口未真正最大化,直接置 _press_maximized 模拟)
        press26 = QMouseEvent(
            _QEv.Type.MouseButtonPress, _QPF(60, 20), _QPF(100, 30),
            _Qt26.MouseButton.LeftButton, _Qt26.MouseButton.LeftButton,
            _Qt26.KeyboardModifier.NoModifier)
        bar26.mousePressEvent(press26)
        bar26._press_maximized = True  # offscreen 下 isMaximized 不可靠,手动置位
        pos_before = w26b.pos()
        move26 = QMouseEvent(
            _QEv.Type.MouseMove, _QPF(80, 40), _QPF(400, 260),
            _Qt26.MouseButton.LeftButton, _Qt26.MouseButton.LeftButton,
            _Qt26.KeyboardModifier.NoModifier)
        bar26.mouseMoveEvent(move26)
        assert bar26._press_maximized is False, "最大化拖动应已还原"
        assert bar26._maximized is False, "还原后状态应清除"
        assert w26b.pos() != pos_before, "拖动后窗口位置应变化"
        bar26.mouseReleaseEvent(move26)
        w26b.deleteLater()
        print("[26] titlebar drag OK")

        # ── 27. 地图首次显示自动适应 ──
        from src.editor.modules.map import MapModule, MapDock
        mm27 = MapModule(work)
        md27 = MapDock(mm27)
        assert getattr(md27, "_auto_fit_done", False) is False, "构造时不应已自动适应"
        # monkeypatch 计数 _fit_view 调用(构造时已调过一次,不在此计数)
        fit_calls = []
        orig_fit = md27._fit_view
        md27._fit_view = lambda: (fit_calls.append(1), orig_fit())[1]
        md27.show()
        for _ in range(10):
            app.processEvents()
        assert md27._auto_fit_done is True, "首次显示应自动适应"
        assert fit_calls, "自动适应应实际执行 _fit_view"
        # 再次显示不重复自动适应(会话内仅一次)
        md27.hide()
        md27.show()
        assert md27._auto_fit_done is True
        md27.close()
        md27.deleteLater()
        print("[27] map auto fit OK")

        # ── 27b. 地图:备注节点便签渲染 + 节点颜色编辑 ──
        from src.editor.modules.map import (MapModule as _MM, MapDock as _MD,
                                            MapNodeItem as _MNI, MapNodeDialog as _MND,
                                            NODE_TYPE_CONFIG as _NTC)
        mm27b = _MM(work)
        note = mm27b.add_node("王都旁白", node_type="note",
                              description="王都西侧是迷雾森林", x=100, y=100)
        assert note.color == "", "未指定颜色时为空(跟随类型默认色)"
        assert "note" in _NTC, "备注节点类型已注册"
        md27b = _MD(mm27b)
        # note 节点渲染为圆角矩形便签 + 备注文本可见
        note_item = next(it for it in md27b.scene.items()
                         if isinstance(it, _MNI) and it.node_data.get("_id") == note.id)
        assert note_item.path().boundingRect().width() >= _MNI.NOTE_W * 0.9, \
            "备注节点应为便签矩形(宽)"
        assert note_item._note_text.isVisible(), "备注内容应显示"
        assert note_item._note_text.toPlainText() == "王都西侧是迷雾森林"
        # 普通城市节点仍为圆形、备注文本隐藏
        city = mm27b.add_node("临海城", node_type="city", x=300, y=300)
        md27b._build_map()
        city_item = next(it for it in md27b.scene.items()
                         if isinstance(it, _MNI) and it.node_data.get("_id") == city.id)
        assert not city_item._note_text.isVisible(), "非备注节点不显示备注文本"
        # 对话框:颜色选择/默认重置/编辑返回 color
        d27 = _MND(note)
        assert d27.get_data()["color"] == "", "未手动选色时 color 为空(跟随类型)"
        d27._picked_color = "#123456"
        assert d27.get_data()["color"] == "#123456", "选色后返回 hex"
        d27._reset_color()
        assert d27.get_data()["color"] == "", "重置后回到类型默认色"
        # 编辑已有自定义颜色节点:对话框预填颜色,保存不丢色
        red = mm27b.add_node("红城", node_type="city", color="#FF0000", x=400, y=400)
        d27b = _MND(red)
        assert d27b.get_data()["color"] == "#FF0000", "编辑时应预填已存颜色"
        # 编辑保存:颜色/类型/描述写回并持久化
        mm27b.update_node(note.id, color="#FF0000", description="新备注")
        assert mm27b.nodes[0].color == "#FF0000"
        md27b.close(); md27b.deleteLater()
        print("[27b] map note + color OK")

        # ── 28. 任务内自动继续:确认一次 → 本任务后续写操作直接执行 → 任务结束复位 ──
        from src.editor.modules.ai_assistant.module import AIAssistantModule as _AIM
        from PySide6.QtCore import QObject as _QObj, Signal as _Sig

        class _FakeBubble(_QObj):
            confirmed = _Sig(list)
            auto_confirmed = _Sig(list)
            cancelled = _Sig()

        class _FakePanel:
            def __init__(self):
                self._bubbles = []
                self._msgs = []
            def add_confirm_bubble(self, descs, tcs):
                b = _FakeBubble()
                self._bubbles.append(b)
                return b
            def add_message(self, role, content, track=True):
                self._msgs.append((role, content))
            def hide_loading(self): pass
            def show_loading(self): pass
            def enable_send(self): pass
            def set_busy(self, busy): self._busy = busy
            def update_memory(self, n): pass
            def _scroll_to_bottom(self): pass
            def begin_streaming_message(self): pass
            def update_streaming(self, *a): pass

        fw28 = QWidget()
        fw28.modules = {}
        fw28.docks = {}
        fw28._load_chapter_content = lambda p: None
        am28 = _AIM(work19, fw28)
        am28.chat_panel = _FakePanel()
        exec_log = []
        am28._execute_writes = lambda tcs, msgs, touched, auto=False: (
            exec_log.append(("exec", auto)) or msgs)
        am28._finish_after_writes = lambda *a, **k: exec_log.append(("finish",))
        tc_w = [{"id": "t1", "type": "function",
                 "function": {"name": "create_character", "arguments": "{}"}}]

        # 未确认:写操作应弹确认气泡而非直接执行
        am28._handle_tool_calls(tc_w, [], "")
        assert not exec_log, "未确认不应直接执行"
        assert am28.chat_panel._bubbles, "应弹确认气泡"

        # 点「允许」→ 本任务内自动继续开启
        am28._on_write_confirmed(tc_w, [], "", auto=False)
        assert am28._task_auto is True, "确认后应开启任务内自动继续"
        assert ("exec", False) in exec_log
        assert am28._auto_confirm is False, "任务内自动不等于会话级全部允许"
        exec_log.clear()

        # 后续写操作:不再弹确认,直接执行(⚡ 自动标志)
        am28.chat_panel._bubbles.clear()
        am28._handle_tool_calls(tc_w, [], "")
        assert not am28.chat_panel._bubbles, "任务内自动不应再弹确认"
        assert ("exec", True) in exec_log, "任务内自动应直接执行(auto=True)"

        # 任务结束(最终回复)→ 复位;新任务 → 复位
        am28._on_ai_response(am28._proposal_worker, "完成了")
        assert am28._task_auto is False, "任务结束应复位"
        am28._task_auto = True
        import src.editor.modules.ai_assistant.worker as _wk28
        _orig_w = _wk28.StreamingProposalWorker
        class _FakeWorker(_QObj):
            text_chunk = _Sig(str)
            reasoning_chunk = _Sig(str)
            proposals_ready = _Sig(list, list, list, str)
            text_response = _Sig(str)
            api_error = _Sig(str)
            finished = _Sig()
            def __init__(self, *a, **k):
                super().__init__()
            def start(self): pass
            def request_stop(self): pass
        _wk28.StreamingProposalWorker = _FakeWorker
        try:
            am28._do_chat("新问题", "current_chapter")
            assert am28._task_auto is False, "新任务应复位"
        finally:
            _wk28.StreamingProposalWorker = _orig_w
        # 取消 → 复位
        am28._task_auto = True
        am28._on_cancel()
        assert am28._task_auto is False, "取消应复位"

        # 真实 _do_chapter_diff:auto 跳过 diff 对话框/手动弹窗/空内容报参数错误
        ch28 = work19 / "chapters"
        ch28.mkdir(exist_ok=True)
        (ch28 / "0001_第一章.md").write_text("旧内容", encoding="utf-8")
        am28d = _AIM(work19, fw28)
        am28d.chat_panel = _FakePanel()
        diff_calls = []
        am28d._show_diff_dialog = lambda old, new, cn: (diff_calls.append(cn), True)[1]
        r1 = am28d._do_chapter_diff({"chapter": "第一章", "content": "新内容"}, auto=True)
        assert r1.get("success") is True and diff_calls == [], f"auto 不应弹 diff: {r1}"
        r2 = am28d._do_chapter_diff({"chapter": "第一章", "content": "新内容2"}, auto=False)
        assert r2.get("success") is True and diff_calls == ["0001_第一章.md"], diff_calls
        r3 = am28d._do_chapter_diff({"chapter": "第一章", "content": ""}, auto=True)
        assert r3.get("success") is False and "空" in r3.get("error", ""), \
            "空内容应报参数错误而非用户拒绝"
        # 全部允许(会话级)后写操作经 _handle_tool_calls 直接执行(auto=True)
        # (update_chapter 不弹 diff 的行为已由上方 994-995 行真实用例覆盖)
        am28d._auto_confirm = True
        diff_calls.clear()
        exec28 = []
        am28d._execute_writes = lambda tcs, msgs, touched, auto=False: (
            exec28.append(auto) or msgs)
        am28d._finish_after_writes = lambda *a, **k: None
        am28d._show_diff_dialog = lambda old, new, cn: (diff_calls.append(cn), True)[1]
        am28d._handle_tool_calls(tc_w, [], "")
        assert exec28 == [True], "全部允许后应直接执行且 auto=True"
        assert diff_calls == [], "全部允许后不应弹 diff"
        am28d._auto_confirm = False
        print("[28] task auto continue OK")

        # ── 29. 推送失败后重新推送:已 commit 未 push(ahead)仍可推送 ──
        import subprocess as _sp
        import tempfile as _tf
        from src.storage.git_manager import GitManager as _GM
        base29 = Path(_tf.mkdtemp(prefix="rw_git_"))
        try:
            repo29 = base29 / "repo"; remote29 = base29 / "remote.git"
            repo29.mkdir(); remote29.mkdir()
            def _g(cwd, *args):
                r = _sp.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
                assert r.returncode == 0, (args, r.stderr)
                return r.stdout
            _g(repo29, "init", "-b", "main")
            _g(repo29, "config", "user.email", "t@t.t")
            _g(repo29, "config", "user.name", "T")
            (repo29 / "a.txt").write_text("v1", encoding="utf-8")
            _g(repo29, "add", "-A"); _g(repo29, "commit", "-m", "c1")
            _g(remote29, "init", "--bare")
            _g(repo29, "remote", "add", "origin", str(remote29))
            _g(repo29, "push", "-u", "origin", "main")
            gm29 = _GM(repo29)
            # 再提交但不推送(模拟推送失败后:本地 ahead=1,工作区干净)
            (repo29 / "a.txt").write_text("v2", encoding="utf-8")
            _g(repo29, "add", "-A"); _g(repo29, "commit", "-m", "c2")
            s29 = gm29.status()
            assert s29["ahead"] == 1 and not s29["dirty"], s29
            # commit_and_push:无新更改(commit 空转)也应完成推送
            ok29, msg29 = gm29.commit_and_push("ReWrite: 重试推送")
            assert ok29, msg29
            s29b = gm29.status()
            assert s29b["ahead"] == 0, f"推送后 ahead 应归零: {s29b}"
            # 无 upstream/无 remote-tracking(旧版本直推 URL 的残留状态):
            # ahead_unknown=True → 调用方放行推送;首次 push 后 tracking 建立
            repo30 = base29 / "repo2"; remote30 = base29 / "remote2.git"
            repo30.mkdir(); remote30.mkdir()
            _g(repo30, "init", "-b", "master")
            _g(repo30, "config", "user.email", "t@t.t")
            _g(repo30, "config", "user.name", "T")
            (repo30 / "b.txt").write_text("x", encoding="utf-8")
            _g(repo30, "add", "-A"); _g(repo30, "commit", "-m", "c1")
            _g(remote30, "init", "--bare")
            _g(repo30, "remote", "add", "origin", str(remote30))
            gm30 = _GM(repo30)
            s30 = gm30.status()
            assert s30["ahead_unknown"] is True, "无 tracking 时应无法确定领先"
            ok30, msg30 = gm30.commit_and_push("首推")
            assert ok30, msg30
            s30b = gm30.status()
            assert s30b["ahead_unknown"] is False and s30b["ahead"] == 0, s30b
        finally:
            import shutil as _sh
            _sh.rmtree(base29, ignore_errors=True)

        # ── 29b. 作品级自定义 AI 提示词:字段往返 + module 读取 + worker 追加 ──
        from src.storage.meta import load_meta as _LM, save_meta as _SM, WorkMeta as _WM
        meta29 = _WM(title="测试作品", work_type="novel",
                     modules=["chapters"], work_id="w29")
        meta29.ai_system_prompt = "允许成人内容,描写细腻"
        _SM(work / "work.json", meta29)
        m29 = _LM(work / "work.json")
        assert m29 is not None and m29.ai_system_prompt == "允许成人内容,描写细腻", \
            "作品提示词应往返保留"
        from src.editor.modules.ai_assistant.worker import StreamingProposalWorker as _SPW
        w29 = _SPW(None, "msg", "ctx", extra_system="允许成人内容,描写细腻")
        assert w29.extra_system == "允许成人内容,描写细腻", "worker 应接收作品提示词"
        am29 = _AIM(work, fw28)
        am29.agent = None  # 仅测 _work_ai_prompt(不依赖 agent)
        assert am29._work_ai_prompt() == "允许成人内容,描写细腻", \
            "module 应能从 work.json 读取作品提示词"
        # 无提示词(空)时返回 ""
        _SM(work / "work.json", _WM(title="测试作品", work_type="novel",
                                    modules=["chapters"], work_id="w29"))
        assert am29._work_ai_prompt() == "", "无作品提示词时应返回空串"
        print("[29b] work ai prompt OK")

        print("[29] git retry push OK")

        # ── 30. 假完成检测:行动承诺类("让我直接修复/我会用")触发而非当最终回复 ──
        from src.editor.modules.ai_assistant.providers import _check_fake_completion as _CFC
        assert _CFC("我理解问题了,让我直接修复——我会用 update_chapter 重建格式"), \
            "行动承诺应命中"
        assert _CFC("好的,我来修改这个章节的内容"), "我来修改应命中"
        assert _CFC("我现在就调用 create_character 创建角色"), "我现在就应命中"
        assert _CFC("好的,我会用 update_chapter 更新"), "我会用应命中"
        # 不命中时返回空字符串(falsy)
        assert not _CFC("这章写得不错,情节很紧凑"), "正常点评不应命中"
        assert not _CFC("建议你尝试调整一下节奏"), "建议类不应命中"
        assert not _CFC("让我先分析一下这段文字"), "分析意图不应误报"
        assert not _CFC("我会用更生动的语言重写这段描述"), "无工具名承诺不应误报"
        assert not _CFC(""), "空内容不应命中"
        # 完成时表述仍命中
        assert _CFC("已经修改好了"), "完成表述应命中"
        print("[30] fake promise detection OK")

        # ── 31. 工具遵从强化:系统提示词/工具描述包含写作映射铁律 ──
        from src.editor.modules.ai_assistant.prompt_templates import DEFAULT_SYSTEM_PROMPT as _DSP
        from src.editor.modules.ai_assistant.skills.chapter_skills import UpdateChapterSkill as _UCS
        assert "update_chapter" in _DSP and "必须调用 update_chapter" in _DSP, \
            "系统提示词应写明写正文必须调 update_chapter"
        assert "禁止把大段正文直接贴在聊天里" in _DSP, "系统提示词应禁止聊天输出正文"
        assert "先 create_chapter 再 update_chapter" in _DSP
        desc31 = _UCS().description
        assert "必须调用本工具把正文写入文件" in desc31, "update_chapter 描述应强调唯一写入途径"
        assert "不要" in desc31 and "聊天回复" in desc31, "update_chapter 描述应禁止聊天输出正文"
        # 工具数量与 registry 一致(防 SKILL_MAP 数字漂移)
        import re as _re31
        from src.editor.modules.ai_assistant.skills.registry import get_all_skills as _GAS
        _m31 = _re31.search(r"共 (\d+) 个", _DSP)
        assert _m31 and int(_m31.group(1)) == len(_GAS()), \
            f"SKILL_MAP 工具数应等于 registry: {_m31.group(1) if _m31 else '?'} vs {len(_GAS())}"
        print("[31] tool compliance prompt OK")

        # ── 32. 章节写入规范化:标题分隔/段落空行(修复标题粘连与换行消失) ──
        from src.editor.modules.ai_assistant.skills.chapter_skills import (
            normalize_chapter_content as _NCC)
        # 标题与正文粘连 → 强制空行
        r32 = _NCC("# 第一章\n正文第一段", "第一章")
        assert r32 == "# 第一章\n\n正文第一段\n", repr(r32)
        # 无标题 → 用回退标题补
        r32b = _NCC("正文第一段\n正文第二段", "第二章")
        assert r32b == "# 第二章\n\n正文第一段\n\n正文第二段\n", repr(r32b)
        # 单换行段落 → 补空行(修复换行消失)
        r32c = _NCC("第一段内容。\n第二段内容。", "")
        assert r32c == "第一段内容。\n\n第二段内容。\n", repr(r32c)
        # 列表不拆散
        r32d = _NCC("第一段。\n- 条目一\n- 条目二\n第二段。", "")
        assert "- 条目一\n- 条目二" in r32d and r32d.count("\n\n") >= 2, repr(r32d)
        # 两位数有序列表不拆散
        r32h = _NCC("10. 第十条\n11. 第十一条", "")
        assert "10. 第十条\n11. 第十一条" in r32h, repr(r32h)
        # 围栏代码块原样保留(不插空行、保留缩进)
        r32i = _NCC("正文。\n```\n    code_line()\n```\n结尾。", "")
        assert "```\n    code_line()\n```" in r32i, repr(r32i)
        assert "\n\n```" not in r32i, repr(r32i)
        # 已有空行结构保持不变(不重复插空行)
        r32e = _NCC("# 标题\n\n段落一\n\n段落二", "")
        assert r32e == "# 标题\n\n段落一\n\n段落二\n", repr(r32e)
        # 换行符统一
        r32f = _NCC("段落一\r\n段落二\r", "")
        assert "\r" not in r32f, repr(r32f)
        # 空内容原样返回
        assert _NCC("", "") == ""
        # update_chapter 集成:无标题 content → 保留原文件标题并分隔
        from src.editor.modules.ai_assistant.skills.chapter_skills import UpdateChapterSkill as _UCS2
        ch32 = work / "chapters"
        ch32.mkdir(exist_ok=True)
        (ch32 / "0001_第三章.md").write_text("# 第三章\n\n旧正文\n", encoding="utf-8")
        r32g = _UCS2().execute({"chapter": "第三章", "content": "新正文A\n新正文B"}, work_name="novel-test1")
        assert r32g.get("success") is True, r32g
        got32 = (ch32 / "0001_第三章.md").read_text(encoding="utf-8")
        assert got32.startswith("# 第三章\n\n新正文A\n\n新正文B\n"), repr(got32)
        # 缩进续行(列表项补充行)不拆散
        r32e = _NCC("第一段。\n- 条目一\n  条目一的补充\n第二段。", "")
        assert "- 条目一\n条目一的补充" in r32e, repr(r32e)
        assert "\n\n第二段。" in r32e, repr(r32e)
        print("[32] chapter normalize OK")

        # ── 33. 大纲创建技能 + 技能名容错匹配(createoutlineentry 不再未知) ──
        from src.editor.modules.ai_assistant.skills.registry import (
            get_skill as _GS, execute_skill as _ES)
        # 容错:AI 去掉下划线也能匹配到正确技能
        s33 = _GS("createoutlineentry")
        assert s33 is not None and s33.name == "create_outline_entry", \
            f"createoutlineentry 应容错匹配: {s33}"
        assert _GS("delete_outline_entry") is not None, "正常名仍精确匹配"
        assert _GS("createoutlineentryx") is None, "无关名字不应误匹配"
        assert _GS("") is None
        # 创建顶层条目 + 子条目
        (work / "outline.json").write_text('{"entries": []}', encoding="utf-8")
        r33a = _ES("create_outline_entry", {"title": "第一卷"}, work_name="novel-test1")
        assert r33a.get("success") is True, r33a
        r33b = _ES("create_outline_entry", {"title": "第一章", "parent": "第一卷",
                                            "content": "开头"}, work_name="novel-test1")
        assert r33b.get("success") is True, r33b
        import json as _json33
        data33 = _json33.loads((work / "outline.json").read_text(encoding="utf-8"))
        assert data33["entries"][0]["title"] == "第一卷"
        assert data33["entries"][0]["children"][0]["title"] == "第一章"
        assert data33["entries"][0]["children"][0]["content"] == "开头"
        # 父条目不存在 → 真实报错
        r33c = _ES("create_outline_entry", {"title": "X", "parent": "不存在"},
                   work_name="novel-test1")
        assert r33c.get("success") is False and "未找到父条目" in r33c.get("error", ""), r33c
        # 空标题拒绝
        r33d = _ES("create_outline_entry", {"title": "  "}, work_name="novel-test1")
        assert r33d.get("success") is False, r33d
        # SKILL_MAP 包含新技能(供 AI 参考)
        assert "create_outline_entry" in _DSP
        print("[33] outline create + fuzzy match OK")

        # ── 34. HTML 标签清理 + 网络错误友好提示 ──
        from src.editor.modules.ai_assistant.skills.chapter_skills import (
            _strip_html_tags as _SHT)
        assert _SHT("<h1>标题</h1><p>段落</p><br>第二段") == "# 标题\n段落\n\n第二段", \
            repr(_SHT("<h1>标题</h1><p>段落</p><br>第二段"))
        assert _SHT("正文 <strong>强调</strong> 结束") == "正文 强调 结束"
        assert _SHT("无标签内容") == "无标签内容"
        # normalize 集成:带标签内容 → 干净 Markdown
        r34 = _NCC("<h1>第五章</h1><p>第一段</p><p>第二段</p>", "")
        assert r34 == "# 第五章\n\n第一段\n\n第二段\n", repr(r34)
        # 10054 友好映射
        from src.editor.modules.ai_assistant.providers import friendly_api_error as _FAE
        assert "10054" in _FAE("[WinError 10054] 远程主机强迫关闭了一个现有的连接。"), _FAE("x")
        assert "服务端中断" in _FAE("远程主机强迫关闭了一个现有的连接。"), _FAE("y")
        assert "超时" in _FAE("timed out"), _FAE("z")
        assert _FAE("其他错误") == "其他错误", _FAE("w")
        # 未输出内容时断连 → 可重试(emitted=False)
        from src.editor.modules.ai_assistant.providers import _StreamReadError as _SRE
        e1 = _SRE(OSError("10054"), emitted=False)
        e2 = _SRE(OSError("10054"), emitted=True)
        assert e1.emitted is False and e2.emitted is True
        print("[34] html strip + friendly error OK")

        # ── 35. 停止按钮 + 停止后部分记忆记录 ──
        # 35a. 面板:停止按钮存在,busy 时可见可点,点击发出 stop_requested
        assert hasattr(panel, "stop_btn"), "停止按钮应存在"
        assert not panel.stop_btn.isVisibleTo(panel), "空闲时停止按钮隐藏"
        panel.set_busy(True)
        assert panel.stop_btn.isVisibleTo(panel) and panel.stop_btn.isEnabled(), \
            "busy 时停止按钮可见可点"
        stop_hits = []
        panel.stop_requested.connect(lambda: stop_hits.append(1))
        panel.stop_btn.click()
        assert stop_hits == [1], "点击停止应发出 stop_requested"
        panel.set_busy(False)
        assert not panel.stop_btn.isVisibleTo(panel), "空闲后停止按钮隐藏"
        # 35b. module:停止时记录已生成的部分文本与已执行工具操作
        am35 = _AIM(work19, fw28)
        am35.chat_panel = _FakePanel()
        am35._streaming_text = "她推开门,月光洒了进来。\n"
        h0 = len(am35.agent.history)
        am35._on_stop_generation()
        assert len(am35.agent.history) == h0 + 1, "停止后应新增一条部分内容记录"
        last35 = am35.agent.history[-1]
        assert last35["role"] == "assistant" and "月光洒了进来" in last35["content"], \
            "已生成的部分文本应记入记忆"
        assert "用户停止了生成" in last35["content"]
        assert am35._task_auto is False and am35._auto_confirm is False, "停止后自动模式退出"
        assert am35._proposal_worker is None and am35._loop_worker is None
        # 35c. 已执行的工具操作(loop messages)也应被记录
        am35b = _AIM(work19, fw28)
        am35b.chat_panel = _FakePanel()
        am35b._streaming_text = ""
        class _FakeLoopWorker:
            messages = [{"role": "tool", "tool_call_id": "t1",
                         "content": "✅ 已更新章节《第一章》"}]
            def request_stop(self): pass
        am35b._loop_worker = _FakeLoopWorker()
        h0b = len(am35b.agent.history)
        am35b._on_stop_generation()
        assert len(am35b.agent.history) == h0b + 1, "已执行工具操作应记入记忆"
        assert "已更新章节" in am35b.agent.history[-1]["content"]
        # 35d. 停止后 _tool_loop 不再发起续写(标志位拦截)
        am35c = _AIM(work19, fw28)
        am35c.chat_panel = _FakePanel()
        am35c._stopped_flag = True
        am35c._tool_loop([], "")  # 标志位分支应直接 return,不创建 worker
        assert am35c._stopped_flag is False, "标志位应复位"
        assert am35c.chat_panel._busy is False, "停止后发言栏解锁"
        # 35e. worker.request_stop 设置事件;_StreamStopped 不会被读取异常处理器吞掉
        from src.editor.modules.ai_assistant.worker import StreamingProposalWorker as _SPW
        from src.editor.modules.ai_assistant.providers import _StreamStopped as _SS35
        w35 = _SPW(am35.agent, "测试")
        assert not w35._stop_event.is_set()
        w35.request_stop()
        assert w35._stop_event.is_set(), "request_stop 应设置停止事件"
        assert not issubclass(_SS35, OSError) and not issubclass(_SS35, TimeoutError), \
            "_StreamStopped 不应被读取异常处理器捕获"
        try:
            raise _SS35()
        except _SS35:
            pass
        # 35f. 停止后:确认写操作被拦截;已执行操作在 _finish_after_writes 记录
        am35f = _AIM(work19, fw28)
        am35f.chat_panel = _FakePanel()
        am35f._stopped_flag = True
        exec35 = []
        am35f._execute_writes = lambda *a, **k: exec35.append(1)
        am35f._on_write_confirmed([], [], "")
        assert exec35 == [], "停止后确认不应执行写操作"
        am35g = _AIM(work19, fw28)
        am35g.chat_panel = _FakePanel()
        am35g._stopped_flag = True
        h35g = len(am35g.agent.history)
        am35g._finish_after_writes([{"role": "tool", "content": "✅ 已更新章节"}], "", set())
        assert len(am35g.agent.history) == h35g + 1, "停止时应记录已执行操作"
        assert "已更新章节" in am35g.agent.history[-1]["content"]
        # 35g. 信号接线冒烟:真实 _do_chat 连接下 emit 不抛 TypeError,响应被处理
        import src.editor.modules.ai_assistant.worker as _wmod35
        _orig_spw = _wmod35.StreamingProposalWorker
        _wmod35.StreamingProposalWorker = _FakeWorker
        am35h = _AIM(work19, fw28)
        am35h.chat_panel = _FakePanel()
        am35h._do_chat("测试信号", "")
        _wmod35.StreamingProposalWorker = _orig_spw
        w35h = am35h._proposal_worker
        assert isinstance(w35h, _FakeWorker)
        w35h.text_chunk.emit("片段")
        assert "片段" in am35h._streaming_text, "chunk 应累积"
        w35h.text_response.emit("完成")
        assert am35h.chat_panel._busy is False, "响应后应解锁"
        print("[35] stop button + partial memory OK")

        print("[18] annotations refactor OK")
        print("[17] launcher theme OK")

        print("ALL SMOKE TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
