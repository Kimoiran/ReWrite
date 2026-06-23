"""上下文收集器 — 从各模块读取内容供 AI 使用。"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..chapters import ChapterModule
    from ..characters import CharacterModule
    from ..outline import OutlineModule
    from ..timeline import TimelineModule


def collect_context(scope: list[str], current_html: str = "",
                    current_selection: str = "",
                    chapter_module=None, character_module=None,
                    outline_module=None, timeline_module=None,
                    work_meta: Optional[dict] = None) -> str:
    """收集 AI 上下文，返回纯文本。

    scope: 需要收集的模块列表
    """
    parts = []

    if "current_chapter" in scope and current_html:
        import re
        text = re.sub(r"<[^>]+>", "", current_html).strip()
        if text:
            parts.append(f"--- 当前章节内容 ---\n{text[:8000]}")

    if "selected_text" in scope and current_selection:
        import re
        sel = re.sub(r"<[^>]+>", "", current_selection).strip()
        if sel:
            parts.append(f"--- 用户选中的文本 ---\n{sel[:3000]}")

    if "outline" in scope and outline_module:
        texts = _outline_text(outline_module.entries)
        if texts:
            parts.append(f"--- 大纲 ---\n{texts[:3000]}")

    if "characters" in scope and character_module:
        texts = _characters_text(character_module.characters)
        if texts:
            parts.append(f"--- 人物设定 ---\n{texts[:3000]}")

    if "timeline" in scope and timeline_module:
        texts = _timeline_text(timeline_module.events)
        if texts:
            parts.append(f"--- 时间线 ---\n{texts[:2000]}")

    if "work_meta" in scope and work_meta:
        info = []
        if work_meta.get("title"):
            info.append(f"作品名称: {work_meta['title']}")
        if work_meta.get("work_type"):
            info.append(f"类型: {work_meta.get('work_type', '')}")
        if work_meta.get("tags"):
            info.append(f"标签: {', '.join(work_meta['tags'])}")
        if work_meta.get("total_words"):
            info.append(f"总字数: {work_meta['total_words']}")
        if info:
            parts.append("--- 作品信息 ---\n" + "\n".join(info))

    return "\n\n".join(parts)


def _outline_text(entries, depth=0) -> str:
    text = ""
    prefix = "  " * depth
    for e in entries:
        text += f"{prefix}- {e.title}"
        if e.status:
            text += f" [{e.status}]"
        text += "\n"
        if e.children:
            text += _outline_text(e.children, depth + 1)
    return text


def _characters_text(characters) -> str:
    text = ""
    for c in characters:
        text += f"- {c.name}"
        if c.aliases:
            text += f" (别名: {c.aliases})"
        text += "\n"
        if c.occupation:
            text += f"  身份: {c.occupation}\n"
        if c.personality:
            text += f"  性格: {c.personality[:100]}\n"
        if c.background:
            text += f"  背景: {c.background[:100]}\n"
    return text


def _timeline_text(events) -> str:
    text = ""
    for e in events:
        text += f"- {e.date}: {e.title}\n"
        if e.description:
            text += f"  {e.description[:100]}\n"
    return text
