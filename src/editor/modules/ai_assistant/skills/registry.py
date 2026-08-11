"""Skill 注册表 — 所有技能在此注册，供 Agent 和 MCP 共同使用。"""

from typing import Any

from .base_skill import Skill
from .character_skills import (GetCharacterGroupsSkill, GetCharactersSkill, CreateCharacterSkill,
                                UpdateCharacterSkill, AddGroupSkill, DeleteCharacterSkill, DeleteGroupSkill)
from .outline_skills import (GetOutlineSkill, CreateOutlineEntrySkill,
                             UpdateOutlineEntrySkill, DeleteOutlineEntrySkill)
from .chapter_skills import (GetChaptersSkill, ReadChapterSkill, CreateChapterSkill,
                                UpdateChapterSkill, RenameChapterSkill, DeleteChapterSkill)
from .timeline_skills import (CreateTimelineEventSkill, GetTimelineSkill,
                                UpdateTimelineEventSkill, DeleteTimelineEventSkill)
from .worldview_skills import (GetWorldviewSkill, CreateWorldviewEntrySkill,
                                UpdateWorldviewEntrySkill, DeleteWorldviewEntrySkill)
from .map_skills import (GetMapSkill, CreateMapNodeSkill, UpdateMapNodeSkill,
                          DeleteMapNodeSkill, CreateMapRouteSkill, DeleteMapRouteSkill)
from .rag_skills import SearchChaptersSkill


def get_all_skills() -> list[Skill]:
    """返回所有注册的技能实例。"""
    return [
        GetCharacterGroupsSkill(),
        GetCharactersSkill(),
        CreateCharacterSkill(),
        UpdateCharacterSkill(),
        AddGroupSkill(),
        DeleteCharacterSkill(),
        DeleteGroupSkill(),
        GetOutlineSkill(),
        CreateOutlineEntrySkill(),
        UpdateOutlineEntrySkill(),
        DeleteOutlineEntrySkill(),
        CreateTimelineEventSkill(),
        GetTimelineSkill(),
        UpdateTimelineEventSkill(),
        DeleteTimelineEventSkill(),
        GetWorldviewSkill(),
        UpdateWorldviewEntrySkill(),
        CreateWorldviewEntrySkill(),
        DeleteWorldviewEntrySkill(),
        GetMapSkill(),
        CreateMapNodeSkill(),
        UpdateMapNodeSkill(),
        DeleteMapNodeSkill(),
        CreateMapRouteSkill(),
        DeleteMapRouteSkill(),
        SearchChaptersSkill(),
        GetChaptersSkill(),
        ReadChapterSkill(),
        CreateChapterSkill(),
        UpdateChapterSkill(),
        RenameChapterSkill(),
        DeleteChapterSkill(),
    ]


def _normalize_name(name: str) -> str:
    """技能名规范化:去下划线/连字符/空格并小写(容错匹配用)。"""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def get_skill(name: str) -> Skill | None:
    """按名称查找技能。"""
    for s in get_all_skills():
        if s.name == name:
            return s
    # 容错:AI 可能去掉下划线/连字符(如 createoutlineentry → create_outline_entry)
    nn = _normalize_name(name)
    if nn:
        for s in get_all_skills():
            if nn == _normalize_name(s.name):
                return s
    return None


def execute_skill(name: str, args: dict[str, Any] = None, work_name: str = "") -> dict:
    """按名称执行技能。"""
    skill = get_skill(name)
    if not skill:
        return {"success": False, "error": f"未知技能: {name}"}
    try:
        return skill.execute(args, work_name)
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_openai_tools() -> list[dict]:
    """获取 OpenAI function calling 格式的工具定义。"""
    return [s.to_openai_tool() for s in get_all_skills()]


def get_claude_tools() -> list[dict]:
    """获取 Claude tool 格式的工具定义。"""
    return [s.to_claude_tool() for s in get_all_skills()]
