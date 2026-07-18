"""编辑器主窗口——QMainWindow 组装所有编辑器组件。"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox, QInputDialog, QLineEdit

from .editor_widget import EditorWidget
from .toolbar import EditorToolbar
from .chapter_list import ChapterListPanel
from .statusbar import EditorStatusBar
from .modules import MODULE_MAP
from .modules.chapters import ChapterModule
from .autosave.engine import SaveEngine
from .search import SearchDialog
from .sync import document_sync
from ..storage.git_manager import GitManager, MigrateGit
from ..ui.titlebar import make_frameless, attach_title_bar


class EditorWindow(QMainWindow):
    """编辑器主窗口。"""

    closed = Signal()

    def __init__(self, work_path: str, parent=None):
        super().__init__(parent)
        make_frameless(self)
        self.work_path = Path(work_path)
        self.modules = {}
        self.docks = {}
        self._right_docks = []  # 用于 tabify
        self._read_module_config()
        self._setup_title()
        self._init_git()
        self._ensure_chapters()
        self._setup_editor()
        self._init_modules()
        self._setup_save_engine()
        self._setup_menu()
        self._connect_signals()
        self._load_initial_chapter()
        self._start_git_polling()
        # 附加标题栏（布局完成后）
        bar = attach_title_bar(self)
        if self._work_meta:
            bar.set_title(self._work_meta.title)

    def _read_module_config(self):
        from ..storage.meta import load_meta
        meta = load_meta(self.work_path / "work.json")
        self._enabled_modules = meta.modules if meta else ["chapters"]
        self._work_meta = meta

    def _setup_title(self):
        self.setWindowTitle("ReWrite")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 900)
        self.setStyleSheet("QMainWindow { background-color: #f0f6fa; }")

    def _init_git(self):
        # 工作空间级 Git 仓库（works/ 目录）
        self.git_manager = GitManager(self.work_path.parent)
        # 迁移：清理旧版作品内嵌的 .git 目录
        MigrateGit(self.work_path.parent).migrate()

    def _ensure_chapters(self):
        chap = ChapterModule(self.work_path)
        chap.load()
        self.modules["chapters"] = chap

    def _init_modules(self):
        first_right = True
        for mod_id in self._enabled_modules:
            if mod_id not in MODULE_MAP:
                continue
            if mod_id == "chapters":
                continue
            mod_class = MODULE_MAP[mod_id]
            instance = mod_class(self.work_path, self)
            instance.load()
            self.modules[mod_id] = instance
            if mod_id == "ai_assistant" and hasattr(instance, "set_editor"):
                instance.set_editor(self.editor)

            dock = instance.create_dock_widget()
            if dock is not None:
                self.docks[mod_id] = dock
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
                self._right_docks.append(dock)

            if hasattr(instance, "get_extra_docks"):
                for extra_dock in instance.get_extra_docks():
                    extra_name = f"{mod_id}_annotations"
                    self.docks[extra_name] = extra_dock
                    self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, extra_dock)
                    self._right_docks.append(extra_dock)

        # Tabify 所有右侧面板，避免重叠
        if len(self._right_docks) > 1:
            for i in range(1, len(self._right_docks)):
                self.tabifyDockWidget(self._right_docks[0], self._right_docks[i])
            self._right_docks[0].raise_()

    def _setup_editor(self):
        self.editor = EditorWidget()
        self.setCentralWidget(self.editor)

        self.toolbar = EditorToolbar(self.editor, self)
        self.addToolBar(self.toolbar)

        chap_mod = self.modules.get("chapters")
        self.chapter_list = ChapterListPanel(chap_mod)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.chapter_list)

        self.status_bar = EditorStatusBar()
        self.setStatusBar(self.status_bar)

        # 设置初始比例：左侧章节列表面板 220px，右侧面板和中央编辑区按 3:7 分剩余空间
        QTimer.singleShot(0, self._resize_docks)

    def _resize_docks(self):
        """给面板设置合理的初始大小比例。"""
        from PySide6.QtWidgets import QSizePolicy
        # 左侧章节列表面板
        self.resizeDocks([self.chapter_list], [240], Qt.Orientation.Horizontal)
        # 右侧所有 dock
        right_docks = [d for d in self.docks.values() if d.isVisible()]
        if right_docks:
            right_width = max(280, self.width() // 4)
            self.resizeDocks(right_docks, [right_width // len(right_docks)] * len(right_docks), Qt.Orientation.Horizontal)

    def _setup_save_engine(self):
        """初始化保存引擎（实时写入 + 定时快照）。"""
        chap_mod = self.modules.get("chapters")
        self.save_engine = SaveEngine(
            chapter_module=chap_mod,
            work_path=self.work_path,
        )

    def _setup_menu(self):
        menubar = self.menuBar()

        # ── 文件 ──
        file_menu = menubar.addMenu("文件")
        save_act = QAction("保存 (Ctrl+S)", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self._on_save)
        file_menu.addAction(save_act)

        export_act = QAction("导出为 .writepack...", self)
        export_act.triggered.connect(self._on_export)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        import_act = QAction("导入文件...", self)
        import_act.triggered.connect(self._on_import_from_editor)
        file_menu.addAction(import_act)

        file_menu.addSeparator()

        settings_act = QAction("设置...", self)
        settings_act.triggered.connect(self._on_open_settings)
        file_menu.addAction(settings_act)

        file_menu.addSeparator()
        close_act = QAction("返回作品选择", self)
        close_act.triggered.connect(self.close)
        file_menu.addAction(close_act)

        # ── Git ──
        git_menu = menubar.addMenu("Git")
        status_act = QAction("查看状态", self)
        status_act.triggered.connect(self._show_git_status)
        git_menu.addAction(status_act)
        git_menu.addSeparator()
        push_act = QAction("提交并推送", self)
        push_act.triggered.connect(self._on_commit_and_push)
        git_menu.addAction(push_act)
        push_now_act = QAction("仅推送", self)
        push_now_act.triggered.connect(self._on_push_only)
        git_menu.addAction(push_now_act)
        git_menu.addSeparator()
        token_act = QAction("配置 GitHub Token...", self)
        token_act.triggered.connect(self._configure_token)
        git_menu.addAction(token_act)

        # ── 编辑 ──
        edit_menu = menubar.addMenu("编辑")
        undo_act = QAction("撤销 (Ctrl+Z)", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo_act)
        redo_act = QAction("重做 (Ctrl+Y)", self)
        redo_act.setShortcut("Ctrl+Y")
        redo_act.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo_act)
        edit_menu.addSeparator()
        search_act = QAction("全局搜索 (Ctrl+Shift+F)", self)
        search_act.setShortcut("Ctrl+Shift+F")
        search_act.triggered.connect(self._on_global_search)
        edit_menu.addAction(search_act)

        # ── 视图 ──
        view_menu = menubar.addMenu("视图")
        view_menu.addAction(self.chapter_list.toggleViewAction())
        for mod_id, dock in self.docks.items():
            view_menu.addAction(dock.toggleViewAction())

        # ── 模块 ──
        self.modules_menu = menubar.addMenu("模块")
        for mod_id, mod in self.modules.items():
            if mod_id in self.docks:
                toggle_act = QAction(f"打开 {mod.__class__.__name__.replace('Module', '')} 面板", self)
                toggle_act.triggered.connect(
                    lambda checked, d=self.docks[mod_id]: d.show()
                )
                self.modules_menu.addAction(toggle_act)

    def _connect_signals(self):
        self.editor.chapter_modified.connect(self._on_editor_modified)
        self.chapter_list.chapter_selected.connect(self._on_chapter_selected)
        self.chapter_list.chapter_created.connect(self._on_chapter_created)
        self.chapter_list.chapter_deleted.connect(self._on_chapter_deleted)
        self.chapter_list.chapter_renamed.connect(self._on_chapter_renamed)
        self.status_bar.commit_push_requested.connect(self._on_commit_and_push)

    def _load_initial_chapter(self):
        chap_mod = self.modules.get("chapters")
        if not chap_mod:
            return
        chapters = chap_mod.list_chapters()
        if chapters:
            first = chapters[0]
            self._load_chapter_content(str(first.path))
            self.chapter_list.select_chapter(str(first.path))
        else:
            self.status_bar.set_chapter_name("无章节")

    def _load_chapter_content(self, path_str: str):
        path = Path(path_str)
        chap_mod = self.modules.get("chapters")
        if not chap_mod:
            return
        md = chap_mod.read_chapter(path)
        self.editor.load_markdown(md)
        self.editor.set_current_chapter(path_str)

        from ..utils.stats import count_words as _cw
        wc = _cw(md)
        chapters = chap_mod.list_chapters()
        for c in chapters:
            if str(c.path) == path_str:
                c.word_count = wc
                self.status_bar.set_chapter_name(c.title)
                self.status_bar.update_word_count(wc)
                break

        # 注册主编辑器同步监听（当前章节路径）
        for key in list(document_sync._listeners.keys()):
            if key != path_str:
                document_sync.unregister(key, self.editor.apply_sync)
        document_sync.register(path_str, self.editor.apply_sync)
        self.status_bar.show_saved()

        # 加载该章节的批注高亮
        ai_mod = self.modules.get("ai_assistant")
        if ai_mod and hasattr(ai_mod, "annotation_mgr"):
            chapter_anns = ai_mod.annotation_mgr.get_chapter_annotations(path_str)
            self.editor.set_annotations(chapter_anns)

    def _on_editor_modified(self):
        """内容变化：实时写入 + 更新字数 + 更新侧栏。不发射信号。"""
        md = self.editor.get_markdown()
        path = self.editor.current_chapter_path()
        if path:
            self.save_engine.write_chapter(path, md)
            from ..utils.stats import count_words as _cw
            plain = self.editor.get_plain_text()
            wc = _cw(plain)
            self.status_bar.update_word_count(wc)
            # 实时更新侧栏章节字数（原地改，不重建列表）
            chap_mod = self.modules.get("chapters")
            if chap_mod and self.editor.current_chapter_path():
                for c in chap_mod.list_chapters():
                    if str(c.path) == self.editor.current_chapter_path():
                        c.word_count = wc
                        self.chapter_list.update_item_display(self.editor.current_chapter_path())
                        break

    def _on_chapter_selected(self, path_str: str):
        self._on_save()
        self._load_chapter_content(path_str)

    def _on_chapter_created(self, path_str: str):
        self._load_chapter_content(path_str)

    def _on_chapter_deleted(self, _path_str: str):
        chap_mod = self.modules.get("chapters")
        if not chap_mod:
            return
        chapters = chap_mod.list_chapters()
        if chapters:
            self._load_chapter_content(str(chapters[0].path))
        else:
            self.editor.clear()
            self.editor.set_current_chapter(None)
            self.status_bar.set_chapter_name("无章节")
            self.status_bar.update_word_count(0)

    def _on_chapter_renamed(self, old_path: str, new_path: str):
        if self.editor.current_chapter_path() == old_path:
            chap_mod = self.modules.get("chapters")
            if not chap_mod:
                return
            chapters = chap_mod.list_chapters()
            for c in chapters:
                if str(c.path) == new_path:
                    self.status_bar.set_chapter_name(c.title)
                    break
            # 同步编辑器路径，否则实时写入会重建旧文件
            self.editor.set_current_chapter(new_path)

    def _on_save(self):
        """手动保存（Ctrl+S）：创建快照 + 广播同步 + 保存模块数据。"""
        md = self.editor.get_markdown()
        path = self.editor.current_chapter_path()
        if path:
            self.save_engine.write_chapter(path, md)
            self.save_engine.manual_snapshot(path, md)
            document_sync.broadcast(path, md, sender=self.editor.apply_sync)
        for mod_id, mod in self.modules.items():
            try:
                mod.save()
            except Exception as e:
                print(f"保存模块 {mod_id} 失败: {e}")
        self.editor.mark_saved()

    def _on_global_search(self):
        searchable = dict(self.modules)
        dialog = SearchDialog(searchable, self)
        dialog.result_selected.connect(self._on_search_result)
        center = self.geometry().center()
        dialog.move(center.x() - dialog.width() // 2, center.y() - dialog.height() // 2)
        dialog.exec()

    def _on_search_result(self, module_id: str, ref_data: str):
        if module_id == "chapters":
            chap_mod = self.modules.get("chapters")
            if chap_mod:
                for c in chap_mod.list_chapters():
                    if str(c.path) == ref_data:
                        self._load_chapter_content(ref_data)
                        self.chapter_list.select_chapter(ref_data)
                        break

    def _on_export(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from ..import_export.packer import pack_work
        meta = self._work_meta
        default_name = f"{meta.title if meta else '作品'}.writepack"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出作品", default_name,
            "ReWrite 包 (*.writepack)"
        )
        if not file_path:
            return

        ok, msg = pack_work(self.work_path, Path(file_path))
        if ok:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.critical(self, "导出失败", msg)

    def _on_import_from_editor(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path

        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入文件", "",
            "支持的文件 (*.writepack *.md *.docx *.txt);;"
            "Markdown (*.md);;"
            "Word 文档 (*.docx);;"
            "纯文本 (*.txt)"
        )
        if not file_path:
            return

        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".md":
            from ..import_export.markdown_import import import_markdown_as_chapter
            chap_mod = self.modules.get("chapters")
            if not chap_mod:
                return
            result = import_markdown_as_chapter(path, chap_mod)
            if result:
                chap_mod.save()
                self.chapter_list._refresh()
                self._load_chapter_content(str(result))
                QMessageBox.information(self, "成功", "Markdown 导入为新的章节")
        elif suffix == ".docx":
            from ..import_export.docx_import import import_docx_as_chapter
            chap_mod = self.modules.get("chapters")
            if not chap_mod:
                return
            try:
                result = import_docx_as_chapter(path, chap_mod)
                if result:
                    chap_mod.save()
                    self.chapter_list._refresh()
                    self._load_chapter_content(str(result))
                    QMessageBox.information(self, "成功", "Word 文档导入为新的章节")
            except ImportError:
                QMessageBox.information(self, "需要安装依赖", "Word 导入需要 python-docx 库")
        elif suffix == ".txt":
            from ..import_export.plaintext_import import import_text_as_chapter
            chap_mod = self.modules.get("chapters")
            if not chap_mod:
                return
            result = import_text_as_chapter(path, chap_mod)
            if result:
                chap_mod.save()
                self.chapter_list._refresh()
                self._load_chapter_content(str(result))
                QMessageBox.information(self, "成功", "纯文本导入为新的章节")
        else:
            QMessageBox.information(self, "提示", "编辑器内导入仅支持 .md/.docx/.txt\n"
                                     ".writepack 请在作品选择页导入")

    def _on_open_settings(self):
        from src.settings.window import SettingsWindow
        dialog = SettingsWindow(self)
        dialog.exec()

    # ── Git ──

    def _start_git_polling(self):
        if not self.git_manager.is_repo():
            return
        # 延迟首次 Git 查询，避免启动卡 UI
        self._git_timer = QTimer(self)
        self._git_timer.timeout.connect(self._refresh_git_status)
        self._git_timer.start(30000)
        QTimer.singleShot(3000, self._refresh_git_status)

    def _refresh_git_status(self):
        try:
            status = self.git_manager.status()
            self.status_bar.update_git_status(status)
        except Exception as e:
            print(f"Git 状态刷新失败: {e}")

    def _show_git_status(self):
        if not self.git_manager.is_repo():
            QMessageBox.information(self, "Git 状态", "工作空间未启用 Git 版本管理")
            return
        status = self.git_manager.status()
        lines = [
            f"提交数: {status['commit_count']}",
            f"未暂存: {status['unstaged']}",
            f"已暂存: {status['staged']}",
            f"领先: {status['ahead']}",
            f"落后: {status['behind']}",
            f"远程: {'已配置' if status['has_remote'] else '未配置'}",
        ]
        QMessageBox.information(self, "Git 状态", "\n".join(lines))

    def _on_commit_and_push(self):
        if not self.git_manager.is_repo():
            QMessageBox.information(self, "提示", "工作空间未启用 Git 版本管理")
            return

        msg = QInputDialog.getText(
            self, "提交说明",
            "提交消息:",
            text="ReWrite: 更新内容",
        )
        if not msg[1] or not msg[0].strip():
            return

        ok, result = self.git_manager.commit_and_push(msg[0].strip())
        if ok:
            QMessageBox.information(self, "成功", result)
        else:
            QMessageBox.warning(self, "失败", result)
        self._refresh_git_status()

    def _on_push_only(self):
        if not self.git_manager.is_repo():
            QMessageBox.information(self, "提示", "此作品未启用 Git 版本管理")
            return
        if not self.git_manager.get_remote_url():
            QMessageBox.information(self, "提示", "未配置远程仓库，请在设置中绑定 GitHub")
            return

        self.git_manager.add_all()
        self.git_manager.commit("ReWrite: 自动提交")
        ok, result = self.git_manager.push()
        if ok:
            QMessageBox.information(self, "成功", "推送成功")
        else:
            QMessageBox.warning(self, "推送失败", result)
        self._refresh_git_status()

    def _configure_token(self):
        from ..storage.git_manager import _load_token, _save_token, open_token_settings
        token, user = _load_token()
        current = f"当前 Token: {token[:8]}... | 用户: {user}" if token else "当前未配置 Token"

        choice = QMessageBox.question(
            self, "GitHub Token",
            f"{current}\n\n"
            "Token 需要 repo 权限，生成地址:\n"
            "https://github.com/settings/tokens\n\n"
            "选择「是」打开 Token 配置文件手动编辑\n"
            "选择「否」在弹窗中输入新的 Token",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Yes:
            open_token_settings()
        elif choice == QMessageBox.StandardButton.No:
            new_token, ok = QInputDialog.getText(
                self, "GitHub Token",
                "输入 Token（可在 https://github.com/settings/tokens 生成）:",
                echo=QLineEdit.EchoMode.Password,
            )
            if ok and new_token.strip():
                import urllib.request, json
                try:
                    req = urllib.request.Request(
                        "https://api.github.com/user",
                        headers={"Authorization": f"Bearer {new_token.strip()}",
                                 "User-Agent": "ReWrite"},
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        user = data.get("login", "")
                    _save_token(new_token.strip(), user)
                    self.git_manager = GitManager(self.work_path.parent)
                    QMessageBox.information(self, "成功", f"Token 保存成功！用户: {user}")
                except Exception as e:
                    QMessageBox.warning(self, "失败", f"Token 验证失败: {e}")

    def closeEvent(self, event):
        for mod_id, mod in self.modules.items():
            try:
                mod.save()
            except Exception:
                pass
        self.chapter_list.deleteLater()
        self.closed.emit()
        super().closeEvent(event)
