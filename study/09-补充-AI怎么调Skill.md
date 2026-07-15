# 补充篇：AI 是怎么调用 Skill 的？

这是学习书里最常见的问题。很多人卡在这里——「AI 不是只能返回文字吗？它怎么调函数的？」

## 1. 关键认知：AI 能返回两种格式

你熟悉的 AI 回复是这样的：

```
"抱歉，我无法查询实时天气，建议你打开天气 App 查看。"
```

这就是一段文字（`content`）。

但 AI **还**能返回另一种东西——**工具调用请求**。它不是文字，是一个结构化的 JSON：

```json
{
  "tool_calls": [{
    "function": {
      "name": "update_character",
      "arguments": "{\"name\": \"主角\", \"field\": \"age\", \"value\": \"二十岁\"}"
    }
  }]
}
```

这个请求的意思是：「我不想回复文字，我想调用 `update_character` 这个函数，参数是 `name=主角, field=age, value=二十岁` 」。

**AI 自己不会执行代码。** 它只是说"我想调这个函数"。真正执行的是你的 Python 代码。

## 2. 怎么让 AI 进入「函数调用模式」？

答案：**不是 prompt，是 API 参数。**

发给 AI 的 HTTP 请求里，有一个 `tools` 字段：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "system", "content": "你是写作助手。"},
    {"role": "user", "content": "把主角的年龄改成二十岁"}
  ],
  "tools": [                                    // ← 这就是关键！
    {
      "type": "function",
      "function": {
        "name": "update_character",              // 函数名
        "description": "修改角色字段值",          // AI 根据描述判断是否该用
        "parameters": {                          // 参数定义
          "type": "object",
          "properties": {
            "name":  {"type": "string"},
            "field": {"type": "string"},
            "value": {"type": "string"}
          }
        }
      }
    },
    ... // 其余 29 个 Skill
  ]
}
```

**当请求里有 `tools` 字段时，AI 的行为就变了：**

```
没有 tools → AI 只生成文字
有 tools   → AI 可以选择生成文字 OR 工具调用
```

## 3. AI 是怎么判断「该调哪个工具」的？

**这是训练出来的，不是代码逻辑。**

在训练阶段，模型被喂了大量的"用户说话 → 调对应函数"的数据对：

```
训练样本 1：
  输入：「今天北京天气怎么样？」
  模型有工具：[get_weather: "查询城市天气"]
  期望输出：{"tool_calls": [{"function": {"name": "get_weather", "arguments": {"city": "北京"}}}]}

训练样本 2：
  输入：「帮我写一首诗」
  模型有工具：[get_weather: "查询城市天气", write_poem: "写诗"]
  期望输出：{"content": "春风得意马蹄疾..."}

训练样本 3：
  输入：「把张三的年龄改成 25」
  模型有工具：[update_person: "修改个人信息"]
  期望输出：{"tool_calls": [{"function": {"name": "update_person", "arguments": {"name": "张三", "field": "age", "value": "25"}}}]}
```

成千上万次训练后，模型学会了：

- 用户的意图和某个工具的 `description` 匹配 → 输出 `tool_calls`
- 用户的意图不匹配任何工具 → 输出 `content` 文字

**这不是代码里的 `if user_said("天气") then call get_weather()`。** 没有这样的代码。是模型内部通过概率计算自己决定的。

## 4. 在 ReWrite 中的实际代码

打开 `providers.py`：

```python
def get_proposals_only(agent, message, context):
    # 1. 获取所有 30 个 Skill 的定义
    tools = get_openai_tools()

    # 2. 组装请求（关键：tools 参数）
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "tools": tools          # ← 传入工具列表，告诉模型「你可以用函数调用」
    }

    # 3. 调 API
    response = requests.post(api_url, json=body)

    # 4. 判断 API 返回的是什么
    msg = response["choices"][0]["message"]

    if msg.get("tool_calls"):
        # AI 选择了工具调用
        return msg["tool_calls"]   # → 传给确认气泡
    else:
        # AI 选择了文字回复
        return msg["content"]      # → 直接显示在聊天框
```

**这段代码没有一行是"判断用户想干什么"的。** 它只是把 `tools` 发给 API，然后接收结果。判断工作全部由 AI 模型内部完成。

## 5. 打个比方

```
没有 tools 的 AI 像一个作家：
  你说话 → 他写文章回复你

有 tools 的 AI 像一个带遥控器的助理：
  你说「开空调」 → 他判断：这不是聊天，应该按遥控器 → 他按了「制冷 26°C」
  你说「今天心情怎么样」 → 他判断：这是聊天 → 他回答「还不错，谢谢关心」

判断能力不是规则写出来的，是训练出来的。
就像你学会「听到门铃去开门」，不需要有人告诉你 if 门铃响了 then 开门。
```

## 6. 不支持 function calling 的模型怎么办？

早期 ReWrite 就是这么做的——用 **prompt 约定格式**：

```
如果你需要调用工具，请用以下格式回复：
[TOOL:update_character]{"name":"主角","field":"age","value":"二十岁"}[/TOOL]
```

然后代码用正则表达式提取工具名和参数。

但这种方式不稳定——AI 可能写错格式、漏掉括号、或者干脆不按约定写。原生 function calling 输出的是严格的 JSON 结构，不会出错。

## 7. 完整数据流

```
你：「把主角的年龄改成二十岁」
     │
     ▼
发送给 API：
  + 用户消息："把主角的年龄改成二十岁"
  + 系统提示词："你是写作助手，你有以下工具..."
  + tools: [update_character: "修改角色字段值", ...]    ← 30 个 Skill 定义
     │
     ▼
AI 内部（概率计算）：
  「用户说'改'，update_character 的 description 说'修改角色'」
  「匹配度很高 → 应该用 tool_call」
  「name=主角, field=age, value=二十岁」
     │
     ▼
API 返回：
  {
    "tool_calls": [{
      "function": {"name": "update_character", "arguments": "{...}"}
    }]
  }
     │
     ▼
ReWrite 收到 → 判断 tool_calls 不为空 → 走函数调用路径
  → registry.get_skill("update_character") → 找到 Skill 实例
  → 弹确认框
  → 用户确认
  → skill.execute(args) → 代码真正执行
```

## 8. 小结

| 问题 | 答案 |
|------|------|
| AI 怎么知道要调函数？ | `tools` 参数告诉 API ，模型内部训练学会判断 |
| 这个判断是代码写的吗？ | 不是，是训练出来的 |
| 代码做了什么？ | 把 tools 发给 API，接住返回的 tool_calls，执行对应的 Skill |
| prompt 有告诉 AI 要调工具吗？ | 有辅助作用（规则里写了），但**主要**靠 tools 参数 |
