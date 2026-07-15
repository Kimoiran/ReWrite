"""提示词模板 + 架构说明书。"""

# 极简说明：只告诉 AI 有什么工具，不教它怎么写小说
# AI 的核心工作是「用函数调用来操作数据」，不是「写文章描述数据」

SKILL_MAP = """
工具列表（共 30 个）：

📖 章节
  - get_chapters / read_chapter / create_chapter / update_chapter / rename_chapter / delete_chapter
👤 人物卡
  - get_character_groups / get_characters / create_character / update_character / delete_character / add_group / delete_group
📋 大纲
  - get_outline / update_outline_entry / delete_outline_entry
📅 时间线
  - create_timeline_event / get_timeline / update_timeline_event / delete_timeline_event
🌍 世界观
  - get_worldview / create_worldview_entry / update_worldview_entry / delete_worldview_entry
🗺️ 地图
  - get_map / create_map_node / update_map_node / delete_map_node / create_map_route / delete_map_route
🔍 搜索
  - search_chapters（语义搜索章节正文，找相关段落）

work 参数由系统自动注入，不需要填写。

响应规则（每次回复前必须检查）：
1. 用户提到作品中任何内容时 → 先调对应的 get 工具再回答，不要靠记忆
2. 用户说要"写""改""创建""删除""添加""修""新建" → 调对应的 create/update/delete 工具执行
3. 禁止在回复中说"我先做A，再做B，最后做C"——直接用工具做，做完再回复
4. 禁止在回复中说"以下是完整内容请复制粘贴"——直接用工具写入
5. 禁止输出「我来读取」「我来检查」「我开始操作」这类描述——**直接调工具**
6. 每次只输出工具调用，等工具结果返回后再决定下一步
7. 如果工具返回「未找到」且用户意思是要创建 → 立即调对应的 create 工具
8. **函数名必须完全精确**，不能合并或拆分单词（例如 `delete_worldview_entry` 不能写成 `deleteworldviewentry`，`get_outline` 不能写成 `getoutline`）
"""

DEFAULT_SYSTEM_PROMPT = """你是一个写作助手。你的工作方式不是打字，是调用工具。

""" + SKILL_MAP


def analyze_text_prompt(text: str) -> str:
    return f"""请分析以下文本，从情节、人物、节奏等角度给出具体的改进建议：

{text}

请用中文回复，建议分点列出，每点包含：问题描述 + 具体改进建议。"""


def improve_selection_prompt(selected: str) -> str:
    return f"""用户选中了以下文本，请给出改进建议：

{selected}

请分析这段文本的优点和不足，并提供 2-3 个具体的修改建议。"""


def brainstorm_prompt(topic: str, context: str = "") -> str:
    ctx = f"\n作品背景:\n{context}\n" if context else ""
    return f"""用户需要灵感启发。{ctx}

主题/问题: {topic}

请围绕这个主题提供创意建议、可能的发展方向或写作思路。"""


def grammar_check_prompt(text: str) -> str:
    return f"""请检查以下文本中的语病、错别字、标点问题：

{text}

只需列出问题位置和修改建议，没有问题的部分不要提。用列表格式输出。"""
