"""字数统计工具测试。"""

import unittest

from src.utils.stats import count_chinese_chars, count_words, format_word_count


class CountWordsTest(unittest.TestCase):
    def test_chinese_chars_counted_individually(self):
        self.assertEqual(count_words("你好世界"), 4)

    def test_english_counted_by_word(self):
        self.assertEqual(count_words("hello world"), 2)

    def test_mixed_chinese_and_english(self):
        self.assertEqual(count_words("你好 hello"), 3)

    def test_html_tags_are_stripped(self):
        self.assertEqual(count_words("<p>你好</p>"), 2)
        self.assertEqual(count_words("<h1>标题</h1><p>正文</p>"), 4)

    def test_empty_and_whitespace(self):
        self.assertEqual(count_words(""), 0)
        self.assertEqual(count_words("   \n\t "), 0)

    def test_hyphenated_and_apostrophe_words_stay_single(self):
        self.assertEqual(count_words("well-known don't"), 2)

    def test_numbers_count_as_words(self):
        self.assertEqual(count_words("第 12 章"), 3)


class CountChineseCharsTest(unittest.TestCase):
    def test_only_chinese_counted(self):
        self.assertEqual(count_chinese_chars("你好 hello 123"), 2)

    def test_html_stripped_first(self):
        self.assertEqual(count_chinese_chars("<b>你好</b>"), 2)


class FormatWordCountTest(unittest.TestCase):
    def test_thousands_separator(self):
        self.assertEqual(format_word_count(12345), "12,345")

    def test_small_number_unchanged(self):
        self.assertEqual(format_word_count(0), "0")
        self.assertEqual(format_word_count(999), "999")


if __name__ == "__main__":
    unittest.main()
