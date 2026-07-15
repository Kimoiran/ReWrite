# ReWrite

> 要不别写了，歇一会吧。

一个开源的桌面写作软件。轻量、专注、模块化——想用什么功能，开什么功能。

- **Python 3.12** + **PySide6** 构建
- **本地优先**：文件即存储，JSON + HTML 格式，不依赖任何服务
- **MIT 协议**开源

---

## 快速开始

### 方式一：下载 exe（推荐）

从 [Releases](https://github.com/Kimoiran/ReWrite/releases) 下载最新版 `ReWrite.exe`，双击运行即可。

### 方式二：从源码运行

```bash
git clone https://github.com/Kimoiran/ReWrite.git
cd ReWrite
pip install -r requirements.txt
python src/main.py
```

或双击 `run.bat` —— 自动创建虚拟环境、安装依赖、启动。

### 数据存储位置

| 数据类型 | 位置 |
|---------|------|
| 作品数据 | `Documents/ReWrite/works/`（可在设置中迁移） |
| 配置文件 | `%USERPROFILE%\.rewrite\`（API Key、Git Token、设置） |
| AI 对话历史 | `%USERPROFILE%\.rewrite\history\` |

---

## 配置指南

### 配置 AI

1. 打开 ReWrite → 启动页点击 ⚙ 设置 → 选择「AI 助手」
2. 选择供应商（DeepSeek / Claude / OpenAI），自定义 API URL 也支持
3. 输入 API Key，保存
4. 创建或打开作品时勾选「AI 写作助手」模块

AI 面板支持 **function calling + Skill 系统**：说「把克诺的性格改成冷酷果断」，AI 会先弹窗让你确认，确认后直接修改数据文件。

### 配置 Git（工作空间版本管理）

ReWrite 使用**工作空间级 Git 仓库**——所有作品共享一个 `works/.git`，无需为每个作品单独建库。

**首次使用：**
1. 启动页 → ⚙ 设置 → 选择「Git 版本管理」
2. 粘贴 GitHub Personal Access Token（在 https://github.com/settings/tokens 生成，勾选 repo 权限）
3. 保存（Token 仅存本地 `~/.rewrite/git_config.json`，不会上传）
4. 回到启动页，点「⬆ 推送」按钮即可 `add + commit + push` 全部作品

**日常使用：** 改完内容 → 回到启动页 → 点「⬆ 推送」→ 输入提交消息 → 完成。

**自动创建 GitHub 仓库：** 新建作品时勾选「Git 版本管理」并输入仓库 URL，或在创建对话框中使用「自动创建仓库」功能（需要 Token）。

---

## 功能模块

每个作品可独立选择启用哪些模块：

| 模块 | 说明 | 默认 |
|------|------|------|
| 章节管理 | 章节增删改、重命名、排序、实时保存 | 必选 |
| 人物设定卡 | 多级分组管理角色信息，树形结构 | 可选 |
| 大纲 | 树形视图 + 文档视图双模式 | 可选 |
| 时间线 | 树形事件组织，智能日期排序 | 可选 |
| 世界观 | 分章节式世界设定，富文本编辑 | 可选 |
| 🗺️ 地图 | 层级地图，缩放拖拽，边界路线 | 可选 |
| AI 写作助手 | 对话 + Skill + 长期记忆 | 可选 |

### 章节管理

- 双击章节列表项切换到该章节
- 右键 → 重命名 / 删除
- 点击「+ 新建章节」输入标题创建
- AI 可通过 `create_chapter` 帮你写新章节
- 修改章节内容时 AI 会弹 diff 对比确认框

### 人物设定卡

树形结构：分组 → 子分组 → 角色，级数不限。

- **添加分组**：点击「+ 分组」
- **添加角色**：选中分组后点「+ 角色」
- **编辑字段**：选中角色后在下方详情区编辑，点「保存修改」
- **批量导入**：粘贴 AI 生成的结构化文本
- **AI 操作**：说「创建一个角色，叫张三，年龄 25」，AI 自动调 create_character

### 大纲

- 树形视图：点击条目显示详情，双击编辑标题，右键添加子级
- 条目状态：待写 / 写作中 / 已完成
- 选中条目后在下方详情区编辑大纲内容

### 时间线

树形事件结构，父事件可以挂载子事件。

- 点击「+ 添加事件」创建事件
- 右键 → 添加子事件
- 日期使用纪元名+年号格式（如「神启1017年」），自动按时间排序
- 纪元名在 `work.json` 的 `date_era` 字段配置，新建作品时可填写

### 世界观

- 树形分章节记录，内容为富文本 HTML
- 选中条目在右侧编辑
- 自动滚动备份（保留最近 20 份）

### 🗺️ 地图

层级地图系统：国家 → 地区 → 城市 → 街区 → 地标。

**操作方式：**

| 操作 | 方式 |
|------|------|
| 缩放 | 滚轮 |
| 平移视图 | 左键拖拽空白区域 |
| 添加节点 | 点击「+ 节点」 |
| 移动节点 | 直接拖拽圆点 |
| 重命名节点 | 右键节点 → 重命名 |
| 设置父节点 | 右键节点 → 设置所属父节点（国家-城市关系） |
| 绘制边界 | 点「▦ 边界」→ 左键加点 → 点击起点封闭 |
| 拖拽边界顶点 | 直接拖白色圆点 |
| 多选顶点 | Shift + 左键逐个点击 |
| 删除顶点 | 右键顶点 → 删除 |
| 绘制路线 | 点「⌇ 路线」→ 左键加点（自动吸附节点）→ 右键完成 |
| 调整节点样式 | 右键节点 → 半径 / 字号 / 斜体 |

**AI 操作：** 说「帮我把克里斯兰和特因城画在地图上」，AI 自动调用 create_map_node。

### AI 写作助手

**交互方式：** 侧边面板对话，芯片式控制 AI 能读取哪些模块的数据。

**Skill 系统（共 30 个）：**

| 模块 | 技能数 | 技能 |
|------|--------|------|
| 📖 章节 | 6 | get_chapters, read_chapter, create_chapter, update_chapter, rename_chapter, delete_chapter |
| 👤 人物卡 | 7 | get_character_groups, get_characters, create_character, update_character, delete_character, add_group, delete_group |
| 📋 大纲 | 3 | get_outline, update_outline_entry, delete_outline_entry |
| 📅 时间线 | 4 | create_timeline_event, get_timeline, update_timeline_event, delete_timeline_event |
| 🌍 世界观 | 4 | get_worldview, create_worldview_entry, update_worldview_entry, delete_worldview_entry |
| 🗺️ 地图 | 6 | get_map, create_map_node, update_map_node, delete_map_node, create_map_route, delete_map_route |
| 🔍 搜索 | 1 | search_chapters（TF-IDF 语义搜索章节正文） |

**核心机制：**

- **分层读取**：上下文仅显示概览（名称/身份），详细数据通过按需调用 get 工具获取
- **操作前确认**：AI 修改/删除前弹出确认气泡，显示具体操作内容
- **自校验机制**：操作失败时返回现有数据列表，AI 自动修正
- **RAG 语义搜索**：说「找出所有描写下雨的段落」，AI 通过 TF-IDF 搜索所有章节找到最相关段落
- **长期记忆**：对话历史自动持久化，关了再开还记得
- **多供应商**：DeepSeek / Claude / OpenAI，还支持自定义 API URL
- **Markdown 表格渲染**：AI 输出的表格在聊天框中渲染为 HTML 表格

**AI 使用示例：**

```
「帮我创建一个人物——张三，二十五岁，铁匠」
「分析一下第一章的情节节奏」
「克诺的性格有没有前后矛盾？」
「帮我把克诺的年龄改成二十岁」
「初始化时间线，神启元年智慧神降临，神启200年黑暗神降临」
「帮我找找小说里所有提到'水'的段落」
```

---

## Git 版本管理

### 工作空间仓库

`works/` 目录本身是一个 Git 仓库，所有作品共享。一个作者 = 一个仓库。

### Token 配置

1. 去 https://github.com/settings/tokens 生成 Token（Classic Token，勾选 repo 权限）
2. 启动页 → ⚙ 设置 → Git 版本管理 → 粘贴 Token → 保存

### 日常操作

- **提交推送**：启动页点「⬆ 推送」→ 输入提交消息 → 确认
- **查看状态**：启动页 Git 按钮显示提交数 + 脏标记 `⚠`
- **自动创建仓库**：新建作品时可调用 GitHub API 自动创建仓库

---

## 数据导入导出

### 导出

启动页 → 选择作品 → 导出 → 生成 `.writepack`（ZIP 格式，包含作品全部数据）

### 导入

启动页 → 导入 → 选择文件（支持 `.writepack`、ZIP、Git 仓库 URL、Markdown、Word、纯文本）

---

## 高级功能

### 全局搜索

`Ctrl+Shift+F` 跨所有模块搜索——章节正文（支持 RAG 语义搜索）、人物名、大纲条目、时间线事件、AI 批注，一键跳转。

### 面板自由布局

章节列表、人物卡、大纲、时间线、AI 对话、批注、地图——所有面板都可以拖出来变成独立窗口，也可以贴回任意边缘。

### 自动快照备份

- 打字即保存：每次按键直接写入文件
- 定时快照：每 5 分钟自动备份到 `.autosave/snapshots/`
- 保留最近 10 份快照

### AI 对话回溯

- 撤回按钮：一键撤回上一条对话（用户消息 + AI 回复）
- 清空记忆：同时删除磁盘上的对话历史文件

---

## 目录结构

```
ReWrite/
├── src/                   # 源代码
│   ├── main.py            # 入口
│   ├── launcher/          # 启动页（作品选择）
│   ├── editor/            # 编辑器核心
│   │   ├── editor_widget.py  # 富文本编辑器
│   │   ├── window.py         # 编辑器主窗口
│   │   ├── chapter_list.py   # 章节列表
│   │   ├── search.py         # 全局搜索
│   │   ├── autosave/         # 实时写入 + 快照
│   │   └── modules/          # 可选模块
│   │       ├── characters.py     # 人物卡
│   │       ├── outline.py        # 大纲
│   │       ├── timeline.py       # 时间线
│   │       ├── worldview.py      # 世界观
│   │       ├── map.py            # 地图
│   │       └── ai_assistant/     # AI 助手
│   │           ├── agent.py          # 对话管理 + 记忆
│   │           ├── providers.py      # API 调用
│   │           ├── rag.py            # RAG 引擎
│   │           ├── skills/           # Skill 系统（30 个）
│   │           ├── contexts.py       # 上下文收集
│   │           ├── prompt_templates.py  # 提示词
│   │           └── markdown_render.py   # Markdown 渲染
│   ├── storage/           # 存储层
│   ├── settings/          # 设置页面
│   ├── import_export/     # 导入导出
│   └── ui/                # 主题 + 标题栏
├── study/                 # AI Agent 学习书（8 篇）
├── assets/                # 图标
├── run.bat                # 一键启动
└── README.md

works/                     # 作品（本地，Git 仓库）
~/.rewrite/                # 个人配置（Token / API Key / 设置）
```

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.12 | 主力语言 |
| PySide6 6.11 | 桌面 GUI（Qt6） |
| urllib | AI API 调用（内置，无需额外依赖） |
| QGraphicsView | 地图引擎 |
| TF-IDF | RAG 语义检索 |
| Git | 版本管理 |

---

## 学习资源

`study/` 目录包含一套从零开始的 AI Agent 学习书（8 篇）：

| 章节 | 内容 |
|------|------|
| 01 | 什么是 AI Agent？ |
| 02 | 什么是 Skill 系统？ |
| 03 | 什么是提示词？ |
| 04 | 三者如何协作？ |
| 05 | 从代码看 Skill |
| 06 | 从代码看提示词 |
| 07 | 代码结构一览 |
| 08 | 什么是 RAG？ |

---

## 开源协议

MIT License

---

*在写了，在写了。*
