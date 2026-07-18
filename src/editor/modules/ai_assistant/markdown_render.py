"""简单的 Markdown → HTML 渲染（供 QLabel RichText 使用）。"""

import re


_TABLE_STYLE = (
    ' style="'
    'border-collapse:collapse; width:100%; margin:6px 0; '
    'font-size:13px; font-family:Microsoft YaHei,sans-serif;"'
)
_TH_STYLE = (
    ' style="'
    'background:#eef2f7; color:#1a2332; font-weight:700; padding:6px 10px; '
    'border:1px solid #d0d7de; text-align:left; font-size:13px;"'
)
_TD_STYLE = (
    ' style="'
    'padding:5px 10px; border:1px solid #d0d7de; '
    'color:#333; font-size:13px; line-height:1.5;"'
)


def _leading_fullwidth_spaces(line: str) -> str:
    """提取行首全角空格（U+3000），直接返回字面量（不在HTML中转义，避免循环断裂）。"""
    count = 0
    for ch in line:
        if ch == "　":
            count += 1
        else:
            break
    return "　" * count


def markdown_to_html(text: str) -> str:
    """将 Markdown 转为 QLabel 可显示的 HTML 子集。"""
    lines = text.split("\n")
    html_parts = []
    in_list = False
    list_type = None
    in_code_block = False
    table_buffer = []   # 缓冲表格行
    para_buffer = []    # 缓冲段落行（合并连续文本行为一个 <p>）

    def _flush_table():
        if not table_buffer:
            return
        html_parts.append(f"<table{_TABLE_STYLE}>")
        for row_idx, row_text in enumerate(table_buffer):
            if row_idx == 1:
                continue
            cells = [c.strip() for c in row_text.split("|")[1:-1]]
            is_header = row_idx == 0
            tag = "th" if is_header else "td"
            style = _TH_STYLE if is_header else _TD_STYLE
            html_parts.append("<tr>")
            for cell in cells:
                html_parts.append(f"<{tag}{style}>{_inline(cell)}</{tag}>")
            html_parts.append("</tr>")
        html_parts.append("</table>")
        table_buffer.clear()

    def _flush_para():
        """将缓冲的连续文本行合并为一个 <p>，缩进取自第一行。"""
        if not para_buffer:
            return
        indent = _leading_fullwidth_spaces(para_buffer[0])
        body = " ".join(_inline(l.strip()) for l in para_buffer)
        html_parts.append(f"<p>{indent}{body}</p>")
        para_buffer.clear()

    def _is_special(stripped: str) -> bool:
        """检测是否为特殊行（非普通段落文本）。"""
        return (stripped.startswith(("#", "```", "- ", "* ", "> ", "|"))
                or re.match(r"^\d+[.、]\s", stripped)
                or stripped in ("---", "***", "___"))

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            _flush_para()
            if in_code_block:
                html_parts.append("</pre>")
                in_code_block = False
            else:
                in_code_block = True
                html_parts.append("<pre>")
            continue
        if in_code_block:
            html_parts.append(_escape_html(line))
            continue

        # 表格行
        if (stripped.startswith("|") and stripped.endswith("|")
                and stripped.count("|") >= 3):
            _flush_para()
            table_buffer.append(stripped)
            continue
        else:
            _flush_table()

        # 空行 → 段落分隔
        if not stripped:
            _flush_para()
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            continue

        # 标题 / 列表 / 引用 / 分隔线
        if stripped.startswith("### "):
            _flush_para()
            if in_list: html_parts.append(f"</{list_type}>"); in_list = False
            html_parts.append(f"<h3>{_inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            _flush_para()
            if in_list: html_parts.append(f"</{list_type}>"); in_list = False
            html_parts.append(f"<h2>{_inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            _flush_para()
            if in_list: html_parts.append(f"</{list_type}>"); in_list = False
            html_parts.append(f"<h1>{_inline(stripped[2:])}</h1>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            _flush_para()
            if not in_list or list_type != "ul":
                if in_list: html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True; list_type = "ul"
            html_parts.append(f"<li>{_inline(stripped[2:])}</li>")
        elif re.match(r"^\d+[.、]\s", stripped):
            _flush_para()
            if not in_list or list_type != "ol":
                if in_list: html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True; list_type = "ol"
            html_parts.append(f"<li>{_inline(re.sub(r'^\d+[.、]\s', '', stripped))}</li>")
        elif stripped.startswith("> "):
            _flush_para()
            if in_list: html_parts.append(f"</{list_type}>"); in_list = False
            html_parts.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        elif stripped in ("---", "***", "___"):
            _flush_para()
            if in_list: html_parts.append(f"</{list_type}>"); in_list = False
            html_parts.append("<hr>")
        else:
            # 普通段落文本：缓冲，待遇到空行或特殊行时合并输出
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            para_buffer.append(line)

    _flush_para()
    if in_list: html_parts.append(f"</{list_type}>")
    if in_code_block: html_parts.append("</pre>")
    _flush_table()
    return "".join(html_parts)


def _escape_html(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def _inline(text: str) -> str:
    """处理行内格式。先转义 HTML，再替换 Markdown。"""
    text = _escape_html(text)
    # 加粗 **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # 加粗 __text__
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    # 斜体 *text*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # 斜体 _text_
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    # 行内代码 `text`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # 链接 [text](url)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    # 删除线 ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    return text
