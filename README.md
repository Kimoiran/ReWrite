# ReWrite

> 要不别写了，歇一会吧。

一个开源的桌面写作软件。轻量、专注、模块化——想用什么功能，开什么功能。

- **Python** + **PySide6** 构建
- **本地优先**：文件即存储，纯 HTML 格式，不依赖任何服务
- **MIT 协议**开源

---

## 特性

### 富文本编辑
所见即所得的编辑器，加粗、斜体、标题、列表、引用——所有格式顺手。写作内容存为 HTML，任何浏览器都能打开阅读。

### 模块化设计，按需启用

每个作品独立配置功能模块，不需要的绝不打扰：

| 模块 | 说明 | 默认 |
|------|------|------|
| 章节管理 | 章节增删改、重命名、排序、实时保存 | 必选 |
| 人物设定卡 | 多级分组管理角色信息，树形结构，级数不限 | 可选 |
| 大纲 | 树形视图 + 文档视图双模式，双击原位编辑 | 可选 |
| 时间线 | 树形事件组织，智能日期排序，支持父/子事件 | 可选 |
| 世界观 | 分章节式世界设定，富文本编辑 | 可选 |
| 🗺️ 地图 | 层级地图（国家→地区→城市），缩放拖拽，边界绘制，路线规划 | 可选 |
| AI 写作助手 | 对话 + 批注 + 长期记忆 + 直接修改数据 | 可选 |

### AI 写作助手（Skill 系统 + function calling + 29 个技能）

当前注册技能（共 29 个）：

| 模块 | 技能数 | 技能 |
|------|--------|------|
| 章节 | 6 | 列表、读取、创建、修改（带 diff）、重命名、删除 |
| 人物卡 | 7 | 分组列表、获取、创建、修改、删除、添加分组、删除分组 |
| 大纲 | 3 | 获取、修改、删除 |
| 时间线 | 4 | 创建、获取、修改、删除 |
| 世界观 | 4 | 获取、创建、修改、删除 |
| 🗺️ 地图 | 6 | 获取地图、创建/修改/删除节点、创建/删除路线 |

每次修改/删除前弹出确认气泡，显示具体操作内容，确认后才执行。
- **对话模式**：侧边面板与 AI 对话，像 ChatGPT 一样自然
- **长期记忆**：AI 记得之前聊过什么，关编辑器再打开还在
- **上下文控制**：芯片式开关，精确控制 AI 能读到什么（当前章节、人物、大纲、世界观、时间线等）
- **多供应商**：支持 DeepSeek、Claude、OpenAI
- **Skill 系统**：所有可执行操作封装为独立 Skill，AI 通过原生 function calling 调用
- **分层读取**：上下文仅显示概览（名称/身份），详细数据通过 Skill 单独获取，避免截断和遗漏
- **操作前确认**：AI 提议修改时弹出对话框，确认后才执行
- **自校验机制**：操作失败时返回现有数据列表，AI 可自动修正
- **表格渲染**：AI 输出的 Markdown 表格渲染为带边框的 HTML 表格

### 人物设定卡（多级分组）
- 树形结构，级数不限：宗门 → 山头 → 人
- 双击重命名，右键添加同级/子级
- 批量导入 AI 输出的结构化文本
- 底部详情编辑器，点击角色显示完整字段

### 大纲（双视图）
- 树形视图：点击条目显示详情，双击编辑标题，右键添加子级
- 文档视图：纯文本 Markdown 风格，用 `#` 号分级
- 条目有状态标记（待写/写作中/已完成）

### 时间线
- 树形结构：父/子事件，可折叠展开
- 按日期智能排序（支持数字和中英文混合）
- 添加/编辑/删除事件，支持子事件

### 🗺️ 地图模块
- 层级地图：国家 → 地区 → 城市 → 街区 → 地标
- QGraphicsView 引擎：滚轮缩放，左键拖拽平移
- **边界绘制**：点击"边界"按钮进入绘制模式，左键添加顶点，封闭自动完成
- **路线绘制**：点击"路线"按钮绘制路径，右键完成，自动吸附节点
- **Shift+多选顶点**：选中多个顶点后拖拽可局部塑形或整体平移
- **完整 AI 读写**：6 个 Skill 覆盖节点和路线的 CRUD

### 世界观模块
- 树形分章节，可无限嵌套
- 右侧富文本编辑器，像写正文一样写设定
- AI 可读写世界观条目

### 实时写入 + 自动快照
- 打字即保存：每次按键直接写入文件
- 定时快照：每 5 分钟自动备份

### 所有面板可拖拽分离
章节列表、人物卡、大纲、时间线、AI 对话、批注——每个面板都可以拖出来变成独立窗口，也可以贴回任意边缘。

### 导入导出
- 导出 .writepack：完整打包作品
- 导入：ZIP 文件 / Git 仓库 / Markdown / Word / 纯文本

### Git 集成
- 每个作品独立的 Git 仓库
- 可选绑定 GitHub 私有仓库
- 状态栏一键提交并推送
- 支持 GitHub Token 自动创建仓库

### 全局搜索
`Ctrl+Shift+F` 跨所有模块搜索——章节正文、人物名、大纲条目、时间线事件、AI 批注，一键跳转。

### 无边框窗口
Windows 风格标题栏按钮，标题栏可拖拽，拖到顶部自动最大化。

### AI 对话回溯
- 撤回按钮：一键撤回上一条对话（用户消息 + AI 回复）
- 清空记忆：同时删除磁盘上的对话历史文件

---

## 快速开始

### 方式一：下载 exe（推荐）

从 [Releases](https://github.com/Kimoiran/ReWrite/releases) 下载最新版 `ReWrite.exe`，双击运行即可。

作品自动保存在 `Documents/ReWrite/works/`，配置文件在 `~/.rewrite/`。

### 方式二：从源码运行

```bash
git clone https://github.com/Kimoiran/ReWrite.git
cd ReWrite
pip install -r requirements.txt
python src/main.py
```

或双击 `run.bat`——自动创建虚拟环境、安装依赖、启动。

### 配置 AI

打开软件 → 文件 → 设置 → AI 助手，选择供应商（DeepSeek / Claude / OpenAI），输入 API Key，保存即可。

AI 面板支持 **function calling + Skill 系统**：说「把克诺的性格改成冷酷果断」，AI 会先弹窗让你确认，确认后直接修改数据。

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller ReWrite.spec
# dist/ReWrite.exe
```

---

## 目录结构

```
ReWrite/
├── src/                   # 源代码
│   ├── main.py
│   ├── launcher/          # 作品选择页
│   ├── editor/            # 编辑器核心
│   │   ├── editor_widget.py  # 富文本编辑器
│   │   ├── window.py         # 编辑器主窗口
│   │   ├── chapter_list.py   # 章节列表面板
│   │   ├── search.py         # 全局搜索
│   │   ├── autosave/         # 实时写入 + 快照
│   │   └── modules/          # 可选模块
│   │       ├── characters.py     # 人物卡（多级分组）
│   │       ├── outline.py        # 大纲
│   │       ├── timeline.py       # 时间线（树形）
│   │       ├── worldview.py      # 世界观
│   │       ├── map.py            # 🗺️ 地图（QGraphicsView）
│   │       └── ai_assistant/     # AI 助手
│   │           ├── agent.py          # 对话管理 + 记忆
│   │           ├── providers.py      # API 调用（function calling）
│   │           ├── skills/           # Skill 系统
│   │           │   ├── base_skill.py     # 基类
│   │           │   ├── character_skills.py  # 人物卡技能
│   │           │   ├── outline_skills.py    # 大纲技能
│   │           │   ├── timeline_skills.py   # 时间线技能
│   │           │   ├── worldview_skills.py  # 世界观技能
│   │           │   ├── map_skills.py        # 🗺️ 地图技能
│   │           │   ├── registry.py          # 注册表
│   │           │   └── _shared.py           # 共享工具函数
│   │           ├── contexts.py    # 上下文收集
│   │           ├── prompt_templates.py  # 提示词模板
│   │           ├── markdown_render.py    # Markdown → HTML
│   │           ├── annotation_manager.py # 批注管理
│   │           └── ui/           # AI 对话界面
│   ├── storage/           # 存储层
│   │   ├── workspace.py
│   │   ├── work_io.py
│   │   ├── meta.py
│   │   ├── paths.py
│   │   └── git_manager.py
│   ├── settings/          # 设置页面
│   ├── import_export/     # 导入导出
│   ├── ui/                # 主题 + 标题栏
│   └── utils/
├── assets/                # 图标等资源
├── run.bat                # 一键启动
└── README.md

works/                     # 作品（被 .gitignore 排除）
~/.rewrite/                # 个人配置（项目外）
```

---

## 技术栈

| 技术 | 用途 |
|------|------|
| Python | 主力语言 |
| PySide6 | 桌面 GUI（Qt6） |
| urllib | AI API 调用（内置，无需额外依赖） |
| python-docx | Word 导入（可选） |
| Git | 版本管理 |

---

## 开源协议

MIT License

---

*在写了，在写了。*
