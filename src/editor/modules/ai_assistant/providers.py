"""API 供应商抽象层 — Claude / OpenAI / 自定义。"""

import json
from abc import ABC, abstractmethod
from typing import Optional


class AIProvider(ABC):
    """AI 供应商抽象基类。"""

    @abstractmethod
    def send_message(self, messages: list[dict],
                     system_prompt: str = "",
                     on_stream: callable = None) -> str:
        ...


class ClaudeProvider(AIProvider):
    """Anthropic Claude API。"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6",
                 api_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    def send_message(self, messages: list[dict],
                     system_prompt: str = "",
                     on_stream: callable = None) -> str:
        import urllib.request
        import urllib.error

        # 将 messages 转为 Claude 格式
        claude_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                claude_messages.append({
                    "role": m["role"],
                    "content": m["content"],
                })

        body = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt or "",
            "messages": claude_messages,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.api_url}/v1/messages",
            data=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "User-Agent": "ReWrite/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("content", [])
                texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                result = "\n".join(texts)
                if on_stream:
                    on_stream(result)
                return result
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return f"[错误] HTTP {e.code}: {err_body[:200]}"
        except Exception as e:
            return f"[错误] {e}"


class OpenAIProvider(AIProvider):
    """OpenAI 兼容 API（也支持自定义端点）。"""

    def __init__(self, api_key: str, model: str = "gpt-4o",
                 api_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    def send_message(self, messages: list[dict],
                     system_prompt: str = "",
                     on_stream: callable = None) -> str:
        import urllib.request
        import urllib.error

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        body = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "messages": full_messages,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.api_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "User-Agent": "ReWrite/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                texts = [c["message"].get("content", "") for c in choices if c.get("message")]
                result = "\n".join(texts)
                if on_stream:
                    on_stream(result)
                return result
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return f"[错误] HTTP {e.code}: {err_body[:200]}"
        except Exception as e:
            return f"[错误] {e}"


def create_provider(provider_type: str, api_key: str,
                    model: str = "", api_url: str = "") -> AIProvider:
    """根据类型创建供应商实例。"""
    if provider_type == "claude":
        return ClaudeProvider(
            api_key=api_key,
            model=model or "claude-sonnet-4-6",
            api_url=api_url or "https://api.anthropic.com",
        )
    elif provider_type == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=model or "gpt-4o",
            api_url=api_url or "https://api.openai.com/v1",
        )
    elif provider_type == "deepseek":
        return OpenAIProvider(
            api_key=api_key,
            model=model or "deepseek-v4-flash",
            api_url=api_url or "https://api.deepseek.com",
        )
    else:
        # 自定义 — 使用 OpenAI 兼容格式
        return OpenAIProvider(
            api_key=api_key,
            model=model or "unknown",
            api_url=api_url or "https://api.openai.com/v1",
        )
