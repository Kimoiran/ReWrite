"""Markdown ↔ QTextDocument 双向转换(自写实现)。

背景:PySide6 全系(6.9/6.10/6.11)的 QTextDocument.toMarkdown/QTextDocumentWriter
在 markdown 格式下会触发 Qt 原生崩溃(0xC0000409),Qt 官方序列化不可用。

本模块自写导出器,遍历 QTextDocument 块模型,无损输出 Markdown:
- 块级:标题(headingLevel)、列表(textList)、表格(QTextTable)、段落
- 行内:加粗/斜体(block.textFormats 字符格式)
- 与项目自研渲染器 markdown_render.markdown_to_html 配合,实现
  「加载:MD → HTML 渲染(所见即所得);保存:文档 → MD(无损)」

设计为纯函数 + QTextDocument 输入,零 UI 依赖,便于单测。
"""

from typing import List, Optional

from PySide6.QtGui import QTextBlock, QTextDocument, QTextTable, QFont

from .ai_assistant.markdown_render import markdown_to_html as _md_to_html


def md_to_html(md: str) -> str:
    """Markdown → 富文本 HTML(带 qrichtext 头,与正文编辑器 load_markdown 同款)。

    返回可直接 setHtml 的完整 HTML 文档。
    """
    stripped = md.strip()
    if stripped.startswith("<!DOCTYPE") or stripped.startswith("<html"):
        # 遗留 HTML 直接使用
        return md
    body = _md_to_html(md)
    return "\n".join([
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
        '"http://www.w3.org/TR/REC-html40/strict.dtd">',
        '<html><head><meta name="qrichtext" content="1" />'
        '<meta charset="utf-8" />'
        '<style type="text/css">',
        "p, li { white-space: pre-wrap; }",
        "h1 { font-size: 17pt; font-weight: 700; margin-top: 0; margin-bottom: 8px; }",
        "h2 { font-size: 15pt; font-weight: 700; }",
        "h3 { font-size: 14pt; font-weight: 700; }",
        'body { font-family: "Microsoft YaHei UI", "Microsoft YaHei", "sans-serif";'
        " font-weight: 400; }",
        "</style></head>",
        f"<body>{body}</body></html>",
    ])


# ── 导出:QTextDocument → Markdown ──


def _collect_tables(frame) -> List[QTextTable]:
    """递归收集所有 QTextTable(含嵌套 frame)。"""
    from PySide6.QtGui import QTextTable as _T
    tables = []
    for child in frame.childFrames():
        if isinstance(child, _T):
            tables.append(child)
        tables.extend(_collect_tables(child))
    return tables


def _inline_md(block: QTextBlock) -> str:
    """提取单个 block 的行内 Markdown(加粗/斜体)。"""
    text = block.text()
    if not text:
        return ""
    fragments = []
    for fr in block.textFormats():
        fmt = fr.format
        try:
            bold = fmt.fontWeight() >= QFont.Weight.Bold
            italic = fmt.fontItalic()
        except RuntimeError:
            bold = italic = False
        fragments.append((fr.start, fr.length, bold, italic))
    if not fragments:
        return text
    fragments.sort(key=lambda x: x[0])

    result = []
    i = 0
    n = len(text)
    while i < n:
        bold = italic = False
        boundary = n
        for s, l, b, it in fragments:
            if s <= i < s + l:
                bold, italic = b, it
                boundary = min(boundary, s + l)
            elif s > i:
                boundary = min(boundary, s)
        chunk = text[i:boundary]
        if bold and italic and chunk.strip():
            result.append(f"***{chunk}***")
        elif bold and chunk.strip():
            result.append(f"**{chunk}**")
        elif italic and chunk.strip():
            result.append(f"*{chunk}*")
        else:
            result.append(chunk)
        i = boundary
    return "".join(result)


def _table_to_md(table: QTextTable) -> str:
    """QTextTable → Markdown 表格。"""
    rows, cols = table.rows(), table.columns()
    if rows == 0 or cols == 0:
        return ""
    md_rows = []
    for r in range(rows):
        cells = []
        for c in range(cols):
            cell = table.cellAt(r, c)
            lines = []
            # 用 findBlock 遍历单元格范围内所有块(避开 PySide6 frame iterator API 缺失)
            doc = table.document()
            pos = cell.firstPosition()
            end = cell.lastPosition()
            while pos <= end:
                cb = doc.findBlock(pos)
                if not cb.isValid():
                    break
                t = _inline_md(cb).strip()
                if t:
                    lines.append(t)
                nxt = cb.position() + len(cb.text()) + 1  # +1 跳过块分隔符
                if nxt <= pos:
                    break
                pos = nxt
            cells.append(" ".join(lines))
        md_rows.append("| " + " | ".join(cells) + " |")
    sep = "|" + "|".join(["---"] * cols) + "|"
    md_rows.insert(1, sep)
    return "\n".join(md_rows)


def document_to_markdown(doc: QTextDocument) -> str:
    """QTextDocument → Markdown(无损导出:标题/列表/表格/加粗/斜体)。"""
    tables = _collect_tables(doc.rootFrame())
    table_ids = set()
    out: List[str] = []
    prev_text = False  # 上一块是否为文本内容(用于空行分隔)
    prev_was_list = False  # 上一块是否为列表项(列表结束后需空行分隔)

    block = doc.begin()
    while block.isValid():
        text = block.text()
        pos = block.position()

        # 表格:整表输出一次,跳过表内其余 block
        table = None
        for t in tables:
            if t.firstPosition() <= pos <= t.lastPosition():
                table = t
                break
        if table is not None:
            if id(table) not in table_ids:
                table_ids.add(id(table))
                if out and out[-1] != "":
                    out.append("")
                md_table = _table_to_md(table)
                if md_table:
                    out.append(md_table)
                    out.append("")
                prev_text = False
            prev_was_list = False
            block = block.next()
            continue

        # 列表
        lst = block.textList()
        if lst is not None:
            indent = "  " * (lst.format().indent() if hasattr(lst.format(), "indent") else 0)
            md = _inline_md(block)
            if prev_text:
                out.append("")
            out.append(f"{indent}- {md}")
            prev_text = False  # 连续列表项不插空行
            prev_was_list = True
            block = block.next()
            continue

        # 非列表块:列表结束后补空行(GFM 严格解析时列表不会吞并后续内容)
        if prev_was_list and (text.strip() or True):
            out.append("")
            prev_was_list = False

        # 标题
        fmt = block.blockFormat()
        hl = int(fmt.headingLevel()) if hasattr(fmt, "headingLevel") else 0
        hl = hl or 0
        if hl > 0:
            if prev_text:
                out.append("")
            # 标题本身由块级样式加粗,直接取文本(避免整块被误包成 **x**)
            out.append(f"{'#' * hl} {text.strip()}")
            out.append("")
            prev_text = False
        elif text.strip():
            if prev_text:
                out.append("")
            out.append(_inline_md(block))
            prev_text = True
        else:
            # 空块:作为段落分隔
            if prev_text:
                out.append("")
                prev_text = False
        block = block.next()

    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def load_markdown_into(editor, md: str):
    """加载 Markdown 到 QTextEdit(渲染为富文本,所见即所得)。"""
    editor.blockSignals(True)
    editor.setHtml(md_to_html(md))
    editor.blockSignals(False)


def save_markdown_from(editor) -> str:
    """从 QTextEdit 导出 Markdown(无损)。"""
    return document_to_markdown(editor.document())
