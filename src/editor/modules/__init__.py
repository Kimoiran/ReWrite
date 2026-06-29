"""模块注册表——所有可选模块在此注册。"""

from .base_module import BaseModule
from .chapters import ChapterModule
from .characters import CharacterModule
from .outline import OutlineModule
from .timeline import TimelineModule
from .worldview import WorldviewModule
from .map import MapModule
from .ai_assistant.module import AIAssistantModule

MODULE_MAP = {
    "chapters": ChapterModule,
    "characters": CharacterModule,
    "outline": OutlineModule,
    "timeline": TimelineModule,
    "worldview": WorldviewModule,
    "map": MapModule,
    "ai_assistant": AIAssistantModule,
}

MODULE_DISPLAY_NAMES = {
    "chapters": "章节管理",
    "characters": "人物设定卡",
    "outline": "大纲",
    "timeline": "时间线",
    "worldview": "世界观",
    "map": "地图",
    "ai_assistant": "AI 写作助手",
}
