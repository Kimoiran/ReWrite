"""作品选择页（启动器）——卡片网格窗口。"""

from pathlib import Path

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import QFont, QIcon, QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QLayout, QSizePolicy, QMessageBox,
    QApplication,
)

from ..storage.meta import WorkMeta, type_to_name
from ..storage.work_io import create_work, delete_work, set_work_cloud_enabled, work_exists
from ..storage.git_manager import GitManager
from ..storage.workspace import Workspace
from ..utils.stats import format_word_count
from ..ui.titlebar import TitleBar, make_frameless
from .work_card import WorkCard
from .create_dialog import CreateWorkDialog


class FlowLayout(QLayout):
    """流式布局：自动换行放置子控件。"""

    def __init__(self, parent=None, margin=0, spacing=12):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list = []

    def __del__(self):
        while self._item_list:
            item = self._item_list.pop()
            item.widget().deleteLater() if item.widget() else None

    def addItem(self, item):
        self._item_list.append(item)
        self.invalidate()

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        w = self.parentWidget().width() if self.parentWidget() else 200
        if w < 50:
            w = 200
        return QSize(w, self._do_layout(QRect(0, 0, w, 0), True))

    def _do_layout(self, rect, test_only):
        left_margin = self.contentsMargins().left()
        top_margin = self.contentsMargins().top()
        x = rect.x() + left_margin
        y = rect.y() + top_margin
        line_height = 0
        spacing = self.spacing()
        available_width = max(rect.width() - left_margin - self.contentsMargins().right(), 200)

        for item in self._item_list:
            widget = item.widget()
            if widget is None:
                continue
            # 注意：不检查 isVisible()，因为初始加载时窗口未显示，
            # 所有 widget 都是不可见的，检查会导致布局计算出错
            widget_size = widget.sizeHint()
            next_x = x + widget_size.width() + spacing
            if next_x - spacing > rect.x() + left_margin + available_width and x > rect.x() + left_margin:
                x = rect.x() + left_margin
                y += line_height + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, widget_size.width(), widget_size.height()))
            x += widget_size.width() + spacing
            line_height = max(line_height, widget_size.height())
        return y + line_height - rect.y()


class LauncherWindow(QWidget):
    """作品选择页主窗口。"""

    open_work_requested = Signal(str)
    settings_requested = Signal()

    PAGE_SIZE = 12  # 每页显示卡片数

    def __init__(self, workspace: Workspace):
        super().__init__()
        self.workspace = workspace
        self._cards = []
        self._current_page = 0
        self._setup_ui()
        self._refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, '_need_icon_fix', False):
            from ..ui.titlebar import _fix_taskbar_icon
            _fix_taskbar_icon(self)
            self._need_icon_fix = False

    def _setup_ui(self):
        self.setWindowTitle("ReWrite")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        self.setStyleSheet("LauncherWindow { background-color: #f0f6fa; }")
        # 无边框标志必须在任何 widget 之前
        make_frameless(self)

        # 设置窗口图标（无边框后会丢失 app 级图标，Windows 需要 .ico）
        for name in ("icon.ico", "icon.png"):
            icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / name
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
                break

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        self.title_bar = TitleBar("ReWrite", self)
        layout.addWidget(self.title_bar)
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 16, 24, 20)
        content_layout.setSpacing(12)

        # ── 工具栏 ──
        btn_style = "QPushButton{font-size:12px;padding:4px 12px;border:1px solid #d0d7de;border-radius:4px;background:#fff;color:#333;}QPushButton:hover{background:#e8eaed;}"
        primary_style = "QPushButton{font-size:12px;font-weight:bold;padding:6px 16px;background:#2196F3;color:#fff;border:none;border-radius:4px;}QPushButton:hover{background:#1976D2;}"

        toolbar = QHBoxLayout()
        import_btn = QPushButton("📥 导入")
        import_btn.setToolTip("从 ZIP 文件或 Git 仓库导入作品")
        import_btn.setStyleSheet(btn_style)
        import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("📤 导出")
        export_btn.setToolTip("导出为 .writepack")
        export_btn.setStyleSheet(btn_style)
        export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(export_btn)

        new_btn = QPushButton("＋ 新作品")
        new_btn.setStyleSheet(primary_style)
        new_btn.clicked.connect(self._on_new_work)
        toolbar.addWidget(new_btn)

        toolbar.addStretch()

        # ── Git 状态 ──
        self.git_status_btn = QPushButton("⬆ 推送")
        self.git_status_btn.setToolTip("提交并推送所有作品到远程仓库")
        self.git_status_btn.setStyleSheet("QPushButton{font-size:12px;padding:4px 12px;border:1px solid #4CAF50;border-radius:4px;background:#E8F5E9;color:#2E7D32;}QPushButton:hover{background:#C8E6C9;}")
        self.git_status_btn.clicked.connect(self._on_git_commit)
        self.git_status_btn.setVisible(False)
        toolbar.addWidget(self.git_status_btn)

        settings_btn = QPushButton("⚙ 设置")
        settings_btn.setToolTip("打开设置")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self.settings_requested.emit)
        toolbar.addWidget(settings_btn)
        content_layout.addLayout(toolbar)

        # ── 卡片网格 ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QLabel.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: transparent;")
        self.flow_layout = FlowLayout(self.scroll_content, margin=4, spacing=24)
        self.scroll_content.setLayout(self.flow_layout)
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area, stretch=1)

        # ── 分页控件 ──
        self.page_widget = QWidget()
        page_layout = QHBoxLayout(self.page_widget)
        page_layout.setContentsMargins(0, 8, 0, 0)
        page_layout.addStretch()
        self.prev_btn = QPushButton("‹ 上一页")
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.prev_btn.clicked.connect(self._prev_page)
        page_layout.addWidget(self.prev_btn)
        self.page_label = QLabel("第 1/1 页")
        self.page_label.setStyleSheet("color: #5a6a7a; font-size: 12px; padding: 4px 12px;")
        page_layout.addWidget(self.page_label)
        self.next_btn = QPushButton("下一页 ›")
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.next_btn.clicked.connect(self._next_page)
        page_layout.addWidget(self.next_btn)
        page_layout.addStretch()
        self.page_widget.setVisible(False)
        content_layout.addWidget(self.page_widget)

        # ── 状态栏 ──
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8a9aaa; font-size: 11px; padding: 4px 0;")
        content_layout.addWidget(self.status_label)

        # ── 空状态提示 ──
        self.empty_label = QLabel("还没有作品\n点击上方「新建作品」按钮创建一个吧")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ef = QFont()
        ef.setPointSize(14)
        self.empty_label.setFont(ef)
        self.empty_label.setStyleSheet("color: #bbbbbb; padding: 80px 0;")
        self.empty_label.setVisible(False)
        content_layout.addWidget(self.empty_label)

        layout.addWidget(content_widget, stretch=1)

        # 连接标题栏信号
        self.title_bar.close_requested.connect(self.close)
        self.title_bar.minimize_requested.connect(self.showMinimized)

        def toggle_max():
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        self.title_bar.maximize_requested.connect(toggle_max)

    def _refresh(self):
        # 清除旧卡片（从 layout 中正确移除并销毁）
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        works = self.workspace.scan()

        # Git 仓库状态
        self._git = GitManager(self.workspace.works_dir)
        self._refresh_git_status()

        total_works = len(works)
        if total_works:
            total_words = sum(w.total_words for w in works)
            self.status_label.setText(f"共 {total_works} 个作品，{format_word_count(total_words)} 字")
            self.empty_label.setVisible(False)
        else:
            self.status_label.setText("")
            self.empty_label.setVisible(True)
            self.page_widget.setVisible(False)

        # ── 分页 ──
        total_pages = max(1, (total_works + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        # 修正当前页码（删除作品后可能越界）
        if self._current_page >= total_pages:
            self._current_page = total_pages - 1
        start = self._current_page * self.PAGE_SIZE
        page_works = works[start:start + self.PAGE_SIZE]

        # 更新分页控件
        if total_works > self.PAGE_SIZE:
            self.page_widget.setVisible(True)
            self.page_label.setText(f"第 {self._current_page + 1}/{total_pages} 页")
            self.prev_btn.setEnabled(self._current_page > 0)
            self.next_btn.setEnabled(self._current_page < total_pages - 1)
        else:
            self.page_widget.setVisible(False)

        for meta in page_works:
            work_path = self.workspace.get_work_path(meta)
            dir_name = work_path.name if work_path.exists() else ""
            if not dir_name:
                continue
            card = WorkCard(meta, dir_name)
            card.clicked.connect(self._on_card_clicked)
            card.delete_requested.connect(self._on_card_delete_requested)
            card.cloud_toggled.connect(self._on_cloud_toggled)
            self.flow_layout.addWidget(card)
            self._cards.append(card)

        # 触发布局更新
        self.scroll_content.updateGeometry()

    def _on_new_work(self):
        dialog = CreateWorkDialog(self.workspace.works_dir, self)
        if dialog.exec() == CreateWorkDialog.DialogCode.Accepted:
            data = dialog.get_result()
            if not data:
                return
            result = create_work(
                works_dir=self.workspace.works_dir,
                title=data["title"],
                work_type=data["work_type"],
                modules=data["modules"],
                cloud_enabled=data["cloud_enabled"],
                date_era=data.get("date_era", ""),
            )
            if result:
                self._current_page = 0  # 新建后跳到首页
                self._refresh()
            else:
                QMessageBox.critical(self, "错误", "创建作品失败，请检查磁盘空间和权限")

    def _on_card_clicked(self, dir_name: str):
        work_path = self.workspace.works_dir / dir_name
        if work_path.exists():
            self.open_work_requested.emit(str(work_path))

    def _on_card_delete_requested(self, dir_name: str):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除作品「{dir_name}」吗？\n删除后不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            work_path = self.workspace.works_dir / dir_name
            if delete_work(work_path):
                self._current_page = 0
                self._refresh()

    def _on_cloud_toggled(self, dir_name: str, enabled: bool):
        """切换作品的云端同步状态。"""
        work_path = self.workspace.works_dir / dir_name
        if set_work_cloud_enabled(work_path, enabled):
            self._refresh()

    def _on_import(self):
        """导入作品 — 选择 ZIP 导入或 Git 仓库克隆。"""
        from .import_dialog import ImportDialog

        dialog = ImportDialog(self.workspace.works_dir, self)
        if dialog.exec() != ImportDialog.DialogCode.Accepted:
            return

        data = dialog.get_result()
        if not data:
            return

        if data["type"] == "zip":
            self._import_zip(Path(data["path"]), data["name"])
        elif data["type"] == "git":
            self._import_git(data["url"], data["name"])

    def _import_zip(self, path: Path, custom_name: str = ""):
        """从 ZIP 或 .writepack 导入。"""
        import shutil, tempfile, zipfile
        from ..import_export.packer import unpack_work

        name = custom_name or path.stem

        if path.suffix.lower() == ".writepack":
            tmp = Path(tempfile.mkdtemp())
            ok, msg, meta = unpack_work(path, tmp)
            if not ok:
                shutil.rmtree(tmp, ignore_errors=True)
                QMessageBox.critical(self, "导入失败", msg)
                return
            title = custom_name or (meta.title if meta else path.stem)
            work_paths = [d for d in tmp.iterdir() if d.is_dir() and (d / "work.json").exists()]
            src = work_paths[0] if work_paths else tmp
        else:
            # 普通 ZIP，解压后看有没有 work.json
            tmp = Path(tempfile.mkdtemp())
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(tmp)
            except zipfile.BadZipFile:
                shutil.rmtree(tmp, ignore_errors=True)
                QMessageBox.critical(self, "导入失败", "不是有效的 ZIP 文件")
                return
            title = custom_name or path.stem
            # 看看有没有 work.json
            if (tmp / "work.json").exists():
                src = tmp
            else:
                # 没有 work.json，创建新作品
                from ..storage.meta import WorkMeta
                meta = WorkMeta.new(title=title, modules=["chapters"])
                from ..storage.meta import save_meta
                (tmp / "chapters").mkdir(exist_ok=True)
                save_meta(tmp / "work.json", meta)
                src = tmp

        if work_exists(self.workspace.works_dir, title):
            shutil.rmtree(tmp, ignore_errors=True)
            QMessageBox.warning(self, "提示", f"已存在同名作品「{title}」")
            return

        from .work_io import slugify
        dir_name = slugify(title)
        target = self.workspace.works_dir / dir_name
        if target.exists():
            shutil.rmtree(tmp, ignore_errors=True)
            QMessageBox.warning(self, "提示", "作品目录已存在")
            return

        shutil.copytree(src, target)
        shutil.rmtree(tmp, ignore_errors=True)
        self._refresh()
        QMessageBox.information(self, "成功", f"作品「{title}」导入成功")

    def _import_git(self, url: str, custom_name: str = ""):
        """从 Git 仓库克隆导入作品。"""
        import subprocess, shutil, tempfile

        repo_name = custom_name or url.rstrip("/").rstrip(".git").split("/")[-1]
        from PySide6.QtWidgets import QInputDialog
        final_name, ok = QInputDialog.getText(self, "导入作品", "作品名称:", text=repo_name)
        if not ok or not final_name.strip():
            return

        if work_exists(self.workspace.works_dir, final_name.strip()):
            QMessageBox.warning(self, "提示", f"已存在同名作品「{final_name.strip()}」")
            return

        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        tmp = Path(tempfile.mkdtemp())
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["git", "clone", url, str(tmp / final_name.strip())],
                capture_output=True, timeout=120, text=True,
                startupinfo=si,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
            if result.returncode != 0:
                shutil.rmtree(tmp, ignore_errors=True)
                QMessageBox.critical(self, "克隆失败",
                    result.stderr[:300] + "\n\n请检查 URL 和网络连接，私有仓库需要 Token。")
                return

            cloned = tmp / final_name.strip()
            # 如果没有 work.json，自动创建
            if not (cloned / "work.json").exists():
                from ..storage.meta import WorkMeta, save_meta
                meta = WorkMeta.new(title=final_name.strip(), modules=["chapters"])
                (cloned / "chapters").mkdir(exist_ok=True)
                save_meta(cloned / "work.json", meta)

            from .work_io import slugify
            target = self.workspace.works_dir / slugify(final_name.strip())
            if target.exists():
                shutil.rmtree(tmp, ignore_errors=True)
                QMessageBox.warning(self, "提示", "作品目录已存在")
                return

            shutil.copytree(cloned, target)
            # 清理旧版内嵌 .git（工作空间级仓库不需要）
            nested_git = target / ".git"
            if nested_git.exists():
                shutil.rmtree(nested_git, ignore_errors=True)
            shutil.rmtree(tmp, ignore_errors=True)
            self._refresh()
            QMessageBox.information(self, "成功", f"作品「{final_name.strip()}」导入成功")

        except subprocess.TimeoutExpired:
            shutil.rmtree(tmp, ignore_errors=True)
            QMessageBox.critical(self, "超时", "克隆超时（120秒），请检查网络或 URL")
        except FileNotFoundError:
            shutil.rmtree(tmp, ignore_errors=True)
            QMessageBox.critical(self, "错误", "未安装 Git，请先安装 git-scm.com")
        except Exception as e:
            shutil.rmtree(tmp, ignore_errors=True)
            QMessageBox.critical(self, "导入失败", str(e))

    # ── 分页导航 ──

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh()

    def _next_page(self):
        total_pages = max(1, (len(self.workspace.scan()) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._refresh()

    def _on_export(self):
        """导出作品为 .writepack。"""
        from PySide6.QtWidgets import QFileDialog
        from ..import_export.packer import pack_work

        works = self.workspace.scan()
        if not works:
            QMessageBox.information(self, "提示", "没有可导出的作品")
            return

        # 选作品
        from PySide6.QtWidgets import QDialog as QD, QVBoxLayout, QListWidget, QDialogButtonBox
        d = QD(self)
        d.setWindowTitle("选择要导出的作品")
        d.setMinimumWidth(300)
        l = QVBoxLayout(d)
        lw = QListWidget(d)
        for w in works:
            lw.addItem(w.title)
        l.addWidget(lw)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, d)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        l.addWidget(bb)
        if d.exec() != QD.Accepted or not lw.currentItem():
            return

        idx = lw.currentRow()
        meta = works[idx]
        work_path = self.workspace.get_work_path(meta)

        default_name = f"{meta.title}.writepack"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出作品", default_name, "ReWrite 包 (*.writepack)")
        if not file_path:
            return

        ok, msg = pack_work(work_path, Path(file_path))
        if ok:
            QMessageBox.information(self, "成功", f"作品「{meta.title}」已导出")
        else:
            QMessageBox.critical(self, "导出失败", msg)

    # ── Git ──

    def _refresh_git_status(self):
        if not hasattr(self, '_git') or not self._git.is_repo():
            self.git_status_btn.setVisible(False)
            return
        self.git_status_btn.setVisible(True)
        try:
            s = self._git.status()
            dirty = "⚠" if s.get("dirty") else ""
            self.git_status_btn.setText(f"⬆ 推送{dirty}")
            tooltip = f"提交数: {s['commit_count']} | 未暂存: {s['unstaged']} | 领先: {s['ahead']}"
            if s.get("has_remote"):
                tooltip += " | 点击提交并推送"
            else:
                tooltip += " | 未配置远程仓库"
            self.git_status_btn.setToolTip(tooltip)
        except Exception:
            self.git_status_btn.setText("⬆ 推送 ?")

    def _on_git_commit(self):
        if not hasattr(self, '_git') or not self._git.is_repo():
            QMessageBox.information(self, "Git", "工作空间未初始化 Git 仓库")
            return
        # 检查是否有未提交的更改
        s = self._git.status()
        if not s.get("dirty") and not s.get("staged") and not s.get("unstaged"):
            QMessageBox.information(self, "Git", "没有需要提交的更改，仓库已是最新")
            return
        from PySide6.QtWidgets import QInputDialog
        msg, ok = QInputDialog.getText(self, "提交说明", "提交消息:",
                                        text="ReWrite: 更新作品库")
        if not ok:
            return
        ok, result = self._git.commit_and_push(msg.strip())
        if ok:
            self._refresh_git_status()
            QMessageBox.information(self, "Git", result)
        else:
            QMessageBox.critical(self, "Git 错误", result)

    def refresh_after_edit(self):
        self._refresh()
