"""Markdown 导入 — 将 .md 文件转换为 HTML 章节。"""

import re
from pathlib import Path
from typing import Optional


def markdown_to_html(md_text: str) -> str:
    """简单的 Markdown → HTML 转换。"""
    lines = md_text.split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # 空行
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        # 标题
        if stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            html_parts.append(f"<h1>{stripped[2:]}</h1>")

        # 无序列表
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            content = _inline_html(stripped[2:])
            html_parts.append(f"<li>{content}</li>")

        # 有序列表
        elif re.match(r"^\d+\.\s", stripped):
            if not in_list:
                html_parts.append("<ol>")
                in_list = True
            content = _inline_html(re.sub(r"^\d+\.\s", "", stripped))
            html_parts.append(f"<li>{content}</li>")

        # 引用
        elif stripped.startswith("> "):
            content = _inline_html(stripped[2:])
            html_parts.append(f"<blockquote>{content}</blockquote>")

        # 普通段落
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{_inline_html(stripped)}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_html(text: str) -> str:
    """处理行内格式：加粗、斜体、链接。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def import_markdown(file_path: Path) -> tuple[bool, str, str]:
    """导入 Markdown 文件，返回 (成功?, 章节标题, HTML 内容)。"""
    if not file_path.exists():
        return False, "", ""

    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = file_path.read_text(encoding="gbk")
        except UnicodeDecodeError:
            return False, "", "无法解码文件编码"

    # 提取标题（第一个 H1 或文件名）
    title_match = re.search(r"^#\s+(.+)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file_path.stem

    html = markdown_to_html(text)
    return True, title, html


def import_markdown_as_chapter(file_path: Path, chapter_module=None) -> Optional[Path]:
    """导入 Markdown 直接作为新章节。需要 ChapterModule 实例。"""
    if chapter_module is None:
        return None
    try:
        md = file_path.read_text(encoding="utf-8")
    except OSError:
        return None
    # 取第一行 # 标题作为章节名
    title = ""
    for line in md.strip().split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break
    if not title:
        title = file_path.stem
    info = chapter_module.create_chapter(title)
    if info:
        chapter_module.write_chapter(info.path, md)
    return info.path if info else None
