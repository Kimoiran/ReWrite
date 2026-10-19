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


# ─────────────────────────────────────────────────────────────
# 技能 → 所属功能模块（对应 work.json 的 modules 字段）
#
# 作品创建时可以只启用部分模块。AI 的工具清单必须跟着收窄，
# 否则它会去调用本作品根本不存在的功能（例如没开人物卡却调
# create_character），用户看到的就是「关了的功能 AI 还在写」。
# ─────────────────────────────────────────────────────────────

SKILL_MODULES: dict[str, set] = {
    "chapters": {
        "get_chapters", "read_chapter", "create_chapter",
        "update_chapter", "rename_chapter", "delete_chapter",
        "search_chapters",   # 语义搜索扫的是章节正文
    },
    "characters": {
        "get_character_groups", "get_characters", "create_character",
        "update_character", "delete_character", "add_group", "delete_group",
    },
    "outline": {
        "get_outline", "create_outline_entry",
        "update_outline_entry", "delete_outline_entry",
    },
    "timeline": {
        "create_timeline_event", "get_timeline",
        "update_timeline_event", "delete_timeline_event",
    },
    "worldview": {
        "get_worldview", "create_worldview_entry",
        "update_worldview_entry", "delete_worldview_entry",
    },
    "map": {
        "get_map", "create_map_node", "update_map_node",
        "delete_map_node", "create_map_route", "delete_map_route",
    },
}

# 工具名 → 模块 id（SKILL_MODULES 的反查表）
TOOL_MODULE: dict[str, str] = {
    name: mod for mod, names in SKILL_MODULES.items() for name in names
}

# 生成提示词时的展示顺序与标题
MODULE_LABELS: dict[str, str] = {
    "chapters": "📖 章节",
    "characters": "👤 人物卡",
    "outline": "📋 大纲",
    "timeline": "📅 时间线",
    "worldview": "🌍 世界观",
    "map": "🗺️ 地图",
}

# 章节是必选模块（create_work 强制包含），这里再兜一次底
ALWAYS_ENABLED = {"chapters"}


def skill_module(name: str) -> str | None:
    """返回技能所属模块 id；未知技能返回 None。"""
    return TOOL_MODULE.get(name)


def allowed_modules(modules) -> set:
    """规范化允许的模块集合：None = 全部启用。"""
    if modules is None:
        return set(SKILL_MODULES)
    return set(modules) | ALWAYS_ENABLED


def tool_enabled(name: str, modules) -> bool:
    """该技能在其所属模块未启用时不可用。

    ``modules=None`` 表示不做限制（全局能力探测/测试用）。
    """
    if modules is None:
        return True
    mod = skill_module(name)
    return mod is None or mod in allowed_modules(modules)


def get_skills_for_modules(modules=None) -> list[Skill]:
    """按作品启用的模块过滤技能。modules=None 返回全部。"""
    if modules is None:
        return get_all_skills()
    allowed = allowed_modules(modules)
    return [s for s in get_all_skills() if skill_module(s.name) in allowed]


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


def get_openai_tools(modules=None) -> list[dict]:
    """获取 OpenAI function calling 格式的工具定义。

    :param modules: 作品启用的模块集合；None = 全部（不做限制）。
    """
    return [s.to_openai_tool() for s in get_skills_for_modules(modules)]


def get_claude_tools(modules=None) -> list[dict]:
    """获取 Claude tool 格式的工具定义（modules 语义同 get_openai_tools）。"""
    return [s.to_claude_tool() for s in get_skills_for_modules(modules)]
