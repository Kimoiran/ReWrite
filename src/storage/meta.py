"""作品元数据模型（work.json）。"""

import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# 模块 ID 列表
AVAILABLE_MODULES = ["chapters", "characters", "outline", "timeline", "worldview", "ai_assistant"]

# 模块中文名映射
MODULE_NAMES = {
    "chapters": "章节管理",
    "characters": "人物设定卡",
    "outline": "大纲",
    "timeline": "时间线",
    "ai_assistant": "AI 写作助手",
}

# 作品类型
WORK_TYPES = ["novel", "essay", "script", "poem", "other"]
WORK_TYPE_NAMES = {
    "novel": "小说",
    "essay": "随笔",
    "script": "剧本",
    "poem": "诗歌",
    "other": "其他",
}

# 封面颜色池
COVER_COLORS = [
    "#2d5a3d", "#5a3d2d", "#3d5a7a", "#7a3d5a",
    "#5a7a3d", "#3d6b6b", "#6b3d6b", "#6b6b3d",
    "#4a6741", "#67414a", "#416767", "#674141",
]


@dataclass
class GitRemote:
    enabled: bool = False
    url: str = ""
    auto_push: bool = False


@dataclass
class GitConfig:
    enabled: bool = True
    remote: GitRemote = field(default_factory=GitRemote)


@dataclass
class WorkMeta:
    title: str
    work_type: str = "novel"
    modules: list = field(default_factory=lambda: ["chapters"])
    git: GitConfig = field(default_factory=GitConfig)
    created: str = ""
    updated: str = ""
    tags: list = field(default_factory=list)
    status: str = "active"
    total_words: int = 0
    cover_color: str = ""
    cloud_enabled: bool = False

    def __post_init__(self):
        if isinstance(self.git, dict):
            git_data = self.git
            remote_data = git_data.get("remote", {})
            if isinstance(remote_data, dict):
                self.git = GitConfig(
                    enabled=git_data.get("enabled", True),
                    remote=GitRemote(
                        enabled=remote_data.get("enabled", False),
                        url=remote_data.get("url", ""),
                        auto_push=remote_data.get("auto_push", False),
                    ),
                )
            else:
                self.git = GitConfig(enabled=git_data.get("enabled", True))

    @staticmethod
    def new(title: str, work_type: str = "novel",
            modules: list = None, git_enabled: bool = True,
            git_remote: str = "", git_auto_push: bool = False) -> "WorkMeta":
        now = datetime.now(timezone.utc).isoformat()
        if modules is None:
            modules = ["chapters"]
        if "chapters" not in modules:
            modules.insert(0, "chapters")
        return WorkMeta(
            title=title,
            work_type=work_type,
            modules=modules,
            git=GitConfig(
                enabled=git_enabled,
                remote=GitRemote(
                    enabled=bool(git_remote),
                    url=git_remote,
                    auto_push=git_auto_push,
                ),
            ),
            created=now,
            updated=now,
            cover_color=random.choice(COVER_COLORS),
        )


def load_meta(path: Path) -> Optional[WorkMeta]:
    """从 work.json 加载元数据。文件不存在或损坏时返回 None。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkMeta(**data)
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        print(f"警告: 读取元数据失败 {path}: {e}")
        return None


def save_meta(path: Path, meta: WorkMeta) -> bool:
    """将元数据写入 work.json。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(meta)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except (OSError, TypeError) as e:
        print(f"错误: 写入元数据失败 {path}: {e}")
        return False


def type_to_name(work_type: str) -> str:
    """作品类型代码转显示名称。"""
    return WORK_TYPE_NAMES.get(work_type, work_type)


def module_to_name(module_id: str) -> str:
    """模块 ID 转显示名称。"""
    return MODULE_NAMES.get(module_id, module_id)
