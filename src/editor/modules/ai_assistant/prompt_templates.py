"""提示词模板 + 架构说明书。"""

# 极简说明：只告诉 AI 有什么工具，不教它怎么写小说
# AI 的核心工作是「用函数调用来操作数据」，不是「写文章描述数据」

_WORKFLOW = """工作流程（每次处理用户请求时遵循）：

步骤 1 — 收集信息
用户请求涉及作品内容时，必须先调对应的 get 工具确认目标存在。不要靠记忆。
如需改多个模块，先把所有相关数据都读出来。

步骤 2 — 执行修改
逐个调 create/update/delete 工具。每次调一个，等结果确认成功后再调下一个。
批量修改时，先改一个验证成功，再改其余的。

步骤 3 — 验证
改完后用 get 工具再读一次，确认修改已生效。确认无误后再回复用户。

铁律：
- 只能使用工具列表里列出的工具。列表里没有的功能 = 本作品未启用该模块，
  禁止调用、禁止承诺、禁止假装能改
- 禁止说「我先做A再做B」→ 直接调工具
- 禁止说「以下是完整内容」→ 用工具写入
- 禁止在没有调工具时说「✅已完成」「已修改」→ 没调工具 = 没做事
- 用户要求「写/续写/重写/修改正文」→ 必须调用 update_chapter，把完整正文放进 content 参数；
  聊天回复只放 1-2 句简短说明，禁止把大段正文直接贴在聊天里
- 用户指定了字数或篇幅（如「5000 字」）→ 这是一条贯穿整个任务的全局规则：
  开工就按该体量铺开场景/细节/对话，不要先写一小段再回头补
- 允许约 ±1000 字的自然浮动，不必为凑数注水；也不要在过程中反复核算字数
- 连续写多章时各章体量保持一致：不要第一章写足、后面越写越短
- 用户要求「写/续写/重写章节全文」而章节不存在 → 先 create_chapter 再 update_chapter
- 用户要求创建人物/设定/事件 → 必须用对应的 create_ 工具，回复里同样只放说明
- 章节名不必逐字照抄：「第一章」「第1章」「第1章 在孤儿院的日子」都能匹配到同一章
- 函数名必须完全精确，不能合并单词
- 工具返回 existing_chapters 时，用里面的真实章节名重新调用；
  不要改用 search_chapters 之类的手段去「找回」正文
- 如果提示词与上下文数据冲突，以工具返回的实际数据为准
- 不要只依赖系统提示词中的示例——以工具返回的真实数据为准
- 工具调用是验证数据准确性的唯一手段，不要猜测或编造
"""


def build_skill_map(modules=None) -> str:
    """按作品实际启用的模块生成工具清单。

    ``modules=None`` 时列出全部工具（未提供作品信息时的兜底）。
    """
    from .skills.registry import (MODULE_LABELS, get_all_skills,
                                  allowed_modules, skill_module)

    grouped: dict[str, list[str]] = {}
    for skill in get_all_skills():
        mod = skill_module(skill.name) or "other"
        grouped.setdefault(mod, []).append(skill.name)

    if modules is not None:
        allowed = allowed_modules(modules)
        grouped = {m: names for m, names in grouped.items() if m in allowed}

    total = sum(len(v) for v in grouped.values())
    lines = [
        f"工具列表（共 {total} 个；只能用这些，未列出的功能本作品未启用）：",
        "",
    ]
    for mod, label in MODULE_LABELS.items():
        names = grouped.get(mod)
        if names:
            lines.append(label)
            lines.append("  - " + " / ".join(names))
    lines.append("")
    lines.append("work 参数由系统自动注入。")
    return "\n".join(lines)


def build_tool_law(modules=None) -> str:
    """完整工具铁律（工具清单 + 工作流程）。"""
    return f"{build_skill_map(modules)}\n\n{_WORKFLOW}"


# ─────────────────────────────────────────────────────────────
# 篇幅要求 → 全局规则
#
# 用户明确说了字数（如「每章 5000 字」）时，这条要求**必须**进入系统提示词，
# 而不是只躺在对话历史里。原因：历史会被 history[-40:] 截断、被记忆压缩摘要、
# 上下文过长时还可能被服务端从头裁掉——一旦被裁，AI 就"忘了要写多长"，
# 表现为越写越少。系统提示词每次请求都在，且位于最前，最不容易被丢。
# ─────────────────────────────────────────────────────────────

_RANGE_RE = r"(\d{2,6})\s*[-~～到至]\s*(\d{2,6})\s*字"
_CHAPTER_RE = r"每章\s*(\d{2,6})\s*字"
_PLAIN_RE = r"(\d{2,6})\s*字"
_EN_RE = r"(\d{2,6})\s*(?:words|word)\b"


def extract_length_rule(text: str) -> str:
    """从用户消息里提取篇幅要求，返回一句可直接注入提示词的规则。

    没提到字数时返回空串（调用方据此保留上一条规则或不注入）。
    """
    import re
    t = (text or "").strip()
    if not t:
        return ""

    m = re.search(_RANGE_RE, t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return f"篇幅区间：约 {lo}–{hi} 字（落在这个区间内即可）"

    m = re.search(_CHAPTER_RE, t)
    if m:
        n = int(m.group(1))
        return f"每一章目标篇幅：约 {n} 字（允许 ±1000 字自然浮动）"

    m = re.search(_PLAIN_RE, t) or re.search(_EN_RE, t, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return f"目标篇幅：约 {n} 字（允许 ±1000 字自然浮动）"

    return ""


def build_length_block(length_rule: str) -> str:
    """把篇幅要求包装成「全局规则」段落。未提供时返回空串。"""
    rule = (length_rule or "").strip()
    if not rule:
        return ""
    return (
        "## 本次写作任务的篇幅要求（全局规则，贯穿整个任务）\n"
        f"- {rule}\n"
        "- 这是一条**开工前就已确定**的硬指标：动笔时就按这个体量铺开场景、细节与对话，"
        "而不是先写一小段再回头补。\n"
        "- 不需要在写作过程中反复核算字数，也不要为凑数注水、重复啰嗦或堆砌形容词；\n"
        "  一次就写到目标体量附近，然后自然收尾。\n"
        "- 连续写多章时，上面的篇幅要求对**每一章**都成立，"
        "不要第一章写足、后面越写越短。\n"
        "- 例外：如果用户当次明确要求「简短」「只要一段」「先给个提纲」，"
        "以当次要求为准。"
    )


# 兜底常量：不限定模块时的完整铁律（供文档/测试引用）
SKILL_MAP = build_tool_law(None)
TOOL_LAW = SKILL_MAP

DEFAULT_SYSTEM_PROMPT = ("你是 ReWrite 写作助手。你必须通过工具调用来操作数据，"
                         "而不是通过打字描述操作。\n\n" + SKILL_MAP)


def build_system_prompt(config: dict, modules=None, length_rule: str = "") -> str:
    """统一的系统提示词构建(唯一入口):

    - 工具铁律为硬编码,始终置于最前,不可被任何自定义覆盖;
    - 工具清单按作品启用的模块收窄(modules),关掉的模块不会出现在清单里;
    - 用户明确指定的篇幅要求(length_rule)以「全局规则」形式紧随铁律注入,
      每条请求都会带上,因此不会因对话历史被截断/压缩而失效;
    - 设置里的自定义提示词追加在其后;
    - 留空时使用内置默认提示词(已含铁律)。
    """
    custom = (config.get("system_prompt") or "").strip()
    law = build_tool_law(modules)
    length_block = build_length_block(length_rule)
    if length_block:
        law = f"{law}\n\n{length_block}"
    identity = ("你是 ReWrite 写作助手。你必须通过工具调用来操作数据，"
                "而不是通过打字描述操作。")
    if custom:
        return f"{law}\n\n你是 ReWrite 写作助手。\n{custom}"
    return f"{identity}\n\n{law}"



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
