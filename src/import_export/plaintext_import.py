"""纯文本导入 — 将 .txt 文件转为 HTML 章节。"""

from pathlib import Path
from typing import Optional


def import_text(file_path: Path) -> tuple[bool, str, str]:
    """导入纯文本文件，返回 (成功?, 标题, HTML 内容)。"""
    if not file_path.exists():
        return False, "", "文件不存在"

    # 自动检测编码
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "big5", "shift-jis"]
    text = ""
    for enc in encodings:
        try:
            text = file_path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not text:
        return False, "", "无法检测文件编码"

    title = file_path.stem

    # 按段落分割，每段包裹 <p>
    parts = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            parts.append(f"<p>{_escape_html(stripped)}</p>")

    html = "\n".join(parts) if parts else "<p></p>"
    return True, title, html


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def import_text_as_chapter(file_path: Path, chapter_module=None) -> Optional[Path]:
    """导入纯文本作为新章节。"""
    if chapter_module is None:
        return None
    ok, title, html = import_text(file_path)
    if not ok:
        return None
    info = chapter_module.create_chapter(title)
    if info and html:
        chapter_module.write_chapter(info.path, f"<h2>{title}</h2>\n{html}")
    return info.path if info else None
