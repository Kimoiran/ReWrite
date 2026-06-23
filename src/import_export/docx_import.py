"""DOCX (Word) 导入 — 提取文字和基本格式转为 HTML。"""

from pathlib import Path
from typing import Optional


def import_docx(file_path: Path) -> tuple[bool, str, str]:
    """导入 Word 文档，返回 (成功?, 标题, HTML 内容)。"""
    try:
        from docx import Document
    except ImportError:
        return False, "", "需要安装 python-docx: pip install python-docx"

    if not file_path.exists():
        return False, "", "文件不存在"

    try:
        doc = Document(str(file_path))
    except Exception as e:
        return False, "", f"无法读取 Word 文档: {e}"

    # 提取标题（第一个段落如果是一级标题，或文件名）
    title = file_path.stem
    html_parts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name.lower() if para.style else ""

        # 标题样式
        if "heading 1" in style_name or "heading1" in style_name:
            if title == file_path.stem:  # 第一个 H1 作为章节标题
                title = text
            html_parts.append(f"<h1>{text}</h1>")
        elif "heading 2" in style_name or "heading2" in style_name:
            html_parts.append(f"<h2>{text}</h2>")
        elif "heading 3" in style_name or "heading3" in style_name:
            html_parts.append(f"<h3>{text}</h3>")
        else:
            # 段落：保留加粗/斜体
            inner = ""
            for run in para.runs:
                t = run.text
                if run.bold:
                    t = f"<strong>{t}</strong>"
                if run.italic:
                    t = f"<em>{t}</em>"
                inner += t
            html_parts.append(f"<p>{inner}</p>")

    html = "\n".join(html_parts)
    return True, title, html


def import_docx_as_chapter(file_path: Path, chapter_module=None) -> Optional[Path]:
    """导入 Word 文档作为新章节。"""
    if chapter_module is None:
        return None
    ok, title, html = import_docx(file_path)
    if not ok:
        return None
    info = chapter_module.create_chapter(title)
    if info and html:
        chapter_module.write_chapter(info.path, f"<h2>{title}</h2>\n{html}")
    return info.path if info else None
