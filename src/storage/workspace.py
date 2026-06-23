"""工作区管理：扫描 works/ 目录获取所有作品信息。"""

from pathlib import Path
from typing import List

from .meta import WorkMeta, load_meta


def _calculate_total_words(work_path: Path) -> int:
    """计算作品目录下所有章节的真实字数。"""
    chapters_dir = work_path / "chapters"
    if not chapters_dir.exists():
        return 0
    total = 0
    for f in chapters_dir.iterdir():
        if f.suffix.lower() == ".html" and not f.name.startswith("."):
            try:
                text = f.read_text(encoding="utf-8")
                from ..utils.stats import count_words
                total += count_words(text)
            except OSError:
                pass
    return total


class Workspace:
    """管理 works/ 目录下所有作品。"""

    def __init__(self, works_dir: Path):
        self.works_dir = works_dir
        self.works_dir.mkdir(parents=True, exist_ok=True)

    def scan(self) -> List[WorkMeta]:
        """扫描 works/ 目录，返回所有作品元数据（按更新时间降序）。"""
        results = []
        if not self.works_dir.exists():
            return results

        for child in sorted(self.works_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            meta = load_meta(child / "work.json")
            if meta is not None:
                # 从章节文件重新计算真实字数
                meta.total_words = _calculate_total_words(child)
                results.append(meta)

        # 按更新时间降序排列
        results.sort(key=lambda m: m.updated, reverse=True)
        return results

    def get_work_path(self, meta: WorkMeta) -> Path:
        """根据 WorkMeta 获取作品目录路径。"""
        from .work_io import slugify
        dir_name = f"{meta.work_type}-{slugify(meta.title)}"
        return self.works_dir / dir_name

    def get_total_works(self) -> int:
        """获取作品数量。"""
        return len(list(self.works_dir.iterdir())) if self.works_dir.exists() else 0
