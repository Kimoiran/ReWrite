# 第二课：什么是 Skill 系统？

## 2.1 开场白：AI 没有"手"

上节课我们说过：AI 大模型只是一个文字生成器。它不识字、不读文件、不写磁盘——它只会**生成看起来合理的文字**。

要让 AI 真正"做事"，我们需要给它配一套**工具**。这套工具在 ReWrite 中叫做 **Skill（技能）**。

```
AI（大脑）：
「我想修改主角的年龄」
     │
     │ 但是我没有手，我做不到
     │
     ▼
Skill（工具）：
「我来帮你做」
     │
     ├─ Step 1: 读取 characters.json
     ├─ Step 2: 找到 name="主角" 的节点
     ├─ Step 3: 把 age 改成 "二十岁"
     └─ Step 4: 保存文件
```

## 2.2 一个 Skill 长什么样

每个 Skill 就是一个 Python 类。我们来看一个最简单的 Skill：

```python
class GetCharactersSkill(Skill):
    # 1. 名字：AI 根据这个名字来调用
    name = "get_characters"

    # 2. 描述：告诉 AI 这个工具是做什么的
    description = "获取人物设定卡（可指定分组过滤）"

    # 3. 参数：告诉 AI 需要传什么信息
    input_schema = {
        "type": "object",
        "properties": {
            "group": {
                "type": "string",
                "description": "分组名称，不填则返回所有角色",
            },
        },
    }

    # 4. 执行：实际的代码逻辑
    def execute(self, args, work_name=""):
        # args 是 AI 传过来的参数（比如 group="自然之力"）
        # work_name 是当前作品的名称
        data = _load(_work_path(work_name) / "characters.json")
        # ... 读取并返回数据
        return {"nodes": nodes}
```

每个 Skill 必须有这 4 个部分，缺一不可。

## 2.3 Skill 的三要素详解

### 第一要素：name（名字）

名字是 AI 调用 Skill 的唯一标识。

```python
name = "update_character"
```

- 必须是英文小写 + 下划线（蛇形命名法）
- 必须唯一（不能有同名 Skill）
- AI 在生成工具调用时就是用这个名字

当 AI 决定「要修改角色数据」时，它会输出：

```json
{
  "function": {
    "name": "update_character",
    "arguments": "{...}"
  }
}
```

系统收到这个请求，在 `registry.py` 中找到名字为 `update_character` 的 Skill，执行它。

### 第二要素：description（描述）

描述是给 AI 看的说明书。AI 根据描述来判断「这个工具适不适合当前任务」。

```python
description = "修改角色字段值"
```

描述要**准确且简洁**。不够准确的描述会让 AI 用错工具：

| 描述 | 问题 |
|------|------|
| "修改角色字段值" | ✅ 准确 |
| "处理角色数据" | ❌ 太模糊，AI 不知道该不该用 |
| "修改角色字段值，比如年龄、性格、背景等" | ✅ 清晰 |

### 第三要素：input_schema（参数定义）

参数定义使用 JSON Schema 格式，告诉 AI 需要传什么参数、每个参数是什么类型。

```python
input_schema = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "角色名称",
        },
        "field": {
            "type": "string",
            "description": "要修改的字段名",
        },
        "value": {
            "type": "string",
            "description": "新的值",
        },
    },
    "required": ["name", "field", "value"],
}
```

这里定义了三个参数：
- `name`：角色名（必填）
- `field`：要改的字段（必填）
- `value`：新值（必填）

`required` 数组告诉 AI 哪些参数是必须传的。不在 `required` 中的参数是可选的。

## 2.4 Skill 的执行流程

当 AI 决定调一个 Skill 时，完整的执行链路是：

```
AI 输出工具调用
    │  {function: {name: "update_character", arguments: "..."}}
    ▼
registry.py -> get_skill("update_character")
    │  按名字找到对应的 Skill 类
    ▼
skill.execute(args, work_name)
    │  执行实际代码
    │  （读文件 → 改数据 → 保存）
    ▼
返回结果给 AI
    │  {success: True, old: "...", new: "..."}
    ▼
summarize(result, args)
    │  把结果转为自然语言
    ▼
AI 看到结果，决定下一步
```

## 2.5 完整的 Skill 生命周期

以修改主角的年龄为例：

```
        用户说：「把主角的年龄改成二十岁」
                      │
                      ▼
         AI 决定调 update_character
         name="主角", field="age", value="二十岁"
                      │
                      ▼
            ┌─────────────────────┐
            │  弹出确认气泡        │
            │  「将主角的 age      │
            │   修改为二十岁」      │
            │  [取消]  [允许]      │
            └─────────────────────┘
                      │ 用户点了「允许」
                      ▼
            ┌─────────────────────┐
            │  1. 读 characters.json│
            │  2. 找到「主角」      │
            │  3. 改 age="二十岁"  │
            │  4. 保存文件          │
            └─────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │  summarize:         │
            │  ✅ 已将「主角」     │
            │  的「age」修改为     │
            │  「二十岁」          │
            └─────────────────────┘
                      │
                      ▼
          AI 回复用户（你看到的消息）
```

## 2.6 30 个 Skill 的分类

ReWrite 目前有 30 个 Skill，分为 7 类：

| 模块 | Skill 数量 | 功能 |
|------|-----------|------|
| 📖 章节 | 6 个 | 增删改查重命名章节文件 |
| 👤 人物卡 | 7 个 | 管理角色和分组 |
| 📋 大纲 | 3 个 | 管理大纲条目 |
| 📅 时间线 | 4 个 | 管理时间线事件 |
| 🌍 世界观 | 4 个 | 管理世界设定 |
| 🗺️ 地图 | 6 个 | 管理地图节点和路线 |
| 🔍 搜索 | 1 个 | 语义搜索章节正文（RAG） |

### RAG 搜索 Skill

这是最新加入的 Skill，它有点特殊——它不是直接读写数据文件，而是**搜索**：

```python
class SearchChaptersSkill(Skill):
    name = "search_chapters"
    description = "搜索章节正文内容，按语义相关性返回最匹配的段落"
    
    def execute(self, args):
        query = args["query"]  # 用户的问题
        # 用 TF-IDF 算法计算每段文字和问题的相似度
        results = self._engine.search(query)
        return {"results": results}
```

这个 Skill 的背后是**RAG 引擎**（我们在第八课会详细讲）。简单说，它能把所有章节的正文切成段落，然后根据你的问题找到最相关的段落——就像 Google 搜索一样。

## 2.7 Skill vs 普通函数的区别

如果你会写 Python，你可能会问：「这不就是普通函数吗？」

没错，Skill **本质上就是一个函数**。但有几个关键区别：

| 特性 | 普通函数 | Skill |
|------|---------|-------|
| 谁来调 | 程序员在代码中调 | **AI** 根据意图决定 |
| 参数怎么传 | 程序员传 | AI 根据描述生成 |
| 返回值给谁 | 给调用代码 | 给 AI 继续处理 |
| 需要注册 | 不需要 | 必须在 registry.py 注册 |

简单说：**普通函数是程序员用的，Skill 是 AI 用的。**

## 2.8 小结

- **Skill** = 一个 Python 类，包含 name + description + input_schema + execute
- AI 通过 name 来调用 Skill
- description 告诉 AI 这个 Skill 是做什么的
- input_schema 告诉 AI 需要传什么参数
- 所有 Skill 在 `registry.py` 中注册
- 执行前弹出确认框确保用户可控
- 目前有 30 个 Skill，覆盖 7 个模块

下一课我们学习：AI 怎么知道自己有哪些 Skill 可用？——提示词（Prompt）。
