"""作品目录工具测试（slugify 等纯函数）。"""

import unittest

from src.storage.work_io import slugify


class SlugifyTest(unittest.TestCase):
    def test_spaces_become_hyphens(self):
        self.assertEqual(slugify("我的 作品"), "我的-作品")

    def test_consecutive_spaces_collapse(self):
        self.assertEqual(slugify("我的   作品"), "我的-作品")

    def test_run_of_hyphens_collapses(self):
        self.assertEqual(slugify("a   -   b"), "a-b")

    def test_windows_illegal_chars_removed(self):
        self.assertEqual(slugify('a\\b/c:d*e?f"g<h>i|j'), "abcdefghij")

    def test_surrounding_whitespace_stripped(self):
        self.assertEqual(slugify("  书名  "), "书名")

    def test_length_capped_at_120(self):
        self.assertEqual(len(slugify("长" * 300)), 120)

    def test_empty_input(self):
        self.assertEqual(slugify(""), "")

    def test_chinese_title_untouched(self):
        self.assertEqual(slugify("新生神明与实习教皇"), "新生神明与实习教皇")


if __name__ == "__main__":
    unittest.main()
