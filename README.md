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

| 模块 | 说明 | 默认 |
|------|------|------|
| 章节管理 | 章节增删改、重命名、排序、实时保存 | 必选 |
| 人物设定卡 | 多级分组管理角色信息，树形结构，级数不限 | 可选 |
| 大纲 | 树形视图 + 文档视图双模式，双击原位编辑 | 可选 |
| 时间线 | 事件列表，智能日期排序，关联角色 | 可选 |
| 世界观 | 分章节式世界设定，富文本编辑 | 可选 |
| AI 写作助手 | 对话 + 批注 + 长期记忆 + 直接修改数据 | 可选 |

### 所有面板可拖拽分离
每个面板都可以拖出来变成独立窗口，也可以贴回任意边缘。

### AI 写作助手（API 原生 function calling）
- **对话模式**：侧边面板与 AI 对话，像 ChatGPT 一样自然
- **长期记忆**：AI 记得之前聊过什么，关编辑器再打开还在
- **上下文控制**：芯片式开关，精确控制 AI 能读到什么
- **多供应商**：支持 Claude、OpenAI、DeepSeek
- **直接修改数据**：通过 API function calling 直接创建/修改角色、条目、事件，不污染对话历史
- **AI 编辑可确认**：修改前弹出对话框显示新旧值对比，确认后才执行
- **批注模式**：AI 跨模块标记建议（正文、人物、大纲、时间线）

### MCP 服务器（集成）
- 启动时自动在后台运行 MCP 服务器（stdio 协议）
- 提供 13 个工具供外部 AI 客户端调用
- 自动写入 Claude Desktop 配置（`~/.claude/mcp.json`）
- 与软件自带 AI 共享同一套工具函数

### 人物设定卡（多级分组）
- 树形结构，级数不限：宗门 → 山头 → 人
- 双击重命名，右键添加同级/子级
- 批量导入 AI 输出的结构化文本
- 底部详情编辑器，点击角色显示完整字段

### 世界观模块
- 树形分章节，可无限嵌套
- 右侧富文本编辑器，像写正文一样写设定
- AI 可读写世界观条目

### 实时写入 + 自动快照
- 打字即保存：每次按键直接写入文件
- 定时快照：每 5 分钟自动备份

### 导入导出
- 导出 .writepack：完整打包作品
- 导入：ZIP 文件 / Git 仓库 / Markdown / Word / 纯文本
- 批量导入人物结构数据

### Git 集成
- 每个作品独立的 Git 仓库
- 可选绑定 GitHub 私有仓库
- 状态栏一键提交并推送
- 支持 GitHub Token 自动创建仓库

### 全局搜索
`Ctrl+Shift+F` 跨所有模块搜索——章节正文、人物名、大纲条目、时间线事件、AI 批注，一键跳转。

### 无边框窗口
macOS 风格交通灯按钮，标题栏可拖拽，拖到顶部自动最大化。

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

AI 面板支持 **function calling**：说「把克诺的性格改成冷酷果断」AI 会直接调用工具修改数据。

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
│   ├── editor/            # 编辑器
│   │   └── modules/       # 可选模块
│   │       ├── characters.py   # 人物卡（多级分组）
│   │       ├── outline.py      # 大纲
│   │       ├── timeline.py     # 时间线
│   │       ├── worldview.py    # 世界观
│   │       └── ai_assistant/   # AI 助手（function calling）
│   ├── mcp_manager.py     # MCP 服务器管理器
│   ├── storage/           # 存储层
│   ├── settings/          # 设置
│   ├── import_export/     # 导入导出
│   └── ui/                # 主题
├── mcp/                   # MCP 服务器 + 共享工具库
│   ├── server.py          # stdio MCP 服务器
│   └── tools.py           # 工具函数（AI 助手和 MCP 共用）
├── assets/
├── run.bat
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
