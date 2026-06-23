# ReWrite

> 要不别写了，歇一会吧。

一个开源的桌面写作软件。轻量、专注、模块化——想用什么功能，开什么功能。

- **Python** + **PySide6** 构建
- **本地优先**：文件即存储，纯 HTML 格式，不依赖任何服务
- **MIT 协议**开源

---

## 截图

*（等你来填）*

---

## 特性

### 📝 富文本编辑
所见即所得的编辑器，加粗、斜体、标题、列表、引用——所有格式顺手。写作内容存为 HTML，任何浏览器都能打开阅读。

### 🧩 模块化设计，按需启用

每个作品独立配置功能模块，不需要的绝不打扰：

| 模块 | 说明 | 默认 |
|------|------|------|
| 📖 章节管理 | 章节增删改、重命名、排序、自动保存 | ✅ 必选 |
| 👤 人物设定卡 | 管理角色信息、外貌、性格、背景、关系网 | 可选 |
| 📋 大纲 | 树形视图 + 文档视图双模式，双击原位编辑 | 可选 |
| 📅 时间线 | 事件列表，按日期排序，关联角色 | 可选 |
| 🤖 AI 写作助手 | 对话式 + 批注式双模式，AI 只读不改 | 可选 |

### 🔌 所有面板可拖拽分离
章节列表、人物卡、大纲、时间线、AI 对话、批注——**每个面板都可以拖出来变成独立窗口**，也可以贴回任意边缘。两个显示器？大纲拖到副屏，主屏专心写。

### 🤖 AI 写作助手（长期记忆）

- **💬 对话模式**：在侧边面板与 AI 对话，像 ChatGPT 一样自然
- **📌 批注模式**：AI 在正文上标记建议，悬停查看，逐条采纳或忽略
- **🧠 长期记忆**：AI 记得你之前聊过什么，关了编辑器再打开还在
- **🎛 上下文控制**：芯片式开关，精确控制 AI 能读到什么
  - 当前章节 / 选中文本 / 大纲 / 人物卡 / 时间线 / 作品信息
- **🔗 多供应商**：支持 Claude、OpenAI、DeepSeek（默认 deepseek-v4-flash）
- **只读原则**：AI 只能读，不能改。所有建议由你决定是否采纳

### 💾 实时写入 + 自动快照

- **打字即保存**：每次按键直接写入文件，无需等待
- **定时快照**：每 5 分钟自动备份到 `.autosave/snapshots/`
- **崩溃恢复**：启动时检测异常退出，提示恢复快照
- **手动快照**：Ctrl+S 时额外创建时间戳快照

### 🔐 三层隐私保护

| 层级 | 内容 | 位置 |
|------|------|------|
| 🌐 公开 | 源代码 | GitHub 公开仓库 |
| 🔒 本地作品 | 章节、人物卡、大纲等 | `works/`（`.gitignore` 排除） |
| 🤫 个人配置 | API Key、GitHub Token、AI 记忆 | `~/.rewrite/`（项目外） |

- 代码开源，**作品内容绝不进入公开仓库**
- 每个作品可绑定独立的私有 GitHub 仓库，可选是否同步
- AI API Key 和对话记忆存在用户目录，git 根本看不到

### 📦 导入导出

- **导出 .writepack**：完整打包作品（章节 + 模块数据 + 资源）
- **导入 .writepack**：完整恢复作品
- **导入 Markdown**：将 `.md` 文件导入为新章节
- **导入 Word / 纯文本**：更多格式支持

### 🔄 Git 集成

- 每个作品独立的 Git 仓库
- 新建作品时选择是否启用 Git
- 可选绑定 GitHub 私有仓库
- 状态栏一键「提交并推送」
- GitHub Token 配置后可通过 API 自动创建仓库

### 🔍 全局搜索

`Ctrl+Shift+F` 跨所有模块搜索——章节正文、人物名、大纲条目、时间线事件、AI 批注，一键跳转。

### 🪟 无边框窗口

macOS 风格交通灯按钮（最小化/最大化/关闭），标题栏可拖拽，拖到顶部自动最大化。干净、现代、不占空间。

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/yourname/ReWrite.git
cd ReWrite

# 安装依赖
pip install -r requirements.txt

# 运行
python src/main.py
```

或者双击 `run.bat`——自动创建虚拟环境、安装依赖、启动。

### 打包为 exe

```bash
pip install pyinstaller
pyinstaller ReWrite.spec
# dist/ReWrite/ReWrite.exe
```

---

## 目录结构

```
ReWrite/
├── src/
│   ├── main.py              # 入口
│   ├── launcher/            # 作品选择页（卡片网格）
│   ├── editor/              # 编辑器核心
│   │   ├── window.py        # 编辑器主窗口（Dock 系统）
│   │   ├── editor_widget.py # 富文本编辑器
│   │   ├── toolbar.py       # 格式化工具栏
│   │   ├── chapter_list.py  # 章节列表面板
│   │   ├── search.py        # 全局搜索
│   │   ├── autosave/        # 实时写入 + 快照引擎
│   │   ├── sync.py          # 多窗口同步
│   │   └── modules/         # 可选模块
│   │       ├── chapters.py      # 章节管理
│   │       ├── characters.py    # 人物设定卡
│   │       ├── outline.py       # 大纲（树形+文档视图）
│   │       ├── timeline.py      # 时间线
│   │       └── ai_assistant/    # AI 写作助手
│   ├── storage/             # 存储层
│   │   ├── workspace.py     # 工作区扫描
│   │   ├── work_io.py       # 作品 CRUD
│   │   ├── meta.py          # 元数据模型
│   │   └── git_manager.py   # Git 操作封装
│   ├── settings/            # 设置页面
│   ├── import_export/       # 导入导出
│   ├── ui/                  # 主题和标题栏
│   └── utils/               # 工具函数
├── assets/
├── run.bat                  # 一键启动脚本
├── ReWrite.spec             # PyInstaller 打包配置
├── .gitignore               # 已排除 works/ 等
└── README.md

works/                       # 🔐 作品目录（不进公开仓库）
├── 你的作品/
│   ├── .git/
│   ├── work.json            # 作品元数据 + 模块配置
│   ├── chapters/            # 章节（HTML）
│   ├── characters.json
│   ├── outline.json
│   ├── timeline.json
│   ├── .autosave/           # 自动快照
│   └── assets/

~/.rewrite/                  # 🤫 个人配置（项目外）
├── ai_config.json           # API Key
├── git_config.json          # GitHub Token
├── history/                 # AI 对话记忆
└── settings.json            # 编辑器设置
```

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **Python** | 主力语言 |
| **PySide6** | 桌面 GUI（Qt6） |
| **URU** | AI API 调用（内置，无需额外依赖） |
| **python-docx** | Word 导入（可选） |
| **Git** | 版本管理 |

## 开发进度

```
阶段 1 ✅ 项目骨架 + 作品选择页（卡片网格）
阶段 2 ✅ 富文本编辑器 + 章节管理 + 实时保存
阶段 3 ✅ 人物卡 + 大纲（双视图）+ 时间线 + 全局搜索
阶段 4 ✅ AI 写作助手（对话+批注+长期记忆）
阶段 5 ✅ 导入导出 + Git 集成 + 设置 + 崩溃恢复 + 打包
       ✅ 现代主题 + 无边框窗口 + 多窗口同步 + Dock 自由拖拽
```

---

## 开源协议

MIT License

---

*在写了，在写了。*
