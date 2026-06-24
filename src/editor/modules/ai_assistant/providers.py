"""API 供应商抽象层 — Claude / OpenAI / 自定义 + 工具调用。"""

import json
from abc import ABC, abstractmethod
from typing import Optional


# ── MCP 工具定义（JSON Schema 格式，供 function calling 使用） ──

MCP_TOOLS = [
    {
        "name": "add_group",
        "description": "创建人物分组",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "分组名称"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_character",
        "description": "创建新角色",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "group": {"type": "string", "description": "所属分组/文件夹名称（如不存在自动创建）"},
                "age": {"type": "string", "description": "年龄"},
                "gender": {"type": "string", "description": "性别"},
                "occupation": {"type": "string", "description": "职业/身份"},
                "appearance": {"type": "string", "description": "外貌描述"},
                "personality": {"type": "string", "description": "性格特征"},
                "background": {"type": "string", "description": "背景故事"},
                "goals": {"type": "string", "description": "动机/目标"},
                "notes": {"type": "string", "description": "备注"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_character",
        "description": "修改角色字段值",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "field": {"type": "string", "description": "字段名: name/aliases/age/gender/occupation/appearance/personality/background/goals/notes"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],
        },
    },
    {
        "name": "update_outline_entry",
        "description": "修改大纲条目",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "条目名称"},
                "field": {"type": "string", "description": "title/content/status"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],
        },
    },
    {
        "name": "update_timeline_event",
        "description": "修改时间线事件",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "事件标题"},
                "field": {"type": "string", "description": "date/title/description"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["title", "field", "value"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in MCP_TOOLS}


def _execute_tool(tool_name: str, args: dict) -> str:
    """执行 MCP 工具并返回结果文本。"""
    from mcp.tools import call_tool, _get_works_dir
    from mcp.tools import list_works as _lw
    # 自动注入 work 参数
    if tool_name != "list_works" and "work" not in args:
        import os as _os
        # 优先用当前打开的作品
        current = _os.environ.get("REWRITE_CURRENT_WORK", "")
        if current:
            args["work"] = current
        else:
            works_dir = str(_get_works_dir())
            works = _lw()
            if works:
                args["work"] = works[0]["name"]
            else:
                return json.dumps({"success": False, "error": f"未找到任何作品 (works目录: {works_dir})"}, ensure_ascii=False)
    result = call_tool(tool_name, args)
    return json.dumps(result, ensure_ascii=False)


class AIProvider(ABC):
    @abstractmethod
    def send_message(self, messages: list[dict],
                     system_prompt: str = "",
                     on_stream: callable = None) -> str:
        ...

    def send_with_tools(self, messages: list[dict],
                        system_prompt: str = "",
                        on_stream: callable = None) -> str:
        """发送消息 + 工具调用支持。AI 决定是否调工具，不污染对话历史。"""
        return self.send_message(messages, system_prompt, on_stream)


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6",
                 api_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    def send_message(self, messages: list[dict],
                     system_prompt: str = "",
                     on_stream: callable = None) -> str:
        import urllib.request, urllib.error
        claude_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                claude_messages.append({"role": m["role"], "content": m["content"]})

        body = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt or "",
            "messages": claude_messages,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.api_url}/v1/messages", data=body,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                texts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
                return "\n".join(texts)
        except urllib.error.HTTPError as e:
            return f"[错误] HTTP {e.code}"
        except Exception as e:
            return f"[错误] {e}"

    def send_with_tools(self, messages, system_prompt="", on_stream=None):
        """Claude 工具调用。用单独轮次执行，不污染历史。"""
        import urllib.request, urllib.error
        claude_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                content = m["content"]
                claude_messages.append({"role": m["role"], "content": content})

        # 第一轮：带工具定义
        body = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": (system_prompt or "") + "\n\n可用工具: add_group, create_character, update_character, update_outline_entry, update_timeline_event",
            "messages": claude_messages,
            "tools": [{"name": t["name"], "description": t["description"],
                       "input_schema": t["input_schema"]} for t in MCP_TOOLS],
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.api_url}/v1/messages", data=body,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            return f"[错误] HTTP {e.code}: {err[:200]}"
        except Exception as e:
            return f"[错误] {e}"

        # 检查是否有工具调用
        content_blocks = data.get("content", [])
        tool_use = None
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "tool_use":
                tool_use = block
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        if not tool_use:
            result = "\n".join(text_parts)
            if on_stream:
                on_stream(result)
            return result

        # 执行工具（不保存到历史）
        tool_name = tool_use.get("name", "")
        tool_args = tool_use.get("input", {})
        tool_result = _execute_tool(tool_name, tool_args)

        # 第二轮：把工具结果发给 AI 生成最终回复
        claude_messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": "\n".join(text_parts)},
                        {"type": "tool_use", "id": tool_use["id"],
                         "name": tool_name, "input": tool_args}]
        })
        claude_messages.append({
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use["id"],
                         "content": tool_result}]
        })

        body2 = json.dumps({
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt or "",
            "messages": claude_messages,
        }).encode("utf-8")

        req2 = urllib.request.Request(
            f"{self.api_url}/v1/messages", data=body2,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"},
        )
        try:
            with urllib.request.urlopen(req2, timeout=120) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
                final_texts = [b.get("text", "") for b in data2.get("content", []) if b.get("type") == "text"]
                result = "\n".join(final_texts)
                if on_stream:
                    on_stream(result)
                return result
        except Exception as e:
            return f"[工具已执行] {tool_name}: {tool_result[:100]}"


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o",
                 api_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    def send_message(self, messages, system_prompt="", on_stream=None):
        import urllib.request, urllib.error
        full = []
        if system_prompt:
            full.append({"role": "system", "content": system_prompt})
        full.extend(messages)
        body = json.dumps({"model": self.model, "max_tokens": 4096, "messages": full}).encode("utf-8")
        req = urllib.request.Request(f"{self.api_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                texts = [c["message"].get("content", "") for c in data.get("choices", []) if c.get("message")]
                return "\n".join(texts)
        except urllib.error.HTTPError as e:
            return f"[错误] HTTP {e.code}"
        except Exception as e:
            return f"[错误] {e}"

    def send_with_tools(self, messages, system_prompt="", on_stream=None):
        """OpenAI/DeepSeek 工具调用。"""
        import urllib.request, urllib.error
        full = []
        if system_prompt:
            full.append({"role": "system", "content": system_prompt})
        full.extend(messages)

        # 第一轮
        openai_tools = [{"type": "function", "function": {
            "name": t["name"], "description": t["description"],
            "parameters": t["input_schema"],
        }} for t in MCP_TOOLS]

        # 构建请求体，content 为 null 时转为空字符串
        body = json.dumps({"model": self.model, "max_tokens": 4096,
                           "messages": full, "tools": openai_tools}).encode("utf-8")
        req = urllib.request.Request(f"{self.api_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            return f"[错误] HTTP {e.code}: {err[:200]}"
        except Exception as e:
            return f"[错误] {e}"

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            if on_stream:
                on_stream(content)
            return content

        # 执行工具，记录执行摘要
        executed = []
        full.append({"role": "assistant", "content": content,
                     "tool_calls": [{"id": tc["id"], "type": "function",
                                     "function": {"name": tc["function"]["name"],
                                                  "arguments": tc["function"]["arguments"]}}
                                    for tc in tool_calls]})
        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}
            tool_result = _execute_tool(func_name, func_args)
            full.append({"role": "tool", "tool_call_id": tc["id"],
                         "content": tool_result})
            executed.append(f"{func_name}({func_args.get('name','') or func_args.get('title','')})")

        # 第二轮 - 让 AI 生成友好的回复
        body2 = json.dumps({"model": self.model, "max_tokens": 4096, "messages": full}).encode("utf-8")
        req2 = urllib.request.Request(f"{self.api_url}/chat/completions", data=body2,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req2, timeout=120) as resp2:
                data2 = json.loads(resp2.read().decode("utf-8"))
                texts = [c["message"].get("content", "") for c in data2.get("choices", []) if c.get("message")]
                result = "\n".join(texts).strip()
                if result:
                    if on_stream:
                        on_stream(result)
                    return result
        except Exception:
            pass

        # 兜底：如果第二轮失败，返回友好的执行摘要
        summary = "✅ 已执行：\n" + "\n".join(f"  - {e}" for e in executed)
        if on_stream:
            on_stream(summary)
        return summary


def create_provider(provider_type, api_key, model="", api_url=""):
    if provider_type == "claude":
        return ClaudeProvider(api_key, model or "claude-sonnet-4-6", api_url or "https://api.anthropic.com")
    elif provider_type == "openai":
        return OpenAIProvider(api_key, model or "gpt-4o", api_url or "https://api.openai.com/v1")
    elif provider_type == "deepseek":
        return OpenAIProvider(api_key, model or "deepseek-v4-flash", api_url or "https://api.deepseek.com")
    else:
        return OpenAIProvider(api_key, model or "unknown", api_url or "https://api.openai.com/v1")
