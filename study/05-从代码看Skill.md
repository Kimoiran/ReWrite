# 第五课：从代码看 Skill（实战阅读）

这一课我们打开真实的代码文件，逐行看懂一个 Skill 是怎么写出来的、怎么注册的、怎么被调用的。

## 5.1 Skill 的基类

所有 Skill 都继承自同一个基类。先看基类的定义：

**位置：`skills/base_skill.py`**

```python
from abc import ABC, abstractmethod

class Skill(ABC):
    """单个可执行技能。所有 Skill 都必须继承此类。"""

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
    def execute(self, args: dict, work_name: str = "") -> dict:
        """执行技能，返回结果。"""
        ...

    def summarize(self, result: dict, args: dict = None) -> str:
        """将执行结果转为自然语言描述。子类可以覆盖。"""
        if result.get("success"):
            return f"已执行 {self.name}"
        return f"失败: {result.get('error', '未知错误')}"

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
```

**关键点解释：**

| 代码 | 含义 |
|------|------|
| `class Skill(ABC)` | 抽象基类，不能直接实例化，必须继承 |
| `@abstractmethod` | 子类**必须**实现这个方法，少一个就报错 |
| `property` | 这不是方法，是属性——`skill.name` 而不是 `skill.name()` |
| `summarize` | 不是抽象的（没有 `@abstractmethod`），子类可以不覆盖 |
| `to_openai_tool` | 自动将 Skill 转为 API 需要的格式，子类不需要关心 |

## 5.2 实战：阅读一个真实的 Skill

**位置：`skills/character_skills.py` — `GetCharactersSkill`**

```python
class GetCharactersSkill(Skill):
    # —— 名字 ——
    @property
    def name(self) -> str:
        return "get_characters"

    # —— 描述 ——
    @property
    def description(self) -> str:
        return "获取人物设定卡（可指定分组过滤）"

    # —— 参数定义 ——
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "description": "（可选）分组名称，仅返回该分组下的角色",
                },
            },
            "required": [],  # ← 空数组表示所有参数可选
        }

    # —— 执行逻辑 ——
    def execute(self, args, work_name=""):
        # 1. 读取 JSON 文件
        data = _load(_work_path(args.get("work", work_name)) / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []

        # 2. 如果指定了分组，过滤
        group = args.get("group", "").strip()
        if group:
            parent = _find_group(nodes, group)
            if parent:
                return {"nodes": parent.get("children", []), "group": group}

        # 3. 返回全部数据
        return {"nodes": nodes}

    # —— 结果转文字 ——
    def summarize(self, result, args=None):
        g = args.get("group", "") if args else ""
        if g:
            return f"已读取分组「{g}」的角色"
        return "已读取人物设定卡"
```

### 逐行解读

**name 属性：**

```python
name = "get_characters"
```

这是 AI 调用这个 Skill 的名字。AI 会输出类似 `{function: {name: "get_characters"}}` 来请求执行这个工具。

**input_schema 属性：**

```python
input_schema = {
    "properties": {
        "group": {
            "type": "string",
            "description": "分组名称",
        },
    },
    "required": [],  # group 是可选的
}
```

这里定义了一个可选参数 `group`。AI 可以选择传或者不传。

- 如果用户说「给我看看水神组有哪些角色」→ AI 传 `group: "水神"`
- 如果用户说「把所有角色列出来」→ AI 不传 `group`

**execute 方法：**

```python
def execute(self, args, work_name=""):
    data = _load(_work_path(work_name) / "characters.json")
    nodes = data.get("nodes", [])
    
    group = args.get("group", "").strip()
    if group:
        parent = _find_group(nodes, group)
        if parent:
            return {"nodes": parent.get("children", [])}
    
    return {"nodes": nodes}
```

| 行 | 做什么 |
|---|--------|
| `_load(...)` | 读取 characters.json 文件 |
| `args.get("group")` | 获取 AI 传过来的 group 参数 |
| `_find_group(nodes, group)` | 在树形数据中找到对应分组 |
| `return {"nodes": ...}` | 返回数据给 AI |

**args.get vs args[]：**

```python
args.get("group", "")  # ✅ 安全：如果 AI 没传 group，返回空字符串
args["group"]          # ❌ 危险：如果 AI 没传 group，程序会崩溃
```

`input_schema` 中 `required` 列表里的字段用 `args["field"]`，可选的用 `args.get("field", 默认值)`。

## 5.3 实战：创建角色的 Skill

**位置：`skills/character_skills.py` — `CreateCharacterSkill`**

```python
class CreateCharacterSkill(Skill):
    @property
    def name(self) -> str: return "create_character"

    @property
    def description(self) -> str: return "创建新角色，可指定所属分组"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "group": {"type": "string", "description": "所属分组名称"},
                "age": {"type": "string", "description": "年龄"},
                # ... 更多字段
            },
            "required": ["name"],  # ← name 是必填的
        }

    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes", [])

        # 生成唯一 ID
        new_id = uuid.uuid4().hex[:12]

        # 创建角色数据
        entry = {
            "id": new_id,
            "name": args["name"],          # ← required，直接用下标
            "age": args.get("age", ""),     # ← optional，用 get
            # ...
        }

        # 如果指定了分组，放到对应分组下
        group_name = args.get("group", "")
        if group_name:
            parent = _find_group(nodes, group_name)
            if parent:
                parent.setdefault("children", []).append(entry)
            else:
                # 分组不存在，自动创建
                nodes.append({"is_group": True, "name": group_name, "children": [entry]})
        else:
            nodes.append(entry)

        # 保存到文件
        _save(work / "characters.json", {"nodes": nodes})

        return {"success": True, "id": new_id, "name": args["name"]}
```

## 5.4 实战：RAG 搜索 Skill

**位置：`skills/rag_skills.py` — `SearchChaptersSkill`**

```python
class SearchChaptersSkill(Skill):
    _engine: RAGEngine = None  # 类变量，所有实例共享同一个 RAG 引擎

    @classmethod
    def set_engine(cls, engine):
        cls._engine = engine  # 在 module.py 启动时注入引擎

    @property
    def name(self) -> str: return "search_chapters"

    @property
    def description(self) -> str:
        return "搜索章节正文内容，按语义相关性返回最匹配的段落"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "top_k": {"type": "integer", "description": "返回结果数量，默认 5"},
            },
            "required": ["query"],
        }

    def execute(self, args, work_name=""):
        engine = self._engine
        if not engine or not engine._ready:
            return {"success": False, "error": "RAG 引擎未初始化"}

        query = args.get("query", "").strip()
        results = engine.search(query, top_k=args.get("top_k", 5))
        return {"success": True, "results": results, "count": len(results)}
```

这个 Skill 和前面的最大区别是：它**不直接读写 JSON 文件**，而是调用 RAG 引擎来搜索。

## 5.5 Skill 的注册

Skill 写好后，必须告诉系统「有这个 Skill 存在」。这一步在 `skills/registry.py` 中：

```python
# 1. 导入所有 Skill 类
from .character_skills import GetCharactersSkill, CreateCharacterSkill, ...
from .rag_skills import SearchChaptersSkill

# 2. 在 get_all_skills 中实例化
def get_all_skills() -> list[Skill]:
    return [
        GetCharactersSkill(),      # ← 实例化，不是类本身
        CreateCharacterSkill(),
        # ... 全部 30 个
        SearchChaptersSkill(),
    ]
```

**注意：**
- 返回的是**实例**（`GetCharactersSkill()`）而不是类（`GetCharactersSkill`）
- 每添加一个新 Skill，都要在这里实例化
- 否则 AI 找不到这个工具

## 5.6 Skill 的执行流程

当系统需要执行 Skill 时：

```python
# registry.py
def execute_skill(name, args, work_name=""):
    # 1. 按名字查找
    skill = get_skill(name)
    if not skill:
        return {"success": False, "error": f"未知技能: {name}"}
    
    # 2. 执行
    try:
        return skill.execute(args, work_name)
    except Exception as e:
        return {"success": False, "error": str(e)}
```

查找过程：

```python
def get_skill(name):
    for s in get_all_skills():  # 遍历 30 个 Skill
        if s.name == name:      # 匹配名字
            return s            # 返回对应的 Skill 实例
    return None
```

## 5.7 Skill 的两种调用路径

### 路径 A：通过 AI（正常流程）

```
AI 输出 {function: {name: "get_characters"}}
  → registry.execute_skill("get_characters", args)
  → GetCharactersSkill.execute(args)
  → 返回结果给 AI
```

### 路径 B：直接调用（调试用）

你也可以在代码中手动执行 Skill：

```python
from skills.registry import execute_skill

result = execute_skill("get_characters", {"group": "水神"}, "我的小说")
print(result)  # {'nodes': [...]}
```

这在测试和调试时很有用。

## 5.8 小结

阅读一个 Skill 的要点：

1. **看 name** → 知道这个工具叫什么
2. **看 description** → 知道 AI 在什么情况下会用它
3. **看 input_schema** → 知道需要传什么参数、哪些是必填
4. **看 execute** → 知道实际做了什么操作
5. **看 summarize** → 知道执行结果会怎么告诉 AI

所有的 Skill 都遵循这个模式。读懂了其中一个，就读懂了全部 30 个。

**核心文件：**
- `skills/base_skill.py` — 基类定义
- `skills/xxx_skills.py` — 具体 Skill 实现
- `skills/registry.py` — Skill 注册 + 查找 + 执行
- `skills/_shared.py` — 共享工具函数（读写文件等）
