"""AI Agent — 对话历史持久化，跨会话记忆。"""

from .providers import create_provider
from .prompt_templates import DEFAULT_SYSTEM_PROMPT
from src.settings.ai_config import load_chat_history, save_chat_history


class AIAgent:
    """AI 助手核心逻辑。记忆像聊天一样持久——关了再开还记得。"""

    def __init__(self, config: dict, work_name: str = ""):
        self.config = config
        self.work_name = work_name
        self._provider = None
        self.history: list[dict] = []

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

    def _persist(self):
        """保存当前历史到磁盘。"""
        if self.work_name:
            save_chat_history(self.work_name, self.history)

    def send_message(self, user_message: str,
                     current_context: str = "",
                     on_stream: callable = None,
                     enable_tools: bool = False) -> str:
        if not self.is_configured():
            return "[提示] 请先在设置中配置 AI API Key"

        provider = self._get_provider()

        system = self.config.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT
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

        if len(self.history) > 80:
            keep = self.history[-30:]
            older = self.history[:-30]
            summary_parts = []
            for msg in older:
                role = "用户" if msg["role"] == "user" else "AI"
                content = msg["content"][:200]
                summary_parts.append(f"{role}: {content}")
            summary = "--- 历史对话摘要 ---\n" + "\n".join(summary_parts[-20:])
            keep.insert(0, {"role": "user", "content": summary})
            self.history = keep

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
