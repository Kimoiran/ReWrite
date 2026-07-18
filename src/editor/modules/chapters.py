"""章节管理模块——文件的增删改查和持久化。"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from PySide6.QtWidgets import QDockWidget

from .base_module import BaseModule
from ...utils.stats import count_words
from .ai_assistant.skills._shared import make_chapter_md


@dataclass
class ChapterInfo:
    title: str
    path: Path
    order: int
    word_count: int = 0


class ChapterModule(BaseModule):
    """管理 chapters/ 目录下的章节文件。"""

    module_id = "chapters"

    def __init__(self, work_path: Path, parent=None):
        super().__init__(work_path, parent)
        self.chapters_dir = work_path / "chapters"
        self.chapters_dir.mkdir(parents=True, exist_ok=True)
        self._chapters: list[ChapterInfo] = []
        self._dirty = False

    def load(self):
        """扫描 chapters/ 目录加载章节列表。自动迁移旧 .html 文件为 .md。"""
        self._chapters = []
        if not self.chapters_dir.exists():
            self.chapters_dir.mkdir(parents=True)
            return

        for f in sorted(self.chapters_dir.iterdir()):
            if f.name.startswith("."):
                continue
            suffix = f.suffix.lower()
            if suffix == ".html":
                # 自动迁移旧 HTML 文件 → Markdown
                try:
                    md_path = self._migrate_html_to_md(f)
                    if md_path:
                        info = self._parse_filename(md_path)
                        if info:
                            self._chapters.append(info)
                except Exception:
                    pass
            elif suffix == ".md":
                info = self._parse_filename(f)
                if info:
                    self._chapters.append(info)

        self._chapters.sort(key=lambda c: c.order)

    def _migrate_html_to_md(self, html_path: Path) -> Path:
        """将旧 .html 章节迁移为 .md，删除原文件。"""
        from PySide6.QtWidgets import QTextEdit
        import re as _re
        html = html_path.read_text(encoding="utf-8")
        editor = QTextEdit()
        editor.setHtml(html)
        from PySide6.QtGui import QTextDocument
        md = editor.toMarkdown(
            QTextDocument.MarkdownFeature.MarkdownDialectGitHub
        )
        # 修正：QTextEdit 将旧标题（17pt bold span）转成了 **Title**，
        # 需要改回 # Title 格式，否则会被 text-indent 缩进
        md = _re.sub(r'^\*\*(.+?)\*\*$', r'# \1', md.strip(), count=1, flags=_re.MULTILINE)
        if not md.startswith("# "):
            # 兜底：取文件名中的标题部分
            stem = html_path.stem
            title = stem.split("_", 1)[-1] if "_" in stem else stem
            md = f"# {title}\n\n{md}"
        md_path = html_path.with_suffix(".md")
        md_path.write_text(md, encoding="utf-8")
        # 备份原 HTML 文件
        html_path.rename(html_path.with_suffix(".html.bak"))
        return md_path

    def _parse_filename(self, path: Path) -> Optional[ChapterInfo]:
        """从文件名解析章节信息（只读文件名，不读内容）。"""
        name = path.stem
        match = re.match(r"(\d+)_(.+)", name)
        if not match:
            order = 999
            title = name
        else:
            order = int(match.group(1))
            title = match.group(2)
        # 读取内容精确统计字数
        try:
            text = path.read_text(encoding="utf-8")
            wc = count_words(text)
        except OSError:
            wc = 0
        return ChapterInfo(title=title, path=path, order=order, word_count=wc)

    def _build_filename(self, order: int, title: str) -> str:
        """生成文件名。"""
        safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()
        return f"{order:04d}_{safe_title}.md"

    def list_chapters(self) -> list[ChapterInfo]:
        """获取章节列表。"""
        return sorted(self._chapters, key=lambda c: c.order)

    def create_chapter(self, title: str) -> Optional[ChapterInfo]:
        """创建新章节。内容为 Markdown 格式。"""
        if not title.strip():
            return None
        # 确定序号
        exists = self.list_chapters()
        max_order = max((c.order for c in exists), default=0)
        order = max_order + 1

        safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()
        filename = self._build_filename(order, safe_title)
        filepath = self.chapters_dir / filename

        md = make_chapter_md(safe_title)
        try:
            filepath.write_text(md, encoding="utf-8")
        except OSError:
            return None

        info = ChapterInfo(title=safe_title, path=filepath, order=order, word_count=0)
        self._chapters.append(info)
        self._chapters.sort(key=lambda c: c.order)
        self._dirty = True
        return info

    def rename_chapter(self, old_path: Path, new_title: str) -> Optional[Path]:
        """重命名章节文件。"""
        info = self._find_by_path(old_path)
        if not info or not new_title.strip():
            return None
        safe_title = re.sub(r'[\\/:*?"<>|]', "", new_title).strip()
        new_filename = self._build_filename(info.order, safe_title)
        new_path = self.chapters_dir / new_filename

        # 读取旧内容，更新 Markdown 标题行
        try:
            md = old_path.read_text(encoding="utf-8")
        except OSError:
            return None
        # 替换 Markdown # 标题
        md = re.sub(r'^# .*$', f'# {safe_title}', md, count=1, flags=re.MULTILINE)

        try:
            old_path.rename(new_path)
            new_path.write_text(md, encoding="utf-8")
        except OSError:
            return None

        info.title = safe_title
        info.path = new_path
        self._dirty = True
        return new_path

    def delete_chapter(self, path: Path) -> bool:
        """删除章节文件。"""
        info = self._find_by_path(path)
        if not info:
            return False
        try:
            path.unlink()
            self._chapters.remove(info)
            self._dirty = True
            return True
        except OSError:
            return False

    def reorder_chapters(self, new_order: list[str]):
        """重新排序。new_order: [(旧文件名), ...] 按目标顺序。"""
        for idx, old_name in enumerate(new_order):
            old_path = self.chapters_dir / old_name
            info = self._find_by_path(old_path)
            if not info:
                continue
            new_order_num = idx + 1
            if info.order != new_order_num:
                info.order = new_order_num
                new_filename = self._build_filename(new_order_num, info.title)
                new_path = self.chapters_dir / new_filename
                if old_path != new_path:
                    try:
                        old_path.rename(new_path)
                        info.path = new_path
                    except OSError:
                        continue
        self._chapters.sort(key=lambda c: c.order)
        self._dirty = True

    def read_chapter(self, path: Path) -> str:
        """读取章节 HTML 内容。"""
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_chapter(self, path: Path, md: str) -> bool:
        """写入章节。先写临时文件再 rename，保证原子性。"""
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(md, encoding="utf-8")
            tmp.replace(path)
            # 更新字数
            info = self._find_by_path(path)
            if info:
                info.word_count = count_words(md)
            self._dirty = True
            return True
        except OSError as e:
            print(f"写入章节失败: {e}")
            return False

    def save(self):
        """章节模块的文件本身就是保存好的，无需额外操作。"""
        self._dirty = False

    def search(self, query: str) -> list:
        """搜索章节内容。"""
        q = query.lower()
        results = []
        for chap in self._chapters:
            md = self.read_chapter(chap.path)
            if q in md.lower():
                idx = md.lower().find(q)
                snippet = md[max(0, idx - 30):idx + len(q) + 30].strip()
                results.append((chap.title, snippet, str(chap.path)))
        return results

    def _find_by_path(self, path: Path) -> Optional[ChapterInfo]:
        for c in self._chapters:
            if c.path == path:
                return c
        return None

    def create_dock_widget(self) -> QDockWidget:
        """章节管理自己的 Dock（实际由 ChapterListPanel 完成）。"""
        return None
