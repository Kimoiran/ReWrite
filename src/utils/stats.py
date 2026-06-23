"""字数统计工具函数。"""

import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """去除 HTML 标签，返回纯文本。"""
    text = _HTML_TAG_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def count_words(text: str) -> int:
    """统计文本字数（自动去除 HTML 标签）。

    中文字每个字算一字，英文按空格分词计算。
    """
    plain = _strip_html(text)
    chinese_chars = len(re.findall(r'[一-鿿㐀-䶿]', plain))
    english_words = len(re.findall(r'[a-zA-Z0-9]+(?:[-\'][a-zA-Z0-9]+)*', plain))
    return chinese_chars + english_words


def count_chinese_chars(text: str) -> int:
    """统计中文字符数（自动去除 HTML 标签）。"""
    plain = _strip_html(text)
    return len(re.findall(r'[一-鿿㐀-䶿]', plain))


def format_word_count(count: int) -> str:
    """格式化字数，如 12345 -> '12,345'"""
    return f"{count:,}"
