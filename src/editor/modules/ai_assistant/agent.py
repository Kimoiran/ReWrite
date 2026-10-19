"""AI Agent — 对话历史持久化，跨会话记忆。"""

from .providers import create_provider
from .prompt_templates import build_system_prompt
from src.settings.ai_config import load_chat_history, save_chat_history


class AIAgent:
    """AI 助手核心逻辑。记忆像聊天一样持久——关了再开还记得。"""

    def __init__(self, config: dict, work_name: str = ""):
        self.config = config
        self.work_name = work_name
        self._provider = None
        self.history: list[dict] = []
        # 本作品启用的模块集合（由 AIAssistantModule 按 work.json 注入）。
        # None = 不做限制（全局/测试场景）。
        self.enabled_modules = None

        # 加载历史记忆
        if work_name:
            saved = load_chat_history(work_name)
            if saved:
                self.history = saved

    def _get_provider(self):
        if self._provider is None:
            self._provider = create_provider(
                provider_type=self.config.get("provider", "claude"),
                api_key=self.config.get("api_key", ""),
                model=self.config.get("model", ""),
                api_url=self.config.get("api_url", ""),
            )
        return self._provider

    def is_configured(self) -> bool:
        return bool(self.config.get("api_key"))

    @property
    def provider_name(self) -> str:
        return self.config.get("provider", "未配置")

    @property
    def model_name(self) -> str:
        return self.config.get("model", "")

    def _compress(self):
        """压缩过长的历史记忆（保留最近 30 条，旧消息合并为摘要）。

        两个关键规则：

        1. **摘要前剥离思考过程**——推理常常比正文还长，混进摘要会把真正的
           信息挤掉，让「记忆」越压越糊涂。
        2. **保留最早的那条用户消息**（任务原点：字数/篇幅/风格要求），
           否则连续写很多章之后，「每章 5000 字」会被摘要吞掉。
        """
        if len(self.history) <= 80:
            return
        from .providers import strip_reasoning

        keep = self.history[-30:]
        older = self.history[:-30]

        summary_parts = []
        for msg in older:
            role = "用户" if msg.get("role") == "user" else "AI"
            c = msg.get("content", "")
            if isinstance(c, list):
                c = " ".join(str(x) for x in c[:5])
            c = strip_reasoning(str(c)).strip()
            if not c:
                continue                      # 纯思考过程的消息不进摘要
            summary_parts.append(f"{role}: {c[:200]}")

        summary = {"role": "user",
                   "content": "--- 历史对话摘要 ---\n" + "\n".join(summary_parts[-20:])}

        # 任务原点：最早的一条真实用户指令（排除上一轮的摘要块）
        origin = next(
            (m for m in older
             if m.get("role") == "user"
             and not str(m.get("content", "")).startswith("--- 历史对话摘要 ---")
             and strip_reasoning(str(m.get("content", ""))).strip()),
            None,
        )

        new_history = [summary]
        if origin is not None:
            new_history.append({
                "role": "user",
                "content": "（本次任务最开始的原始要求，长期有效）\n"
                           + strip_reasoning(str(origin["content"]))[:600],
            })
        self.history = new_history + keep

    def _persist(self):
        """保存当前历史到磁盘（自动触发压缩）。"""
        self._compress()
        if self.work_name:
            save_chat_history(self.work_name, self.history)

    def send_message(self, user_message: str,
                     current_context: str = "",
                     on_stream: callable = None,
                     enable_tools: bool = False) -> str:
        if not self.is_configured():
            return "[提示] 请先在设置中配置 AI API Key"

        provider = self._get_provider()

        # 工具铁律为硬编码(见 build_system_prompt),自定义提示词只能追加其后
        system = build_system_prompt(self.config, self.enabled_modules)
        if current_context:
            system = f"{system}\n\n## 当前作品上下文\n{current_context}"

        self.history.append({"role": "user", "content": user_message})

        recent = self.history[-40:] if len(self.history) > 40 else self.history

        if enable_tools and hasattr(provider, "send_with_tools"):
            # 工具调用：不污染对话历史
            response = provider.send_with_tools(
                messages=recent,
                system_prompt=system,
                on_stream=on_stream,
            )
        else:
            response = provider.send_message(
                messages=recent,
                system_prompt=system,
                on_stream=on_stream,
            )

        self.history.append({"role": "assistant", "content": response})
        self._persist()
        return response

    def undo_last_message(self) -> bool:
        """撤回最后一条消息（用户+AI 一对），返回是否成功。"""
        if len(self.history) < 2:
            return False
        self.history = self.history[:-2]  # 去掉最后 user + assistant
        self._persist()
        return True

    def clear_history(self):
        """清空记忆并删除磁盘文件。"""
        self.history = []
        self._persist()

    def set_config(self, config: dict):
        self.config.update(config)
        self._provider = None
