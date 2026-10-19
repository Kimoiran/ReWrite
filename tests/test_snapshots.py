"""快照留存测试 —— 回归「章节改名后旧快照永不回收」的 bug。

背景：旧实现用 ``stem.startswith(章节完整标题)`` 匹配快照，
章节一改名，旧标题的快照就再也匹配不上、永远不会被删除
（实测某个作品堆积了 800+ 份快照）。

现在的实现用 **章节编号**（``NNNN_标题.md`` 里的 NNNN）作分组键，
改名不改变编号，因此新旧快照会归到同一组并被正常回收。
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.editor.autosave.engine import (
    _snapshot_sort_key,
    prune_snapshots,
    snapshot_group_key,
)


def _write(folder: Path, name: str, text: str = "正文") -> Path:
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


class SnapshotGroupKeyTest(unittest.TestCase):
    def test_renamed_chapters_share_the_same_key(self):
        """同一章改过三次标题，三个快照必须归到同一组。"""
        names = [
            "0003_第3章 代行者与腐朽的教廷.20260802_144539.md",
            "0003_第3章 代行者与教廷.20260802_230000.md",
            "0003_第3章 腐朽不堪的教廷.20260809_153008.md",
        ]
        self.assertEqual({snapshot_group_key(n) for n in names}, {"0003"})

    def test_legacy_html_snapshot(self):
        self.assertEqual(
            snapshot_group_key("0002_第2章.20260623_230142.html"), "0002")

    def test_title_containing_dots_still_parses(self):
        self.assertEqual(
            snapshot_group_key("0001_第1章.v2 修订.20260101_000000.md"), "0001")

    def test_chapter_without_number_falls_back_to_title(self):
        self.assertEqual(
            snapshot_group_key("随笔.20260101_000000.md"), "随笔")

    def test_different_chapters_never_share_a_key(self):
        self.assertNotEqual(
            snapshot_group_key("0001_第1章.20260101_000000.md"),
            snapshot_group_key("0002_第2章.20260101_000000.md"))


class PruneSnapshotsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _names(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_keeps_only_newest_max_keep(self):
        for i in range(1, 16):
            _write(self.dir, f"0001_第1章.20260101_{i:06d}.md")

        removed = prune_snapshots(self.dir, max_keep=10)

        self.assertEqual(removed, 5)
        self.assertEqual(len(self._names()), 10)
        # 留下的应该是最新的 10 份（000006 ~ 000015）
        self.assertEqual(
            self._names()[0], "0001_第1章.20260101_000006.md")
        self.assertEqual(
            self._names()[-1], "0001_第1章.20260101_000015.md")

    def test_rename_does_not_leak_snapshots(self):
        """核心回归：新旧标题的快照合并计算，只保留最新的 3 份。"""
        _write(self.dir, "0003_旧标题.20260101_000001.md")
        _write(self.dir, "0003_旧标题.20260101_000002.md")
        _write(self.dir, "0003_旧标题.20260101_000003.md")
        _write(self.dir, "0003_新标题.20260101_000004.md")
        _write(self.dir, "0003_新标题.20260101_000005.md")
        _write(self.dir, "0003_新标题.20260101_000006.md")

        removed = prune_snapshots(self.dir, max_keep=3)

        self.assertEqual(removed, 3)
        self.assertEqual(self._names(), [
            "0003_新标题.20260101_000004.md",
            "0003_新标题.20260101_000005.md",
            "0003_新标题.20260101_000006.md",
        ])

    def test_orphan_group_of_deleted_chapter_is_reclaimed(self):
        """章节已被删除，它的快照组同样会被回收（不会无限堆积）。"""
        for i in range(1, 13):
            _write(self.dir, f"0009_已删章节.20260101_{i:06d}.md")

        removed = prune_snapshots(self.dir, max_keep=10)

        self.assertEqual(removed, 2)
        self.assertEqual(len(self._names()), 10)

    def test_groups_are_pruned_independently(self):
        for i in range(1, 6):
            _write(self.dir, f"0001_第1章.20260101_{i:06d}.md")
        for i in range(1, 13):
            _write(self.dir, f"0002_第2章.20260101_{i:06d}.md")

        removed = prune_snapshots(self.dir, max_keep=10)

        self.assertEqual(removed, 2)
        remaining = self._names()
        self.assertEqual(
            sum(1 for n in remaining if n.startswith("0001_")), 5)
        self.assertEqual(
            sum(1 for n in remaining if n.startswith("0002_")), 10)

    def test_md_and_html_count_toward_the_same_group(self):
        for i in range(1, 7):
            _write(self.dir, f"0002_第2章.20260101_{i:06d}.md")
        for i in range(7, 13):
            _write(self.dir, f"0002_第2章.20260101_{i:06d}.html")

        removed = prune_snapshots(self.dir, max_keep=10)

        self.assertEqual(removed, 2)
        self.assertEqual(len(self._names()), 10)

    def test_non_snapshot_files_are_never_touched(self):
        _write(self.dir, ".crash_marker", "2026-01-01T00:00:00")
        _write(self.dir, "笔记.txt", "手动文件")
        _write(self.dir, "README.md", "说明")
        for i in range(1, 4):
            _write(self.dir, f"0001_第1章.20260101_{i:06d}.md")

        removed = prune_snapshots(self.dir, max_keep=2)

        self.assertEqual(removed, 1)
        self.assertIn("笔记.txt", self._names())
        self.assertIn("README.md", self._names())
        self.assertIn(".crash_marker", self._names())

    def test_under_limit_changes_nothing_and_is_idempotent(self):
        for i in range(1, 4):
            _write(self.dir, f"0001_第1章.20260101_{i:06d}.md")

        self.assertEqual(prune_snapshots(self.dir, max_keep=10), 0)
        self.assertEqual(prune_snapshots(self.dir, max_keep=10), 0)
        self.assertEqual(len(self._names()), 3)

    def test_second_pass_after_pruning_removes_nothing(self):
        for i in range(1, 16):
            _write(self.dir, f"0001_第1章.20260101_{i:06d}.md")

        prune_snapshots(self.dir, max_keep=10)
        self.assertEqual(prune_snapshots(self.dir, max_keep=10), 0)

    def test_missing_directory_is_safe(self):
        self.assertEqual(
            prune_snapshots(self.dir / "并不存在", max_keep=10), 0)

    def test_empty_directory_is_safe(self):
        self.assertEqual(prune_snapshots(self.dir, max_keep=10), 0)


class SnapshotSortKeyTest(unittest.TestCase):
    def test_prefers_timestamp_in_filename(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            newer_ts = _write(d, "0001_第1章.20260102_000000.md")
            older_ts = _write(d, "0001_第1章.20260101_000000.md")
            # 即使旧的 mtime 更新，也应按文件名时间戳排序
            self.assertLess(
                _snapshot_sort_key(older_ts), _snapshot_sort_key(newer_ts))

    def test_falls_back_to_mtime_without_timestamp(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            a = _write(d, "0001_第1章-a.md")
            b = _write(d, "0001_第1章-b.md")
            self.assertEqual(
                [_snapshot_sort_key(a)[0], _snapshot_sort_key(b)[0]], [1, 1])


class DefaultRetentionTest(unittest.TestCase):
    """留存份数是产品决策，测试把它钉住，避免被无意改回去。"""

    def test_signature_default_is_five(self):
        import inspect
        self.assertEqual(
            inspect.signature(prune_snapshots).parameters["max_keep"].default, 5)

    def test_default_applied_when_argument_omitted(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            for i in range(1, 8):
                _write(d, f"0001_第1章.20260101_{i:06d}.md")
            removed = prune_snapshots(d)   # 不传 max_keep
            self.assertEqual(removed, 2)
            self.assertEqual(len(list(d.iterdir())), 5)


if __name__ == "__main__":
    unittest.main()
