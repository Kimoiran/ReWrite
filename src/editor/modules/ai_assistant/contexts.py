"""上下文收集器 — 从各模块读取内容供 AI 使用，带架构标注。"""

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
                    worldview_module=None,
                    work_meta: Optional[dict] = None) -> str:
    """收集 AI 上下文，返回纯文本。每个模块带类型标注。"""
    parts = []

    if "current_chapter" in scope and current_html:
        import re
        text = re.sub(r"<[^>]+>", "", current_html).strip()
        if text:
            parts.append(f"<<<章节正文 (chapters)>>>\n{text[:8000]}")

    if "selected_text" in scope and current_selection:
        import re
        sel = re.sub(r"<[^>]+>", "", current_selection).strip()
        if sel:
            parts.append(f"<<<用户选中的文本 (selection)>>>\n{sel[:3000]}")

    if "outline" in scope and outline_module:
        texts = _outline_text(outline_module.entries)
        if texts:
            parts.append(f"<<<大纲 (outline) — 树形层级结构>>>\n{texts[:3000]}")
        else:
            parts.append("<<<大纲 (outline) — (当前为空) 每条有 title/content/status(待写/写作中/已完成)/children，可无限嵌套>>>\n(暂无内容)")

    if "characters" in scope and character_module:
        texts = _characters_text(character_module.nodes)
        if texts:
            parts.append(f"<<<人物设定卡 (characters) — 树形分组>>>\n{texts[:3000]}")
        else:
            parts.append("<<<人物设定卡 (characters) — (当前为空) 角色有 name/age/gender/occupation/appearance/personality/background/goals/notes，支持多级分组>>>\n(暂无内容)")

    if "timeline" in scope and timeline_module:
        texts = _timeline_text(timeline_module.events)
        if texts:
            parts.append(f"<<<时间线 (timeline) — 事件按日期排列>>>\n{texts[:2000]}")
        else:
            parts.append("<<<时间线 (timeline) — (当前为空) 每条有 date/title/description，按日期自动排序>>>\n(暂无内容)")

    if "worldview" in scope and worldview_module:
        wv_text = ""
        if hasattr(worldview_module, "to_text"):
            wv_text = worldview_module.to_text()
        if wv_text.strip():
            parts.append(f"<<<世界观 (worldview) — 世界设定，分章节记录>>>\n{wv_text[:3000]}")
        else:
            parts.append("<<<世界观 (worldview) — (当前为空) 每条有 title/content，可无限嵌套层级>>>\n(暂无内容)")

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
            parts.append("<<<作品信息 (work_meta)>>>\n" + "\n".join(info))

    return "\n\n".join(parts)


def _outline_text(entries, depth=0) -> str:
    """大纲格式化输出：层级 + 标题 + 状态 + 内容。"""
    text = ""
    prefix = "  " * depth
    for e in entries:
        status_tag = {"待写": "[待写]", "写作中": "[写作中]", "已完成": "[已完成]"}.get(e.status, "")
        text += f"{prefix}▶ {e.title} {status_tag}"
        text += "\n"
        if e.content:
            # 多行内容逐行缩进
            for line in e.content.split("\n")[:5]:
                text += f"{prefix}  {line}\n"
            if len(e.content.split("\n")) > 5:
                text += f"{prefix}  ...(还有更多内容)\n"
        if e.children:
            text += _outline_text(e.children, depth + 1)
    return text


def _characters_text(nodes, depth=0) -> str:
    """人物卡格式化输出：树形分组 + 完整字段。"""
    parts = []

    def _walk(nodes, depth):
        for n in nodes:
            indent = "  " * depth
            if n.is_group:
                parts.append(f"{indent}📁 分组: {n.name}")
            else:
                parts.append(f"{indent}👤 人物: {n.name}")
                fields = []
                if n.aliases: fields.append(f"别名={n.aliases}")
                if n.age: fields.append(f"年龄={n.age}")
                if n.gender and n.gender != "未设置": fields.append(f"性别={n.gender}")
                if n.occupation: fields.append(f"身份={n.occupation}")
                if fields:
                    parts.append(f"{indent}  [{', '.join(fields)}]")
                if n.appearance: parts.append(f"{indent}  外貌: {n.appearance[:80]}")
                if n.personality: parts.append(f"{indent}  性格: {n.personality[:80]}")
                if n.background: parts.append(f"{indent}  背景: {n.background[:80]}")
                if n.goals: parts.append(f"{indent}  目标: {n.goals[:80]}")
            if n.children:
                _walk(n.children, depth + 1)

    _walk(nodes, 0)
    return "\n".join(parts)


def _timeline_text(events) -> str:
    """时间线格式化输出：日期 + 标题 + 描述。"""
    text = ""
    for e in events:
        text += f"📅 [{e.date}] {e.title}\n"
        if e.description:
            for line in e.description.split("\n")[:3]:
                text += f"   {line}\n"
            if len(e.description.split("\n")) > 3:
                text += f"   ...\n"
    return text
