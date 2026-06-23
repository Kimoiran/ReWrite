"""崩溃恢复 — 检测异常退出并提示恢复。"""

from datetime import datetime
from pathlib import Path
from typing import Optional


CRASH_MARKER_NAME = ".crash_marker"


def _crash_marker_path(work_path: Path) -> Path:
    return work_path / ".autosave" / CRASH_MARKER_NAME


def mark_normal_exit(work_path: Path):
    """正常退出时删除崩溃标记。"""
    marker = _crash_marker_path(work_path)
    if marker.exists():
        try:
            marker.unlink()
        except OSError:
            pass


def mark_launch(work_path: Path):
    """启动时创建崩溃标记。"""
    marker = _crash_marker_path(work_path)
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError:
        pass


def has_crashed(work_path: Path) -> bool:
    """检查作品是否异常退出。"""
    return _crash_marker_path(work_path).exists()


def get_recoverable_snapshots(work_path: Path) -> list[dict]:
    """获取可恢复的快照列表。"""
    snapshots_dir = work_path / ".autosave" / "snapshots"
    if not snapshots_dir.exists():
        return []

    snapshots = []
    for f in sorted(snapshots_dir.iterdir()):
        if f.suffix == ".html":
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                snapshots.append({
                    "path": str(f),
                    "name": f.stem,
                    "time": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                })
            except OSError:
                continue

    # 按时间降序
    snapshots.reverse()
    return snapshots


def restore_from_snapshot(snapshot_path: str, target_path: str) -> bool:
    """从快照恢复到正式文件。"""
    try:
        data = Path(snapshot_path).read_bytes()
        Path(target_path).write_bytes(data)
        return True
    except OSError:
        return False
