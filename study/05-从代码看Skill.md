# 第五课：从代码看 Skill（实战阅读）

这一课我们打开真实的代码文件，逐行看懂一个 Skill 是怎么写出来的、怎么找到文件的、怎么读写数据的。

## 5.0 先导：代码是怎么操作文件的？

在看 Skill 代码之前，你必须先理解一个基本概念：**Python 代码可以像你手动打开文件一样，读取和修改电脑上的任何文件。**

### 一个最简单的例子

在 Windows 上，你可以用记事本打开 `C:\test.txt`，看到里面的文字，修改它，然后保存。Python 代码可以**完全自动地**做同样的事：

```python
# 打开一个文件并读取里面的所有文字
with open("C:\\test.txt", "r", encoding="utf-8") as f:
    content = f.read()          # 把文件内容读到 content 变量里
    print(content)              # 打印出来看看

# 修改内容并重新写入文件
new_content = content + "\n这是新加的一行"
with open("C:\\test.txt", "w", encoding="utf-8") as f:
    f.write(new_content)        # 覆盖写入
```

这就是**文件 I/O（Input/Output，输入/输出）**——代码读写文件的能力。Skill 系统能修改你的作品数据，本质上就是靠这个。

### JSON：作品数据的存储格式

ReWrite 中大部分数据用 **JSON** 格式存储。JSON 看起来像这样：

```json
{
  "nodes": [
    {
      "id": "abc123",
      "name": "主角",
      "age": "二十岁",
      "occupation": "铁匠"
    }
  ]
}
```

JSON 本质上是**结构化的文本**。Python 可以把它读进来变成字典（`dict`），修改字典，再写回文件：

```python
import json

# 1. 读：JSON 文字 → Python 字典
text = Path("characters.json").read_text(encoding="utf-8")   # 读文件文字
data = json.loads(text)                                       # 把文字转成字典

# 2. 改：修改字典中的数据
data["nodes"][0]["age"] = "二十五岁"                         # 和改普通 Python 变量一样

# 3. 写：Python 字典 → JSON 文字 → 文件
new_text = json.dumps(data, ensure_ascii=False, indent=2)    # 字典转回 JSON 文字
Path("characters.json").write_text(new_text, encoding="utf-8") # 写入文件
```

**这就是 Skill 修改数据的全部秘密。** 不复杂，对吧？就是三个步骤：**读→改→写**。

### `execute` 是什么？

`execute` 是英语"执行"的意思。在这个项目中，它就是一个**方法**（函数），当 AI 决定要调用这个 Skill 时，系统会运行这个函数。

```python
def execute(self, args, work_name=""):
    # args:   AI 传过来的参数，比如 {"name": "主角", "field": "age", "value": "二十岁"}
    # work_name: 当前作品的名字，比如 "我的小说"
  
    # 在这里面做：读文件 → 改数据 → 写文件 → 返回结果
    ...
    return {"success": True}
```

你可以把 `execute` 理解为：**「这个工具被调用时要执行的实际代码」**。

### `args` 里面的数据从哪来？

`args` 是 AI 生成的。当用户说「把主角的年龄改成二十岁」，AI 会生成这样一个结构：

```json
{
  "name": "主角",
  "field": "age",
  "value": "二十岁"
}
```

这个 JSON 被解析成 Python 字典，就是 `args`。所以在 `execute` 里你可以写：

```python
name = args["name"]    # → "主角"
field = args["field"]  # → "age"  
value = args["value"]  # → "二十岁"
```

**完整的链路：** 你说的话 → AI 理解 → AI 生成 JSON 参数 → 系统传给 `execute(args)` → 代码运行。

### 代码怎么找到你的文件？

所有的作品文件都在 `works/` 目录下。每个作品是一个文件夹：

```
works/
├── 我的小说/
│   ├── work.json          ← 作品元数据
│   ├── characters.json    ← 人物卡
│   ├── chapters/
│   │   ├── 0001_第一章.html
│   │   └── 0002_第二章.html
│   ├── outline.json       ← 大纲
│   ├── timeline.json      ← 时间线
│   ├── worldview.json     ← 世界观
│   └── map.json           ← 地图
```

代码通过**拼接路径**来定位文件。在 `_shared.py` 中有几个工具函数：

```python
def _work_path(name):
    """根据作品名找到对应的文件夹路径。
    例如：name="我的小说" → Path("works/我的小说")"""
    ...

def _load(path):
    """读取一个 JSON 文件，返回 Python 字典。
    例如：_load(Path("works/我的小说/characters.json")) → {"nodes": [...]}"""
    ...

def _save(path, data):
    """把一个 Python 字典保存为 JSON 文件。
    例如：_save(Path("works/我的小说/characters.json"), {"nodes": [...]})"""
    ...
```

所以在 `execute` 里，当我们写：

```python
data = _load(_work_path(work_name) / "characters.json")
```

实际上发生的是：

```
_work_path(work_name)        → Path("works/我的小说")          # 找到作品文件夹
/ "characters.json"          → Path("works/我的小说/characters.json")  # 拼接文件名
_load(...)                   → {"nodes": [...]}               # 读 JSON → 字典
```

**Path 拼接** 就是用 `/` 把路径连起来，像一个"文件地址"：

```python
from pathlib import Path

folder = Path("works/我的小说")            # 文件夹
file = folder / "characters.json"          # 拼接：works/我的小说/characters.json
```

这个概念贯穿整个 Skill 系统。所有的读、写、创建操作都遵循"先找到路径，再操作文件"的流程。

---

## 5.1 Skill 的基类

现在回头看 Skill 的基类，你应该能理解每个部分的作用了：

**位置：`skills/base_skill.py`**

```python
from abc import ABC, abstractmethod

class Skill(ABC):
    """所有 Skill 的基类。定义了 Skill 必须有的四个部分。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称。AI 通过这个名字来调用。比如 "get_characters" """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述。告诉 AI 这个工具能做什么。"""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """参数定义。JSON Schema 格式，告诉 AI 需要传什么参数。"""
        ...

    @abstractmethod
    def execute(self, args: dict, work_name: str = "") -> dict:
        """实际的代码逻辑。args 是 AI 传的参数，work_name 是作品名。
        在这个方法里做：读文件 → 改数据 → 写文件 → 返回结果。"""
        ...

    def summarize(self, result: dict, args: dict = None) -> str:
        """把 execute 返回的结果转成一句话，给 AI 和用户看。"""
        if result.get("success"):
            return f"已执行 {self.name}"
        return f"失败: {result.get('error', '未知错误')}"

    def to_openai_tool(self) -> dict:
        """把自己转成 OpenAI API 需要的工具定义格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
```

`@abstractmethod` 的意思是"子类必须实现"。如果你写了一个 Skill 但忘了写 `execute`，Python 在启动时就会报错提醒你。

---

## 5.2 实战：读数据的 Skill（只用 Load）

我们先看最简单的 Skill——**不需要改任何文件，只需要读数据**。

**位置：`skills/character_skills.py` — `GetCharactersSkill`**

```python
class GetCharactersSkill(Skill):
    @property
    def name(self) -> str: return "get_characters"

    @property
    def description(self) -> str: return "获取人物设定卡（可指定分组过滤）"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "group": {"type": "string", "description": "分组名称，不填则返回所有角色"},
            },
            "required": [],  # 空 = 所有参数都是可选的
        }

    def execute(self, args, work_name=""):
        # ======== 第 1 步：找到文件并读取 ========
        # _work_path(work_name) → Path("works/我的小说")
        # / "characters.json"   → Path("works/我的小说/characters.json")
        # _load(...)            → 读 JSON → Python 字典
        data = _load(_work_path(args.get("work", work_name)) / "characters.json")
        # data 现在是：{"nodes": [{"id":"...", "name":"主角", ...}, ...]}

        # ======== 第 2 步：从字典中取出角色列表 ========
        nodes = data.get("nodes") or data.get("characters") or []
        # data.get("nodes") → 取出 nodes 的值（角色列表）
        # or data.get("characters") → 兼容旧格式
        # or [] → 如果都没有，给一个空列表

        # ======== 第 3 步：如果 AI 传了 group 参数，过滤数据 ========
        group = args.get("group", "").strip()
        if group:
            # 在树形结构中递归查找名为 group 的分组
            parent = _find_group(nodes, group)
            if parent:
                # 找到后只返回该分组下的角色
                return {"nodes": parent.get("children", []), "group": group, "count": ...}
            # 没找到，返回空 + 警告
            return {"nodes": [], "group": group, "count": 0}

        # ======== 第 4 步：返回全部数据 ========
        return {"nodes": nodes}

    def summarize(self, result, args=None):
        g = args.get("group", "") if args else ""
        if g:
            return f"已读取分组「{g}」的角色（{result.get('count', 0)} 条）"
        return "已读取人物设定卡"
```

### 逐行解读

**第 1 步：找到文件**

```python
data = _load(_work_path(work_name) / "characters.json")
```

这是一个**链式操作**，从右往左看：

| 表达式                    | 结果                                       | 说明                            |
| ------------------------- | ------------------------------------------ | ------------------------------- |
| `work_name`             | `"我的小说"`                             | AI 传进来或系统自动注入的作品名 |
| `_work_path(work_name)` | `Path("works/我的小说")`                 | 找到作品文件夹                  |
| `/ "characters.json"`   | `Path("works/我的小说/characters.json")` | 拼接文件名                      |
| `_load(...)`            | `{"nodes": [...]}`                       | 读取文件内容，转成 Python 字典  |

`_load` 函数在 `_shared.py` 中定义：

```python
def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}
```

它的逻辑是：如果文件存在，读出来 → 用 `json.loads` 把 JSON 文字转成 Python 字典 → 返回。如果文件不存在或读失败，返回空字典 `{}`。

**第 2 步：从字典取数据**

```python
nodes = data.get("nodes") or data.get("characters") or []
```

`data` 是一个字典 `{"nodes": [...]}`。`data.get("nodes")` 取出 `nodes` 键对应的值。如果 `nodes` 不存在（某些旧文件用 `characters` 作为键名），就尝试 `characters`。都没有就返回空列表 `[]`。

**第 3 步：过滤分组**

```python
group = args.get("group", "").strip()
if group:
    parent = _find_group(nodes, group)
```

`args.get("group", "")` 从 AI 传来的参数中取出 `group`。如果 AI 没传，默认值是空字符串 `""`。`.strip()` 去除首尾空白。

如果 AI 传了 group（比如 `"主角队"`），就调用 `_find_group` 在树形结构中找到对应的分组节点。

**第 4 步：返回**

```python
return {"nodes": nodes}
```

把数据打包成字典返回。这个字典会被传给 `summarize` 转成文字，最终 AI 看到。

---

## 5.3 实战：写数据的 Skill（Load → Modify → Save）

现在看一个**需要修改数据**的 Skill。它能直接改你的文件。

**位置：`skills/character_skills.py` — `UpdateCharacterSkill`**

```python
class UpdateCharacterSkill(Skill):
    @property
    def name(self) -> str: return "update_character"

    @property
    def description(self) -> str: return "修改角色字段值"

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "角色名称"},
                "field": {"type": "string", "description": "字段名（age/gender/occupation 等）"},
                "value": {"type": "string", "description": "新值"},
            },
            "required": ["name", "field", "value"],  # ← 三个参数都是必填的
        }

    def execute(self, args, work_name=""):
        # ======== 第 1 步：读文件（和 GetCharactersSkill 一样） ========
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")
        nodes = data.get("nodes") or data.get("characters") or []

        # ======== 第 2 步：从 args 取出要改什么 ========
        name = args["name"]    # 用下标而不是 get，因为 input_schema 标明 required
        field = args["field"]
        value = args["value"]

        # ======== 第 3 步：检查字段名是否合法 ========
        valid_fields = {"name", "aliases", "age", "gender", "occupation",
                        "appearance", "personality", "background", "goals", "notes"}
        if field not in valid_fields:
            return {"success": False, "error": f"不支持字段: {field}"}

        # ======== 第 4 步：在树形结构中递归查找角色 ========
        def _find(nodes):
            for n in nodes:
                # 找到名字匹配且不是分组的节点
                if n.get("name") == name and not n.get("is_group"):
                    return n
                # 如果有子节点，递归找
                if n.get("children"):
                    f = _find(n["children"])
                    if f: return f
            return None

        node = _find(nodes)
        if not node:
            return {"success": False, "error": f"未找到角色: {name}"}

        # ======== 第 5 步：修改字段值 ========
        old = node.get(field, "")
        node[field] = value
        # 此时 node 类似于：{"name":"主角", "age": "二十岁", ...}
        # 执行 node["age"] = "二十五岁" 后，node 里的 age 就变了

        # ======== 第 6 步：写回文件 ========
        _save(work / "characters.json", {"nodes": nodes})
        # _save 在 _shared.py 中：
        #   def _save(path, data):
        #       path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # 把修改后的字典转成 JSON → 写入文件

        return {"success": True, "old": old, "new": value}

    def summarize(self, result, args=None):
        n = (args or {}).get("name", "")
        f = (args or {}).get("field", "")
        v = (args or {}).get("value", "")
        if result.get("success"):
            return f"✅ 已将「{n}」的「{f}」修改为「{v}」"
        return f"❌ 修改失败: {result.get('error')}"
```

### 重点：这个 Skill 是怎么修改你的文件的？

用一张图来表示：

```
电脑硬盘上的文件
     │
     │ _load() 读取
     ▼
┌─────────────────────┐
│ characters.json      │
│ {                    │
│   "nodes": [{        │
│     "name": "主角",   │
│     "age": "十八岁"   │
│   }]                 │
│ }                    │
└─────────┬───────────┘
          │ json.loads() 解析
          ▼
┌─────────────────────┐
│ Python 字典（内存中） │
│ data = {             │
│   "nodes": [{        │
│     "name": "主角",   │
│     "age": "十八岁"   │
│   }]                 │
│ }                    │
└─────────┬───────────┘
          │ node["age"] = "二十岁"  ← 代码修改内存中的值
          ▼
┌─────────────────────┐
│ data = {             │
│   "nodes": [{        │
│     "name": "主角",   │
│     "age": "二十岁"   │  ← 值已改变
│   }]                 │
│ }                    │
└─────────┬───────────┘
          │ _save() 写入
          ▼
┌─────────────────────┐
│ characters.json      │
│ {                    │  ← 文件内容已更新
│   "nodes": [{        │
│     "name": "主角",   │
│     "age": "二十岁"   │
│   }]                 │
│ }                    │
└─────────────────────┘
```

**关键理解：** 文件在硬盘上，Python 把它读到**内存**（RAM）里操作，改完内存后再写回硬盘。硬盘上的文件只有在你调用 `_save` 的那一刻才会发生变化。

### 递归查找：`_find` 函数怎么在树里找角色

```python
def _find(nodes):
    for n in nodes:                              # 遍历当前层级的每个节点
        if n.get("name") == name and not n.get("is_group"):
            return n                             # 找到了！返回这个节点
        if n.get("children"):                    # 如果有子节点
            f = _find(n["children"])             # 递归进去找（自己调用自己）
            if f: return f                       # 在子节点中找到了，返回
    return None                                  # 全部找完也没找到
```

假设数据结构是：

```
人物卡
├── 📁 自然之力
│   ├── 👤 主角（age: 十八岁）
│   └── 👤 女神（age: 新生）
└── 📁 知识
    ├── 👤 长者（age: 一千岁）
    └── 👤 知识神（age: 极古老）
```

当你要找 `"主角"` 时：

1. 先在第一层找：`"自然之力"` → 是分组，跳过；`"知识"` → 是分组，跳过
2. 进 `"自然之力"` 的子节点找：`"主角"` → 名字匹配，不是分组 → **找到了！**

---

## 5.4 实战：创建数据的 Skill

创建角色和修改角色的区别是：创建要**往列表里加新数据**，修改是改已有数据。

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
                "occupation": {"type": "string", "description": "职业/身份"},
                # ... 更多字段
            },
            "required": ["name"],
        }

    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")                # 读文件
        nodes = data.get("nodes") or data.get("characters") or []

        # 生成一个唯一的 12 位 ID
        import uuid
        new_id = uuid.uuid4().hex[:12]

        # 创建新角色的数据字典
        entry = {
            "id": new_id,
            "name": args["name"],             # 从 AI 参数中取
            "is_group": False,                 # False = 是角色，True = 是分组
            "age": args.get("age", ""),        # 用 get 因为可选的
            "occupation": args.get("occupation", ""),
            # ...
        }

        # 如果 AI 指定了分组，放到对应分组下
        group_name = args.get("group", "")
        if group_name:
            parent = _find_group(nodes, group_name)
            if parent:
                parent.setdefault("children", []).append(entry)  # 追加到分组里
            else:
                # 分组不存在，自动创建
                nodes.append({"is_group": True, "name": group_name, "children": [entry]})
        else:
            nodes.append(entry)  # 没指定分组，放到根级

        _save(work / "characters.json", {"nodes": nodes})  # 写回文件

        return {"success": True, "id": new_id, "name": args["name"]}
```

这里的关键是 `nodes.append(entry)`：

```python
# 创建之前
nodes = [...已有的角色...]

# append 把新角色加到列表末尾
nodes.append(entry)

# 创建之后
nodes = [...已有的角色..., 新角色]
```

---

## 5.5 实战：删除数据的 Skill

```python
class DeleteCharacterSkill(Skill):
    @property
    def name(self) -> str: return "delete_character"

    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        data = _load(work / "characters.json")                # 读
        nodes = data.get("nodes") or data.get("characters") or []

        name = args["name"]

        # 递归查找并删除
        def _delete(nodes):
            for i, n in enumerate(nodes):    # enumerate 同时给出索引和值
                if not n.get("is_group") and n.get("name") == name:
                    nodes.pop(i)              # pop(i) = 移除列表第 i 个元素
                    return True
                if n.get("children") and _delete(n["children"]):
                    return True
            return False

        if not _delete(nodes):
            return {"success": False, "error": f"未找到角色: {name}"}

        _save(work / "characters.json", {"nodes": nodes})    # 写
        return {"success": True, "name": name}
```

这里是 `nodes.pop(i)`——Python 列表的删除操作：

```python
# 删除前
nodes = ["A", "B", "C", "D"]

# 删除索引 2 的元素（即 "C"）
nodes.pop(2)

# 删除后
nodes = ["A", "B", "D"]
```

---

## 5.6 Skill 的注册

Skill 写好后，必须告诉系统「有这个 Skill 存在」。在 `skills/registry.py` 中：

```python
from .character_skills import GetCharactersSkill, CreateCharacterSkill, ...

def get_all_skills() -> list[Skill]:
    return [
        GetCharactersSkill(),      # ← 注意括号！是实例化，不是类本身
        CreateCharacterSkill(),
        UpdateCharacterSkill(),
        # ... 全部 30 个
    ]
```

**`GetCharactersSkill` 和 `GetCharactersSkill()` 的区别：**

```python
GetCharactersSkill    # 类本身（Class），只是"蓝图"
GetCharactersSkill()  # 实例（Instance），可以用的"实体"
```

就像：

```python
str      # 字符串类型（蓝图）
"hello"  # 一个具体的字符串（实例）
```

---

## 5.7 衔接回前面学的内容

现在你应该能把前面四课的知识和代码串起来了：

```
用户说「把主角的年龄改成二十岁」
     │
     ├─ 第 3 课的「提示词」让 AI 知道有 update_character 这个工具
     │
     ├─ 第 1-2 课的「Agent」决定调用 update_character
     │
     ├─ AI 生成 args = {"name": "主角", "field": "age", "value": "二十岁"}
     │
     ├─ 第 4 课的「多轮递归」在后台运行：系统执行 Skill → 返回结果 → AI 继续
     │
     └─ 本课的 Skill 代码执行：
         _load → 读文件
         _find → 找到"主角"
         node["age"] = "二十岁" → 修改内存
         _save → 写回文件
```

从你说一句话，到文件被修改，中间的每一步都有对应的代码在做具体的事。

---

## 5.8 小结

阅读一个 Skill 的要点：

1. **看 name** → 知道这个工具叫什么
2. **看 description** → 知道 AI 在什么情况下会用它
3. **看 input_schema** → 知道需要传什么参数、哪些是必填
4. **看 execute** → 知道实际做了什么操作（读→改→写）
5. **看 summarize** → 知道执行结果会怎么告诉 AI

所有的 Skill 都遵循这个模式。读懂了其中一个，就读懂了全部 30 个。

**核心文件：**

| 文件                           | 作用                                        |
| ------------------------------ | ------------------------------------------- |
| `skills/base_skill.py`       | 基类定义（所有 Skill 的模板）               |
| `skills/character_skills.py` | 人物卡 Skill 实现                           |
| `skills/registry.py`         | Skill 注册 + 查找 + 执行                    |
| `skills/_shared.py`          | 共享工具函数（_load, _save, _work_path 等） |
