"""AI 配置加载 — 供 AIAssistantModule 使用。"""

from pathlib import Path
from typing import Optional

from ..storage.paths import get_config_dir

AI_CONFIG_DIR = get_config_dir()
AI_CONFIG_PATH = AI_CONFIG_DIR / "ai_config.json"
AI_HISTORY_DIR = AI_CONFIG_DIR / "history"

DEFAULT_AI_CONFIG = {
    "provider": "",
    "api_key": "",
    "api_url": "",
    "model": "",
    "context_scope": ["current_chapter", "outline", "characters"],
    "system_prompt": "",
}


def load_ai_config() -> dict:
    """加载 AI 配置。"""
    import json
    if AI_CONFIG_PATH.exists():
        try:
            data = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_AI_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_AI_CONFIG)


def save_ai_config(config: dict):
    """保存 AI 配置。"""
    import json
    try:
        AI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        AI_CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        print(f"保存 AI 配置失败")


def load_chat_history(work_name: str) -> list[dict]:
    """加载作品对应的对话历史。"""
    import json
    path = AI_HISTORY_DIR / f"{work_name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_chat_history(work_name: str, history: list[dict]):
    """保存对话历史。"""
    import json
    try:
        AI_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        path = AI_HISTORY_DIR / f"{work_name}.json"
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        print(f"保存对话历史失败")
