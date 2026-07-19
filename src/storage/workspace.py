"""工作区管理：扫描 works/ 目录获取所有作品信息。"""

from pathlib import Path
from typing import List

from .meta import WorkMeta, load_meta


def _calculate_total_words(work_path: Path) -> tuple[int, int]:
    """计算作品目录下章节数和总字数。返回 (章数, 字数)。"""
    chapters_dir = work_path / "chapters"
    if not chapters_dir.exists():
        return 0, 0
    count = 0
    total = 0
    for f in chapters_dir.iterdir():
        if f.suffix.lower() in (".md", ".html") and not f.name.startswith("."):
            count += 1
            try:
                text = f.read_text(encoding="utf-8")
                from ..utils.stats import count_words
                total += count_words(text)
            except OSError:
                pass
    return count, total


class Workspace:
    """管理 works/ 目录下所有作品。"""

    def __init__(self, works_dir: Path):
        self.works_dir = works_dir
        self.works_dir.mkdir(parents=True, exist_ok=True)

    def scan(self) -> List[WorkMeta]:
        """扫描 works/ 目录，返回所有作品元数据（按更新时间降序）。"""
        from .paths import _path_log
        results = []
        if not self.works_dir.exists():
            _path_log(f"scan: works_dir '{self.works_dir}' does NOT exist")
            return results

        _path_log(f"scan: scanning '{self.works_dir}', contents: {[c.name for c in self.works_dir.iterdir()]}")

        for child in sorted(self.works_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            meta_path = child / "work.json"
            meta = load_meta(meta_path)
            if meta is not None:
                # 旧作品无 work_id：自动生成并保存
                if not meta.work_id:
                    import uuid
                    meta.work_id = uuid.uuid4().hex
                    from .meta import save_meta
                    save_meta(meta_path, meta)
                # 从章节文件重新计算真实字数
                chapter_count, word_count = _calculate_total_words(child)
                meta.total_words = word_count
                meta.chapter_count = chapter_count
                results.append(meta)

        # 按更新时间降序排列
        results.sort(key=lambda m: m.updated, reverse=True)
        _path_log(f"scan: found {len(results)} works: {[m.title for m in results]}")
        return results

    def get_work_path(self, meta: WorkMeta) -> Path:
        """根据 WorkMeta 获取作品目录路径。优先 ID 格式，回退旧格式。"""
        # 新格式：work_type-work_id前8位
        if meta.work_id:
            dir_name = f"{meta.work_type}-{meta.work_id[:8]}"
            path = self.works_dir / dir_name
            if path.exists():
                return path
        # 旧格式回退：work_type-slugified_title
        from .work_io import slugify
        dir_name = f"{meta.work_type}-{slugify(meta.title)}"
        return self.works_dir / dir_name

    def get_total_works(self) -> int:
        """获取作品数量。"""
        return len(list(self.works_dir.iterdir())) if self.works_dir.exists() else 0
