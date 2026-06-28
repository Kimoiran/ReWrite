"""章节管理模块——文件的增删改查和持久化。"""

import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from PySide6.QtWidgets import QDockWidget

from .base_module import BaseModule
from ...utils.stats import count_words
from .ai_assistant.skills._shared import make_chapter_html


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
        """扫描 chapters/ 目录加载章节列表（快速扫描，不读文件内容）。"""
        self._chapters = []
        if not self.chapters_dir.exists():
            self.chapters_dir.mkdir(parents=True)
            return

        for f in sorted(self.chapters_dir.iterdir()):
            if f.suffix.lower() != ".html" or f.name.startswith("."):
                continue
            info = self._parse_filename(f)
            if info:
                self._chapters.append(info)

        self._chapters.sort(key=lambda c: c.order)

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
        return f"{order:04d}_{safe_title}.html"

    def list_chapters(self) -> list[ChapterInfo]:
        """获取章节列表。"""
        return sorted(self._chapters, key=lambda c: c.order)

    def create_chapter(self, title: str) -> Optional[ChapterInfo]:
        """创建新章节。内容为空 HTML。"""
        if not title.strip():
            return None
        # 确定序号
        exists = self.list_chapters()
        max_order = max((c.order for c in exists), default=0)
        order = max_order + 1

        safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()
        filename = self._build_filename(order, safe_title)
        filepath = self.chapters_dir / filename

        # 标准化的 QTextEdit HTML 模板
        html = make_chapter_html(safe_title)
        try:
            filepath.write_text(html, encoding="utf-8")
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

        # 读取旧内容，更新标题标签（支持 <h2> 和 QTextEdit 的 <p><span> 两种格式）
        try:
            html = old_path.read_text(encoding="utf-8")
        except OSError:
            return None
        # 优先匹配 QTextEdit 的 <p><span style="...font-weight:700;">...</span></p>
        new_html = re.sub(
            r'(<p[^>]*><span[^>]*font-weight:\s*700[^>]*>).*?(</span></p>)',
            rf'\1{safe_title}\2',
            html, count=1, flags=re.IGNORECASE,
        )
        if new_html == html:
            # 回退：匹配 <h2>...</h2>
            new_html = re.sub(r'<h2>.*?</h2>', f'<h2>{safe_title}</h2>', html, count=1)
        html = new_html

        try:
            old_path.rename(new_path)
            new_path.write_text(html, encoding="utf-8")
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

    def write_chapter(self, path: Path, html: str) -> bool:
        """写入章节。先写临时文件再 rename，保证原子性。"""
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(html, encoding="utf-8")
            tmp.replace(path)
            # 更新字数
            info = self._find_by_path(path)
            if info:
                info.word_count = count_words(html)
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
            html = self.read_chapter(chap.path)
            if q in html.lower():
                # 找匹配位置附近的片段
                import re as re_mod
                # 取前 50 个字符做摘要
                idx = html.lower().find(q)
                snippet = html[max(0, idx - 30):idx + len(q) + 30]
                # 去除 HTML 标签
                snippet = re_mod.sub(r"<[^>]+>", "", snippet).strip()
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
