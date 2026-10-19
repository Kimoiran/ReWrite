"""保存引擎——实时写入 + 定时快照。不发射任何信号，避免窗口弹跳。"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from ..modules.chapters import ChapterModule
from ...utils.logging_setup import get_logger

log = get_logger(__name__)

# 快照文件名：<章节名>.<YYYYMMDD_HHMMSS>.(md|html)
_SNAPSHOT_TS_RE = re.compile(r"^(?P<base>.+)\.(?P<ts>\d{8}_\d{6})$")
# 章节文件名的稳定部分：NNNN_标题 → NNNN
_CHAPTER_ORDER_RE = re.compile(r"^(\d+)")

_SNAPSHOT_SUFFIXES = (".md", ".html")


def snapshot_group_key(filename: str) -> str:
    """返回快照归属的章节分组键。

    章节文件名是 ``NNNN_标题.md``；重命名只改标题、**不改编号**，
    所以用编号作键，改名前后拍的快照会落在同一组里、能被正常回收。

    历史 bug：旧实现用 ``stem.startswith(章节完整标题)`` 匹配，
    章节一改名旧标题的快照就永远匹配不上，从此再也不会被删除
    （实测堆积了 800+ 份）。改用编号作键即可根治。

    无编号的章节（文件名不以数字开头）退化为用完整章节名作键。
    """
    stem = Path(filename).stem
    m = _SNAPSHOT_TS_RE.match(stem)
    base = m.group("base") if m else stem
    order = _CHAPTER_ORDER_RE.match(base)
    return order.group(1) if order else base


def _snapshot_sort_key(path: Path) -> tuple:
    """同一章节内快照的排序键：优先用文件名时间戳，异常时退回 mtime。"""
    stem = Path(path).stem
    m = _SNAPSHOT_TS_RE.match(stem)
    if m:
        return (0, m.group("ts"))
    try:
        return (1, f"{path.stat().st_mtime:020.6f}")
    except OSError:
        return (2, path.name)


def prune_snapshots(snapshot_dir: Path, max_keep: int = 5) -> int:
    """按章节分组回收旧快照，每组只保留最新 ``max_keep`` 份。

    遍历整个快照目录（而不是只处理当前章节），因此那些因改名、
    重排、删章而失去归属的「孤儿快照」也会被一并回收。

    :return: 实际删除的文件数。失败不会抛出异常。
    """
    try:
        files = [
            f for f in Path(snapshot_dir).iterdir()
            if f.is_file() and f.suffix in _SNAPSHOT_SUFFIXES
        ]
    except OSError as e:
        log.warning("扫描快照目录失败 %s: %s", snapshot_dir, e)
        return 0

    groups: dict[str, list[Path]] = {}
    for f in files:
        groups.setdefault(snapshot_group_key(f.name), []).append(f)

    removed = 0
    for group in groups.values():
        if len(group) <= max_keep:
            continue
        group.sort(key=_snapshot_sort_key)  # 旧 → 新
        for f in group[: len(group) - max_keep]:
            try:
                f.unlink()
                removed += 1
            except OSError as e:
                log.warning("删除旧快照失败 %s: %s", f, e)
    return removed


class SaveEngine(QObject):
    """保存引擎。

    - 实时写入：每次内容变化直接写文件
    - 定时快照：每 5 分钟给最近修改过的章节存一份快照到 .autosave/snapshots/
    - 手动保存（Ctrl+S）：创建快照标记
    - 留存策略：每个章节（按编号）只保留最近 5 份快照
    """

    def __init__(self, chapter_module: ChapterModule, work_path: Path, parent=None):
        super().__init__(parent)
        self.chapter_module = chapter_module
        self.work_path = work_path
        self.autosave_dir = work_path / ".autosave"
        self.snapshot_dir = self.autosave_dir / "snapshots"
        self._max_snapshots = 5
        self._last_snapshot_time = datetime.now()

        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 定时快照：每 5 分钟一次
        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setInterval(300_000)  # 5 min
        self._snapshot_timer.timeout.connect(self._take_snapshot)
        self._snapshot_timer.start()

    def write_chapter(self, path: str, md: str) -> bool:
        """实时写入章节文件。由编辑器内容变化时直接调用。"""
        return self.chapter_module.write_chapter(Path(path), md)

    def _recent_chapters(self, chapters, limit: int = 3):
        """挑出最近修改过的若干章节。

        旧实现固定取 ``chapters[:3]``，第 4 章以后的章节永远不会产生快照；
        按 mtime 排序后，每个章节最终都能轮到自己被保护。
        """
        def _mtime(chap) -> float:
            try:
                return chap.path.stat().st_mtime
            except OSError:
                return 0.0

        return sorted(chapters, key=_mtime, reverse=True)[:limit]

    def _take_snapshot(self):
        """定时快照：只存 .autosave/snapshots/，不动正式文件。"""
        chapters = self.chapter_module.list_chapters()
        if not chapters:
            return
        for chap in self._recent_chapters(chapters):
            try:
                md = self.chapter_module.read_chapter(chap.path)
                if "\n" not in md:  # 空章节（只有标题行）不拍
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"{chap.path.stem}.{timestamp}.md"
                (self.snapshot_dir / fname).write_text(md, encoding="utf-8")
            except OSError as e:
                log.warning("写入快照失败 %s: %s", chap.path, e)
        prune_snapshots(self.snapshot_dir, self._max_snapshots)

    def manual_snapshot(self, path: str, md: str):
        """手动保存（Ctrl+S）：立即创建快照，并回收旧快照。"""
        stem = Path(path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{stem}.{timestamp}.md"
        try:
            (self.snapshot_dir / fname).write_text(md, encoding="utf-8")
        except OSError as e:
            log.warning("写入手动快照失败 %s: %s", path, e)
            return
        prune_snapshots(self.snapshot_dir, self._max_snapshots)
