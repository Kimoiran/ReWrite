"""技能间共享工具函数。"""

import json
import re as _re
from pathlib import Path


def list_works() -> list:
    """列出所有作品（供 providers.py 使用）。"""
    wd = _works_dir()
    works = []
    for child in sorted(wd.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = child / "work.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                works.append({
                    "name": child.name,
                    "title": m.get("title", child.name),
                    "type": m.get("work_type", ""),
                    "modules": m.get("modules", []),
                    "updated": m.get("updated", ""),
                })
            except Exception:
                pass
    return works


def _works_dir() -> Path:
    import os
    env = os.environ.get("REWRITE_WORKS_DIR", "")
    if env:
        return Path(env)
    from .....storage.paths import get_works_dir
    return get_works_dir()


def _work_path(name: str) -> Path:
    wd = _works_dir()
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == name or child.name.endswith(f"-{name}"):
            return child
        meta = child / "work.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if data.get("title") == name:
                    return child
            except Exception:
                pass
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if name.lower() in child.name.lower():
            return child
    return wd / name


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_chapter_md(title: str, content: str = "") -> str:
    """生成标准化的章节 Markdown 文本。"""
    safe_title = _re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
    if content:
        return f"# {safe_title}\n\n{content}"
    return f"# {safe_title}\n\n"


def make_chapter_html(title: str, content: str = "") -> str:
    """生成标准化的章节 HTML（QTextEdit 兼容格式，统一 14pt 正文/17pt 标题）。

    与 QTextEdit 默认字号一致，避免 px/pt 混用导致的字体大小不一致。
    """
    safe_title = _re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
    lines = [
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
        '"http://www.w3.org/TR/REC-html40/strict.dtd">',
        '<html><head><meta name="qrichtext" content="1" />'
        '<meta charset="utf-8" />'
        '<style type="text/css">',
        "p, li { white-space: pre-wrap; }",
        "hr { height: 1px; border-width: 0; }",
        'li.unchecked::marker { content: "\\2610"; }',
        'li.checked::marker { content: "\\2612"; }',
        "</style></head>",
        '<body style="'
        "font-family:'Microsoft YaHei UI','Microsoft YaHei','Segoe UI','sans-serif';"
        " font-size:14pt; font-weight:400; font-style:normal;\">",
        # 标题行：17pt 加粗
        '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; '
        'margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
        '<span style=" font-size:17pt; font-weight:700;">'
        f'{safe_title}</span></p>',
    ]
    if content:
        lines.append(content)
    else:
        # 默认正文空段：显式 14pt，新文字从正确大小开始
        lines.append(
            '<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; '
            'margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
            '<span style=" font-size:14pt;"> </span></p>'
        )
    lines.append("</body></html>")
    return "\n".join(lines)


def _date_sort_key(date_str: str, era: str = ""):
    """智能日期排序键，支持「{era}XXX年」「{era}前XXX年」「{era}元年」等格式。"""
    if not date_str:
        return (1, "", 0, 0)
    if era:
        if f"{era}元年" in date_str:
            return (0, "", 1, 1)
        m = _re.match(_re.escape(era) + r'前?\s*(\d+)', date_str)
        if m:
            year = int(m.group(1))
            is_before = "前" in date_str
            return (0, "", 0 if is_before else 1, year)
    if date_str.isdigit():
        return (0, "", 0, int(date_str))
    nums = _re.findall(r'\d+', date_str)
    if nums:
        return (0, "", 0, int(nums[0]))
    return (1, date_str, 0, 0)


_SENTENCE_BREAK = _re.compile(r'(。|！|？|；|……|——)')
"""在中文句末标点后自动断行。"""


def _fmt_text(text: str, max_len: int = 100) -> str:
    """长文本自动加换行：在句末标点后插入 \\n，使每行不超过 max_len 字。

    适用于人物卡/大纲/时间线中的长文本字段。
    已有换行或长度 ≤ max_len 的文本原样返回。
    """
    if not text or len(text) <= max_len or "\n" in text:
        return text
    # 在标点后断句，用零宽断言保留标点
    parts = _SENTENCE_BREAK.split(text)
    # parts = [text, punct, text, punct, ...]
    lines = []
    buf = ""
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        punct = parts[i + 1] if i + 1 < len(parts) else ""
        if not chunk and not punct:
            continue
        segment = chunk + punct
        if len(buf) + len(segment) <= max_len:
            buf += segment
        else:
            if buf:
                lines.append(buf)
            buf = segment
    if buf:
        lines.append(buf)
    return "\n".join(lines) if len(lines) > 1 else text


def _fmt_nodes(obj, fields: set, max_len: int = 100):
    """递归遍历 JSON 结构，对指定字段名的字符串值应用 _fmt_text。

    用于在 skill execute() 中格式化返回给 AI 的数据。
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k in fields:
                obj[k] = _fmt_text(v, max_len)
            else:
                _fmt_nodes(v, fields, max_len)
    elif isinstance(obj, list):
        for item in obj:
            _fmt_nodes(item, fields, max_len)
    return obj
