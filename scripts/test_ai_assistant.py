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

        # update_chapter 直写路径:内容必须原样写入(不能用 JSON 序列化损坏章节)
        r = execute_skill("update_chapter", {"chapter": "第一章", "content": "# 第一章\n\n新正文内容"},
                          work_name="novel-test1")
        assert r.get("success") is True, r
        content = (work / "chapters" / "0001_第一章.md").read_text(encoding="utf-8")
        assert content == "# 第一章\n\n新正文内容", content

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
        panel.mem_menu_btn.menu().actions()[-1].trigger()  # 清空记忆菜单项
        assert fired == [1], "clear_requested 未触发"
        panel.update_memory(3)
        assert "3" in panel.mem_menu_btn.text()
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

        # ── 12. 大纲 UI:主题化/去前缀/占位项隐藏/状态切换 ──
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
        print("[17] launcher theme OK")

        print("ALL SMOKE TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
