"""路径安全测试 —— AI 提供的 ``work`` 参数绝不能逃出 works 目录。

这是 v1.2.0「路径穿越三层防御」中的第一层：``_work_path`` 名称白名单。
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src.editor.modules.ai_assistant.skills._shared import (
    _work_path,
    make_chapter_md,
)

INVALID_NAME = ".__invalid_work_name__"   # 非法名称的回退目标（必定不存在）


class WorkPathSafetyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.works = Path(self._tmp.name)
        self.work = self.works / "novel-测试书"
        self.work.mkdir()
        (self.work / "work.json").write_text(
            json.dumps({"title": "测试书"}, ensure_ascii=False), encoding="utf-8")
        self._env = mock.patch.dict(os.environ, {"REWRITE_WORKS_DIR": str(self.works)})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def assertRejected(self, name):
        """非法名称必须回退到不会写入任何真实目录的哨兵路径。"""
        result = _work_path(name)
        self.assertEqual(result.name, INVALID_NAME, f"未拒绝非法名称: {name!r}")
        self.assertEqual(result.parent.resolve(), self.works.resolve())

    def test_parent_directory_traversal_rejected(self):
        self.assertRejected("../")
        self.assertRejected("..")
        self.assertRejected("../../其他作品")

    def test_absolute_paths_rejected(self):
        self.assertRejected(str(self.works / "novel-测试书"))
        self.assertRejected("/etc/passwd")

    def test_windows_drive_letter_rejected(self):
        self.assertRejected("C:\\Windows")
        self.assertRejected("C:Windows")
        self.assertRejected("d:/作品")

    def test_path_separators_rejected(self):
        self.assertRejected("其他作品/章节")
        self.assertRejected("其他作品\\章节")

    def test_empty_name_rejected(self):
        self.assertRejected("")
        self.assertRejected(None)

    def test_valid_directory_name_resolves_inside_works(self):
        result = _work_path("novel-测试书")
        self.assertEqual(result.resolve(), self.work.resolve())

    def test_title_resolves_to_directory(self):
        self.assertEqual(_work_path("测试书").resolve(), self.work.resolve())

    def test_hash_suffix_lookup(self):
        """书名查找要支持 works 目录的 `<类型>-<hash>` 命名。"""
        self.assertEqual(_work_path("测试书").resolve(), self.work.resolve())

    def test_unknown_name_stays_inside_works(self):
        """未匹配到任何作品时也只能落在 works 目录下，不能向上越界。"""
        result = _work_path("根本不存在的作品")
        self.assertEqual(result.parent.resolve(), self.works.resolve())


class MakeChapterMdTest(unittest.TestCase):
    def test_illegal_filename_chars_removed(self):
        md = make_chapter_md('第1章: 开始/结束?')
        self.assertTrue(md.startswith("# "))
        self.assertNotIn(":", md.splitlines()[0])
        self.assertNotIn("/", md.splitlines()[0])
        self.assertNotIn("?", md.splitlines()[0])

    def test_title_truncated_to_80_chars(self):
        md = make_chapter_md("长" * 200)
        first_line = md.splitlines()[0]
        self.assertEqual(len(first_line), 2 + 80)   # "# " + 80 字

    def test_content_appended_under_title(self):
        md = make_chapter_md("第1章", "正文内容")
        self.assertIn("# 第1章", md)
        self.assertIn("正文内容", md)

    def test_empty_content_gives_title_only(self):
        self.assertEqual(make_chapter_md("第1章"), "# 第1章\n\n")


if __name__ == "__main__":
    unittest.main()
