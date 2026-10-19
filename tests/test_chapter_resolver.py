"""章节名宽松解析测试 —— 回归「AI 读不到章节、只好用搜索把正文找回来」。

根因：旧实现只做 ``display == 章节名`` 的严格相等比较。
用户章节叫「第1章 在孤儿院的日子」，AI 只会说「第1章」或「第一章」，
于是每次「未找到章节」，AI 就退回去用 search_chapters(RAG) 兜底。
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.editor.modules.ai_assistant.skills._shared import (
    chapter_display_name,
    chapter_order,
    cn_numeral_to_int,
    list_chapter_files,
    list_chapter_names,
    normalize_chapter_name,
    resolve_chapter_file,
)


def _setup_chapters(root: Path) -> Path:
    cd = root / "chapters"
    cd.mkdir(parents=True)
    names = [
        "0001_第1章 在孤儿院的日子.md",
        "0002_第2章 未来可期.md",
        "0011_第11章 十之后.md",
        "0012_第十二章 中文序.md",
        "0020_尾声.md",
    ]
    for n in names:
        (cd / n).write_text(f"# {n}\n\n正文\n", encoding="utf-8")
    # 各种残留文件：都不能被当成章节
    (cd / "0002_第2章 未来可期.html.bak").write_text("legacy", encoding="utf-8")
    (cd / "0003_第3章.tmp").write_text("tmp", encoding="utf-8")
    (cd / ".hidden_chapter.md").write_text("hidden", encoding="utf-8")
    return cd


class NumeralTest(unittest.TestCase):
    def test_chinese_numerals(self):
        self.assertEqual(cn_numeral_to_int("一"), 1)
        self.assertEqual(cn_numeral_to_int("十"), 10)
        self.assertEqual(cn_numeral_to_int("十二"), 12)
        self.assertEqual(cn_numeral_to_int("二十三"), 23)
        self.assertEqual(cn_numeral_to_int("一百零五"), 105)

    def test_unparsable_returns_zero(self):
        self.assertEqual(cn_numeral_to_int(""), 0)
        self.assertEqual(cn_numeral_to_int("abc"), 0)

    def test_order_from_various_forms(self):
        self.assertEqual(chapter_order("第12章 标题"), 12)
        self.assertEqual(chapter_order("0012_标题"), 12)
        self.assertEqual(chapter_order("第十二章"), 12)
        self.assertEqual(chapter_order("十二"), 12)
        self.assertIsNone(chapter_order("尾声"))

    def test_normalize_unifies_title_forms(self):
        self.assertEqual(normalize_chapter_name("第一章 在孤儿院的日子"),
                         normalize_chapter_name("0001_第1章在孤儿院的日子"))


class ResolveChapterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cd = _setup_chapters(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _resolved(self, query):
        f = resolve_chapter_file(self.cd, query)
        return f.name if f else None

    def test_full_display_name(self):
        self.assertEqual(self._resolved("第1章 在孤儿院的日子"),
                         "0001_第1章 在孤儿院的日子.md")

    def test_ai_says_only_chapter_number(self):
        """最常见的情况：AI 只说「第1章」。"""
        self.assertEqual(self._resolved("第1章"),
                         "0001_第1章 在孤儿院的日子.md")

    def test_chinese_numeral_form(self):
        """AI 也可能写「第一章」。"""
        self.assertEqual(self._resolved("第一章"),
                         "0001_第1章 在孤儿院的日子.md")

    def test_full_filename_stem(self):
        self.assertEqual(self._resolved("0001_第1章 在孤儿院的日子"),
                         "0001_第1章 在孤儿院的日子.md")

    def test_must_not_confuse_1_with_11(self):
        """「第11章」绝不能命中「第1章」（旧实现的子串匹配就踩过这个坑）。"""
        self.assertEqual(self._resolved("第11章"), "0011_第11章 十之后.md")
        self.assertEqual(self._resolved("第十一章"), "0011_第11章 十之后.md")

    def test_filename_with_chinese_numeral(self):
        self.assertEqual(self._resolved("第十二章 中文序"),
                         "0012_第十二章 中文序.md")
        self.assertEqual(self._resolved("第12章"), "0012_第十二章 中文序.md")

    def test_partial_title(self):
        self.assertEqual(self._resolved("第1章 在孤儿院"),
                         "0001_第1章 在孤儿院的日子.md")

    def test_keyword_only(self):
        """AI 只给了标题关键词。"""
        self.assertEqual(self._resolved("孤儿院"), "0001_第1章 在孤儿院的日子.md")

    def test_extra_whitespace_and_fullwidth(self):
        self.assertEqual(self._resolved("  第1章　在孤儿院的日子  "),
                         "0001_第1章 在孤儿院的日子.md")

    def test_unknown_returns_none(self):
        self.assertIsNone(self._resolved("不存在的章节"))

    def test_empty_query_returns_none(self):
        self.assertIsNone(self._resolved(""))
        self.assertIsNone(self._resolved("   "))

    def test_does_not_match_backup_or_temp_files(self):
        """「第2章」必须命中 .md，而不是 .html.bak。"""
        self.assertEqual(self._resolved("第2章"), "0002_第2章 未来可期.md")


class ChapterFileListingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cd = _setup_chapters(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_real_chapters_listed(self):
        names = [f.name for f in list_chapter_files(self.cd)]
        self.assertEqual(len(names), 5)
        self.assertNotIn("0002_第2章 未来可期.html.bak", names)
        self.assertNotIn("0003_第3章.tmp", names)
        self.assertNotIn(".hidden_chapter.md", names)

    def test_display_names_have_no_order_prefix(self):
        self.assertEqual(chapter_display_name(self.cd / "0001_第1章 在孤儿院的日子.md"),
                         "第1章 在孤儿院的日子")
        self.assertEqual(list_chapter_names(self.cd)[0], "第1章 在孤儿院的日子")

    def test_missing_directory_is_safe(self):
        self.assertEqual(list_chapter_files(self.cd / "不存在"), [])


if __name__ == "__main__":
    unittest.main()
