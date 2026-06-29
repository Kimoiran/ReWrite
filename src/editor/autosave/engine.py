"""保存引擎——实时写入 + 定时快照。不发射任何信号，避免窗口弹跳。"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer

from ..modules.chapters import ChapterModule


class SaveEngine(QObject):
    """保存引擎。

    - 实时写入：每次内容变化直接写文件
    - 定时快照：每 5 分钟保存一份快照到 .autosave/snapshots/
    - 手动保存（Ctrl+S）：创建快照标记
    """

    def __init__(self, chapter_module: ChapterModule, work_path: Path, parent=None):
        super().__init__(parent)
        self.chapter_module = chapter_module
        self.work_path = work_path
        self.autosave_dir = work_path / ".autosave"
        self.snapshot_dir = self.autosave_dir / "snapshots"
        self._max_snapshots = 20
        self._last_snapshot_time = datetime.now()

        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # 定时快照：每 5 分钟一次
        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setInterval(300_000)  # 5 min
        self._snapshot_timer.timeout.connect(self._take_snapshot)
        self._snapshot_timer.start()

    def write_chapter(self, path: str, html: str) -> bool:
        """实时写入章节文件。由编辑器内容变化时直接调用。"""
        return self.chapter_module.write_chapter(Path(path), html)

    def _take_snapshot(self):
        """定时快照：只存 .autosave/snapshots/，不动正式文件。"""
        chapters = self.chapter_module.list_chapters()
        if not chapters:
            return
        for chap in chapters[:3]:  # 最多拍 3 个章节的快照
            try:
                html = self.chapter_module.read_chapter(chap.path)
                if html.count("<p>") < 2:  # 空章节不拍
                    continue
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"{chap.path.stem}.{timestamp}.html"
                (self.snapshot_dir / fname).write_text(html, encoding="utf-8")
                self._cleanup_old(chap.path.stem)
            except OSError:
                pass

    def _cleanup_old(self, prefix: str):
        """清理旧快照。"""
        snaps = sorted(
            [f for f in self.snapshot_dir.iterdir()
             if f.suffix == ".html" and f.stem.startswith(prefix)]
        )
        while len(snaps) > self._max_snapshots:
            try:
                snaps.pop(0).unlink()
            except OSError:
                pass

    def manual_snapshot(self, path: str, html: str):
        """手动保存（Ctrl+S）：立即创建快照，自动清理旧快照。"""
        stem = Path(path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"{stem}.{timestamp}.html"
        try:
            (self.snapshot_dir / fname).write_text(html, encoding="utf-8")
            self._cleanup_old(stem)
        except OSError:
            pass
