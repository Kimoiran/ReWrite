"""AI 输出 Markdown → HTML 渲染测试（纯字符串，不依赖 Qt）。"""

import unittest

from src.editor.modules.ai_assistant.markdown_render import markdown_to_html


class HeadingTest(unittest.TestCase):
    def test_h1_to_h3(self):
        self.assertIn("<h1>标题</h1>", markdown_to_html("# 标题"))
        self.assertIn("<h2>标题</h2>", markdown_to_html("## 标题"))
        self.assertIn("<h3>标题</h3>", markdown_to_html("### 标题"))


class InlineTest(unittest.TestCase):
    def test_bold_and_italic(self):
        html = markdown_to_html("**粗体** 和 *斜体*")
        self.assertIn("<b>粗体</b>", html)
        self.assertIn("<i>斜体</i>", html)

    def test_inline_code(self):
        self.assertIn("<code>print()</code>", markdown_to_html("`print()`"))

    def test_strikethrough(self):
        self.assertIn("<s>删掉</s>", markdown_to_html("~~删掉~~"))


class TableTest(unittest.TestCase):
    def test_markdown_table_becomes_html_table(self):
        md = "| 角色 | 年龄 |\n| --- | --- |\n| 张三 | 25 |"
        html = markdown_to_html(md)
        self.assertIn("<table", html)
        self.assertIn("<th", html)
        self.assertIn("<td", html)
        self.assertIn("张三", html)

    def test_separator_row_is_dropped(self):
        html = markdown_to_html("| a | b |\n| --- | --- |\n| 1 | 2 |")
        self.assertEqual(html.count("<tr>"), 2)   # 表头 + 1 行数据


class ListAndBlockTest(unittest.TestCase):
    def test_unordered_list(self):
        html = markdown_to_html("- 甲\n- 乙")
        self.assertIn("<ul>", html)
        self.assertEqual(html.count("<li>"), 2)

    def test_ordered_list(self):
        html = markdown_to_html("1. 甲\n2. 乙")
        self.assertIn("<ol>", html)
        self.assertEqual(html.count("<li>"), 2)

    def test_blockquote(self):
        self.assertIn("<blockquote>引用</blockquote>", markdown_to_html("> 引用"))

    def test_horizontal_rule(self):
        self.assertIn("<hr>", markdown_to_html("---"))

    def test_code_block(self):
        html = markdown_to_html("```\ncode\n```")
        self.assertIn("<pre>", html)
        self.assertIn("code", html)

    def test_consecutive_lines_merge_into_one_paragraph(self):
        html = markdown_to_html("第一行\n第二行")
        self.assertEqual(html.count("<p>"), 1)


class SafetyTest(unittest.TestCase):
    def test_raw_html_is_escaped_not_rendered(self):
        """AI 输出里的 HTML 必须转义，防注入。"""
        html = markdown_to_html("<script>alert(1)</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_code_block_content_is_escaped(self):
        html = markdown_to_html("```\n<b>x</b>\n```")
        self.assertIn("&lt;b&gt;", html)

    def test_ampersand_escaped(self):
        self.assertIn("&amp;", markdown_to_html("甲 & 乙"))


class EdgeCaseTest(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(markdown_to_html(""), "")

    def test_plain_text_wrapped_in_paragraph(self):
        self.assertEqual(markdown_to_html("一句话"), "<p>一句话</p>")


if __name__ == "__main__":
    unittest.main()
