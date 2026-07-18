"""API 供应商抽象层 — Claude / OpenAI / 自定义 + 工具调用。"""

import json
import urllib.request, urllib.error
from abc import ABC, abstractmethod

from .skills.registry import get_all_skills, get_skill, execute_skill, get_openai_tools, get_claude_tools

SKILLS = get_all_skills()
TOOL_NAMES = {s.name for s in SKILLS}


def _describe_tool(tool_name: str, args: dict, result: dict) -> str:
    """将工具执行结果转为自然语言描述。"""
    skill = get_skill(tool_name)
    if skill and hasattr(skill, 'summarize'):
        return skill.summarize(result, args)
    if result.get("success") is False:
        return f"❌ {tool_name} 失败: {result.get('error', '未知错误')}"
    return f"✅ 已执行 {tool_name}"


def _execute_tool(tool_name: str, args: dict) -> str:
    """执行 Skill 并返回描述文本。"""
    if tool_name != "list_works" and "work" not in args:
        import os as _os
        current = _os.environ.get("REWRITE_CURRENT_WORK", "")
        if current:
            args["work"] = current
        else:
            from .skills._shared import list_works as _lw
            works = _lw()
            if works:
                args["work"] = works[0]["name"]
            else:
                return "❌ 未找到作品"
    result = execute_skill(tool_name, args)
    return _describe_tool(tool_name, args, result)


class AIProvider(ABC):
    @abstractmethod
    def send_message(self, messages, system_prompt="", on_stream=None):
        ...

    def send_with_tools(self, messages, system_prompt="", on_stream=None):
        return self.send_message(messages, system_prompt, on_stream)


class ClaudeProvider(AIProvider):
    def __init__(self, api_key="", model="claude-sonnet-4-6",
                 api_url="https://api.anthropic.com"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    def send_message(self, messages, system_prompt="", on_stream=None):
        import urllib.request, urllib.error
        claude = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                claude.append({"role": m["role"], "content": m["content"]})
        body = json.dumps({"model": self.model, "max_tokens": 4096,
            "system": system_prompt or "", "messages": claude}).encode("utf-8")
        req = urllib.request.Request(f"{self.api_url}/v1/messages", data=body,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
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
        import urllib.request, urllib.error
        claude = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                claude.append({"role": m["role"], "content": m["content"]})
        tools = get_claude_tools()
        body = json.dumps({"model": self.model, "max_tokens": 4096,
            "system": (system_prompt or "") + "\n\n可用工具: " + ", ".join(t["name"] for t in tools),
            "messages": claude, "tools": tools}).encode("utf-8")
        req = urllib.request.Request(f"{self.api_url}/v1/messages", data=body,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return f"[错误] {e}"

        tool_use = None
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                tool_use = block
            elif block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        if not tool_use:
            return "\n".join(text_parts)

        tool_result = _execute_tool(tool_use.get("name", ""), tool_use.get("input", {}))
        name = tool_use.get("name", "")
        claude.append({"role": "assistant", "content": [
            {"type": "text", "text": "\n".join(text_parts)},
            {"type": "tool_use", "id": tool_use["id"], "name": name, "input": tool_use["input"]}
        ]})
        claude.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use["id"], "content": tool_result}
        ]})
        body2 = json.dumps({"model": self.model, "max_tokens": 4096,
            "system": system_prompt or "", "messages": claude}).encode("utf-8")
        req2 = urllib.request.Request(f"{self.api_url}/v1/messages", data=body2,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req2, timeout=120) as resp2:
                d2 = json.loads(resp2.read().decode("utf-8"))
                texts = [b.get("text", "") for b in d2.get("content", []) if b.get("type") == "text"]
                result = "\n".join(texts).strip()
                if result:
                    return result
        except Exception:
            pass
        return f"工具已执行: {name}"


class OpenAIProvider(AIProvider):
    def __init__(self, api_key="", model="gpt-4o",
                 api_url="https://api.openai.com/v1"):
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
        import urllib.request, urllib.error
        full = []
        if system_prompt:
            full.append({"role": "system", "content": system_prompt})
        full.extend(messages)
        tools = get_openai_tools()
        body = json.dumps({"model": self.model, "max_tokens": 4096,
            "messages": full, "tools": tools}).encode("utf-8")
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

        executed = []
        full.append({"role": "assistant", "content": content,
            "tool_calls": [{"id": tc["id"], "type": "function",
                "function": {"name": tc["function"]["name"],
                             "arguments": tc["function"]["arguments"]}}
                for tc in tool_calls]})
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}
            r = _execute_tool(name, args)
            full.append({"role": "tool", "tool_call_id": tc["id"], "content": r})
            executed.append(f"{name}({args.get('name','') or args.get('title','')})")

        body2 = json.dumps({"model": self.model, "max_tokens": 4096, "messages": full}).encode("utf-8")
        req2 = urllib.request.Request(f"{self.api_url}/chat/completions", data=body2,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
        try:
            with urllib.request.urlopen(req2, timeout=120) as resp2:
                d2 = json.loads(resp2.read().decode("utf-8"))
                texts = [c["message"].get("content", "") for c in d2.get("choices", []) if c.get("message")]
                result = "\n".join(texts).strip()
                if result:
                    return result
        except Exception:
            pass
        return "工具已执行: " + ", ".join(executed)


def _make_chat_request(agent, messages: list, system_prompt: str = "", tools: list = None) -> dict:
    """发送底层聊天请求，返回原始响应 dict。不处理历史，不持久化。
    统一用 OpenAI 兼容格式（DeepSeek / OpenAI / 自定义都支持）。"""
    config = agent.config
    api_key = config.get("api_key", "")
    model = config.get("model", "deepseek-v4-flash")
    api_url = config.get("api_url", "https://api.deepseek.com")

    url = api_url.rstrip("/") + "/chat/completions"
    full = []
    if system_prompt and system_prompt.strip():
        full.append({"role": "system", "content": system_prompt})
    full.extend(messages)
    payload = {"model": model, "max_tokens": 8192, "messages": full}
    if tools:
        payload["tools"] = tools
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def _extract_reasoning(data: dict) -> str:
    """从 API 响应中提取推理内容（DeepSeek 的 reasoning_content）。"""
    try:
        delta = data.get("choices", [{}])[0].get("delta", {})
        if "reasoning_content" in delta:
            return delta["reasoning_content"] or ""
        # 非流式响应
        msg = data.get("choices", [{}])[0].get("message", {})
        if "reasoning_content" in msg:
            return msg["reasoning_content"] or ""
    except Exception:
        pass
    return ""


def _make_streaming_request(agent, messages: list, system_prompt: str = "",
                             on_reasoning=None, on_content=None, tools: list = None):
    """流式请求，边接收边回调。返回 (full_text, tool_calls, reasoning)。

    - on_reasoning(chunk): 收到推理内容时回调
    - on_content(chunk): 收到正文内容时回调
    - tools: 可选工具定义，传入后启用 function calling
    """
    import urllib.request, urllib.error, json as _json
    config = agent.config
    api_key = config.get("api_key", "")
    model = config.get("model", "deepseek-v4-flash")
    api_url = config.get("api_url", "https://api.deepseek.com")

    url = api_url.rstrip("/") + "/chat/completions"
    full = []
    if system_prompt and system_prompt.strip():
        full.append({"role": "system", "content": system_prompt})
    full.extend(messages)

    payload = {"model": model, "max_tokens": 8192, "messages": full, "stream": True}
    if tools:
        payload["tools"] = tools
    body = _json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
        headers={"Authorization": f"Bearer {api_key}",
                 "content-type": "application/json"})

    result_parts = []
    reasoning_parts = []
    # 流式 tool_calls 累积：index → {id, function.name, function.arguments}
    tool_calls_map = {}

    with urllib.request.urlopen(req, timeout=180) as resp:
        raw_buffer = b""
        done = False
        while not done:
            raw_chunk = resp.read(4096)
            if not raw_chunk:
                break
            raw_buffer += raw_chunk
            # 统一换行符：\r\n → \n
            raw_buffer = raw_buffer.replace(b"\r\n", b"\n")
            # SSE 帧由 \n\n 分隔，确保在帧边界解码 UTF-8（避免拆散多字节中文）
            while b"\n\n" in raw_buffer:
                frame, raw_buffer = raw_buffer.split(b"\n\n", 1)
                text = frame.decode("utf-8", errors="replace")
                for line in text.strip().split("\n"):
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            done = True
                            break
                        try:
                            data = _json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})

                            if "reasoning_content" in delta and delta["reasoning_content"]:
                                reasoning_parts.append(delta["reasoning_content"])
                                if on_reasoning:
                                    on_reasoning(delta["reasoning_content"])

                            if "content" in delta and delta["content"]:
                                result_parts.append(delta["content"])
                                if on_content:
                                    on_content(delta["content"])

                            # 累积流式 tool_calls（按 index 合并）
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    idx = tc.get("index", 0)
                                    if idx not in tool_calls_map:
                                        tool_calls_map[idx] = {
                                            "id": "", "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        }
                                    entry = tool_calls_map[idx]
                                    if "id" in tc and tc["id"]:
                                        entry["id"] = tc["id"]
                                    if "function" in tc:
                                        f = tc["function"]
                                        if "name" in f and f["name"]:
                                            entry["function"]["name"] = f["name"]
                                        if "arguments" in f:
                                            entry["function"]["arguments"] += f["arguments"]
                        except _json.JSONDecodeError:
                            pass
                if done:
                    break

    full_text = "".join(result_parts)
    reasoning = "".join(reasoning_parts)
    tool_calls = list(tool_calls_map.values()) if tool_calls_map else []

    if tool_calls:
        import logging
        logger = logging.getLogger("rewrite.ai")
        logger.info(f"流式请求收集到 {len(tool_calls)} 个工具调用: "
                    f"{[(tc['function']['name'], tc['function']['arguments'][:200]) for tc in tool_calls]}")

    return full_text, tool_calls, reasoning


_FAKE_PATTERN = ["✅ ", "已修改", "已创建", "已删除", "已更新", "已完成", "已恢复", "操作完成"]


def _check_fake_completion(content: str) -> str:
    """检测 AI 是否在没有调用工具的情况下假装完成了操作。"""
    if not content:
        return ""
    for marker in _FAKE_PATTERN:
        if marker in content:
            return "未检测到工具调用——以上内容仅为 AI 文字描述，数据未被实际修改。请重新操作。"
    return ""


def _ensure_work_args(tool_name: str, args: dict):
    """为工具调用注入 work 参数。"""
    if tool_name != "list_works" and "work" not in args:
        import os as _os
        current = _os.environ.get("REWRITE_CURRENT_WORK", "")
        if current:
            args["work"] = current
        else:
            from .skills._shared import list_works as _lw
            works = _lw()
            if works:
                args["work"] = works[0]["name"]


def get_proposals_only(agent, message: str, context: str = ""):
    """第一轮：发给 AI，只获取工具调用提案，不执行。
    返回 (tool_calls, messages_before, messages_after) 或 错误文本。
    """
    import json as _j
    from .prompt_templates import DEFAULT_SYSTEM_PROMPT

    config = agent.config
    provider = create_provider(
        config.get("provider", ""),
        config.get("api_key", ""),
        config.get("model", ""),
        config.get("api_url", ""),
    )

    if not hasattr(provider, "send_with_tools"):
        return agent.send_message(message, current_context=context)

    system = config.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
    if context:
        system += f"\n\n## 当前作品上下文\n{context}"

    agent.history.append({"role": "user", "content": message})
    recent = agent.history[-40:]

    # 构建请求
    full = [{"role": "system", "content": system}]
    full.extend(recent)
    tools = get_openai_tools()

    body = _j.dumps({"model": provider.model, "max_tokens": 4096,
                      "messages": full, "tools": tools}).encode("utf-8")

    import urllib.request, urllib.error
    req = urllib.request.Request(f"{provider.api_url}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {provider.api_key}",
                 "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _j.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return f"[错误] HTTP {e.code}: {err[:200]}"
    except Exception as e:
        return f"[错误] {e}"

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content") or ""
    tool_calls = msg.get("tool_calls", [])
    reasoning = msg.get("reasoning_content", "") or data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")

    if not tool_calls:
        agent.history.append({"role": "assistant", "content": content})
        agent._persist()
        # 推理内容用特殊标记包围，在 markdown 渲染前提取
        if reasoning:
            content = f"<!--REASONING-->\n{reasoning}\n<!--/REASONING-->\n\n{content}"
        fake_check = _check_fake_completion(content)
        if fake_check:
            content = f"⚠️ {fake_check}\n\n{content}"
        return content

    # 构建传递用的 messages
    before = list(full)
    after = [{"role": "assistant", "content": content,
              "tool_calls": [{"id": tc["id"], "type": "function",
                              "function": {"name": tc["function"]["name"],
                                          "arguments": tc["function"]["arguments"]}}
                             for tc in tool_calls]}]
    after.append({"role": "tool", "tool_call_id": "pending", "content": ""})  # placeholder

    return (tool_calls, before, after, system, reasoning)


def get_final_response(agent, messages: list, system_prompt: str = ""):
    """第三轮：工具结果已注入 messages，发送给 AI 得到最终回复。"""
    import json as _j
    import urllib.request, urllib.error

    config = agent.config
    provider = create_provider(
        config.get("provider", ""),
        config.get("api_key", ""),
        config.get("model", ""),
        config.get("api_url", ""),
    )

    body = _j.dumps({"model": provider.model, "max_tokens": 4096,
                      "messages": messages}).encode("utf-8")
    req = urllib.request.Request(f"{provider.api_url}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {provider.api_key}",
                 "content-type": "application/json", "User-Agent": "ReWrite/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = _j.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"[错误] {e}"

    texts = [c["message"].get("content", "") for c in data.get("choices", []) if c.get("message")]
    result = "\n".join(texts).strip()

    # 保存到历史
    agent.history.append({"role": "assistant", "content": result})
    agent._persist()
    return result


def create_provider(provider_type, api_key, model="", api_url=""):
    if provider_type == "claude":
        return ClaudeProvider(api_key, model or "claude-sonnet-4-6", api_url or "https://api.anthropic.com")
    elif provider_type == "openai":
        return OpenAIProvider(api_key, model or "gpt-4o", api_url or "https://api.openai.com/v1")
    elif provider_type == "deepseek":
        return OpenAIProvider(api_key, model or "deepseek-v4-flash", api_url or "https://api.deepseek.com")
    else:
        return OpenAIProvider(api_key, model or "unknown", api_url or "")
