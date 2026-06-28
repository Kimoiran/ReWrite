"""Skill 基类 — 所有技能继承此接口。"""

from abc import ABC, abstractmethod
from typing import Any


class Skill(ABC):
    """单个可执行技能。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称（英文，用于 function calling）。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述（给 AI 看的）。"""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema 格式的参数定义。"""
        ...

    @abstractmethod
    def execute(self, args: dict[str, Any], work_name: str = "") -> dict:
        """执行技能，返回结果 dict。"""
        ...

    def summarize(self, result: dict, args: dict[str, Any] = None) -> str:
        """将执行结果转为自然语言描述。子类可覆盖。"""
        if result.get("success"):
            return f"✅ 已执行 {self.name}"
        return f"❌ {self.name} 失败: {result.get('error', '未知错误')}"

    def to_openai_tool(self) -> dict:
        """转为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def to_claude_tool(self) -> dict:
        """转为 Claude tool 格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
