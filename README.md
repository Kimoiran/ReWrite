# ReWrite

> 要不别写了，歇一会吧。

一个开源的桌面写作软件。不过很烂就是了（有多烂呢，这么说吧，我自己都不知道我都让AI写了些什么玩意
其实我不是很建议任何人使用它，它只是我无聊时造出来的答辩，但是造得久了舍不得删
起码给了我很多情绪价值？

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

| 数据类型    | 位置                                                    |
| ----------- | ------------------------------------------------------- |
| 作品数据    | 源码运行：项目根目录 `works/`；打包后：exe 同目录 `works/`（可在设置中迁移） |
| 配置文件    | `%USERPROFILE%\.rewrite\`（API Key、Git Token、设置） |
| AI 对话历史 | `%USERPROFILE%\.rewrite\history\`                     |
| 运行日志    | `%USERPROFILE%\.rewrite\logs\rewrite.log`（轮转，最多 4 份 × 1 MB） |

---

## 配置指南

### 配置 AI

1. 打开 ReWrite → 启动页点击 ⚙ 设置 → 选择「AI 助手」
2. 选择供应商（DeepSeek / Claude / OpenAI），自定义 API URL 也支持
3. 输入 API Key，保存
4. 创建或打开作品时勾选「AI 写作助手」模块

AI 面板支持 **function calling + Skill 系统**：说「把主角的性格改成冷酷果断」，AI 会先弹窗让你确认，确认后直接修改数据文件。

### 配置 Git（工作空间版本管理）

ReWrite 使用**工作空间级 Git 仓库**——所有作品共享一个 `works/.git`。每个作品可选择是否参与云端同步。

**首次使用：**

1. 启动页 → ⚙ 设置 → 选择「Git 版本管理」
2. 输入 GitHub 仓库 URL（先去 GitHub 创建一个空仓库）
3. 粘贴 GitHub Personal Access Token（在 https://github.com/settings/tokens 生成，勾选 repo 权限）
4. 在「作品云端同步」区块中勾选需要同步的作品
5. 保存，回到启动页点「⬆ 推送」即可提交并推送

**日常使用：** 改完内容 → 回到启动页 → 点「⬆ 推送」→ 输入提交消息 → 完成。

**按作品粒度控制：** 新建作品时可勾选「☁ 同步到云端」；已创建的作品可在设置中随时切换，或右键卡片选择「同步到云端/取消云端同步」。不勾选的作品会写入 `.gitignore`，不会被提交推送。

---

## 功能模块

每个作品可独立选择启用哪些模块：

| 模块        | 说明                               | 默认 |
| ----------- | ---------------------------------- | ---- |
| 章节管理    | 章节增删改、重命名、排序、实时保存 | 必选 |
| 人物设定卡  | 多级分组管理角色信息，树形结构     | 可选 |
| 大纲        | 树形视图 + 文档视图双模式          | 可选 |
| 时间线      | 树形事件组织，智能日期排序         | 可选 |
| 世界观      | 分章节式世界设定，所见即所得(Markdown 富文本) | 可选 |
| 🗺️ 地图   | 层级地图，缩放拖拽，边界路线       | 可选 |
| AI 写作助手 | 对话 + Skill + 长期记忆            | 可选 |
| 🎨 主题     | 4 套内置主题 + 实时预览（设置 → 外观） | 全局 |

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
- 编辑/更改条目后子条目保持展开状态，不会自动收起

### 时间线

树形事件结构，父事件可以挂载子事件。

- 点击「+ 添加事件」创建事件
- 右键 → 添加子事件
- 日期使用纪元名+年号格式（如「创世元年」「建国200年」），自动按时间排序
- 纪元名在 `work.json` 的 `date_era` 字段配置，新建作品时可填写

### 世界观

- 树形分章节记录，**所见即所得**编辑：选中文字加粗/斜体立刻生效，插入表格直接编辑（Typora 式）
- 内容统一存储为 **Markdown 纯文本**（旧 HTML 数据首次打开自动迁移，滚动备份兜底）
- 自动滚动备份（保留最近 20 份）+ 原子写入

### 🗺️ 地图

层级地图系统：国家 → 地区 → 城市 → 街区 → 地标。

**操作方式：**

| 操作         | 方式                                                |
| ------------ | --------------------------------------------------- |
| 缩放         | 滚轮                                                |
| 平移视图     | 左键拖拽空白区域                                    |
| 添加节点     | 点击「+ 节点」                                      |
| 移动节点     | 直接拖拽圆点                                        |
| 重命名节点   | 右键节点 → 重命名                                  |
| 设置父节点   | 右键节点 → 设置所属父节点（国家-城市关系）         |
| 绘制边界     | 点「▦ 边界」→ 左键加点 → 点击起点封闭            |
| 拖拽边界顶点 | 直接拖白色圆点                                      |
| 多选顶点     | Shift + 左键逐个点击                                |
| 删除顶点     | 右键顶点 → 删除                                    |
| 绘制路线     | 点「⌇ 路线」→ 左键加点（自动吸附节点）→ 右键完成 | 
| 编辑节点     | 右键节点 → 编辑…（名称 / 类型 / 颜色 / 描述）   |
| 备注节点     | 「+ 节点」时类型选「备注」，便签式多行文本      |
| 调整节点样式 | 右键节点 → 半径 / 字号 / 斜体                      |

**AI 操作：** 说「帮我把北方王国和边陲小城画在地图上」，AI 自动调用 create_map_node。

### AI 写作助手

**交互方式：** 侧边面板对话，芯片式控制 AI 能读取哪些模块的数据。

**Skill 系统（共 32 个，按作品启用的模块自动收窄）：**

| 模块      | 技能数 | 技能                                                                                                                |
| --------- | ------ | ------------------------------------------------------------------------------------------------------------------- |
| 📖 章节   | 6      | get_chapters, read_chapter, create_chapter, update_chapter, rename_chapter, delete_chapter                          |
| 👤 人物卡 | 7      | get_character_groups, get_characters, create_character, update_character, delete_character, add_group, delete_group |
| 📋 大纲   | 4      | get_outline, create_outline_entry, update_outline_entry, delete_outline_entry                                       |
| 📅 时间线 | 4      | create_timeline_event, get_timeline, update_timeline_event, delete_timeline_event                                   |
| 🌍 世界观 | 4      | get_worldview, create_worldview_entry, update_worldview_entry, delete_worldview_entry                               |
| 🗺️ 地图 | 6      | get_map, create_map_node, update_map_node, delete_map_node, create_map_route, delete_map_route                      |
| 🔍 搜索   | 1      | search_chapters（TF-IDF 语义搜索章节正文，归入章节模块）                                                              |

> **工具清单跟随启用模块**：作品只开了「章节」时，AI 只能看到 7 个章节相关工具；
> 关掉的模块既不出现在提示词的清单里，注册表也不会把它的工具定义发给模型，
> 执行层还会再拦一次并回传「该模块未启用」。三层防护，避免 AI 去写没开的功能。

**核心机制：**

- **分层读取**：上下文仅显示概览（名称/身份），详细数据通过按需调用 get 工具获取
- **读操作免确认**：`get_*` / `read_*` / `search_*` 只读操作直接执行；仅写操作弹确认气泡
- **「全部允许」**：多步操作可一键放行后续所有确认
- **任务内自动继续**：确认一次写操作后，本任务内后续操作自动执行，无需逐条确认
- **「■ 停止」**：AI 工作期间可随时中断生成；已生成内容与已执行操作会保留并记入记忆
- **撤回 = 数据回滚**：AI 写操作前自动快照，点「↩ 撤回」恢复数据并撤回对话
- **自校验机制**：操作失败时返回现有数据列表（含 `existing_chapters`），AI 自动修正
- **章节名模糊匹配**：「第一章」「第1章」「第1章 在孤儿院的日子」都能定位到同一章，
  不再因为 AI 没逐字复述标题就报「未找到章节」
- **续写不丢上下文**：工具执行后的续写轮会带上完整对话，因此「每章 5000 字」这类要求
  在连续写作多章时依然生效，不会越写越短
- **工具随模块收窄**：作品关掉的模块不会出现在工具清单里，执行层也会拒绝调用
- **思考过程可回看、不进上下文**：推理内容显示在气泡上方（深色主题下用主题色，
  不会再变成刺眼白块），并随历史持久化；但发回模型前会被剥离——既省 token，
  也避免 AI 把自己斟酌中的猜测当成既定事实
- **对话自动贴底**：流式输出、气泡高度变化、加载气泡移除后都会重新贴到底部，
  不会出现「完成后下方一大片空白、要往上拉找对话」
- **作品级提示词**：✨ 指令 →「设置作品提示词…」可为单个作品定制写作风格与尺度
- **RAG 语义搜索**：说「找出所有描写下雨的段落」，AI 通过 TF-IDF 搜索所有章节找到最相关段落
- **长期记忆**：对话历史自动持久化，关了再开还记得；AI 输出中的 HTML 标签写入时自动清理为 Markdown
- **多供应商**：DeepSeek / Claude / OpenAI，还支持自定义 API URL
- **Markdown 表格渲染**：AI 输出的表格在聊天框中渲染为 HTML 表格

**AI 使用示例：**

```
「帮我创建一个人物——张三，二十五岁，铁匠」
「分析一下第一章的情节节奏」
「主角的性格有没有前后矛盾？」
「帮我把主角的年龄改成二十岁」
「初始化时间线，创世元年神降临，创世200年第二位神降临」
「帮我找找小说里所有提到'水'的段落」
```

---

## Git 版本管理

### 工作空间仓库

`works/` 目录整体是一个 Git 仓库。每个作品可通过云同步开关独立控制是否参与版本跟踪，未勾选的作品自动写入 `.gitignore`。

### 首次配置

1. 去 https://github.com/settings/tokens 生成 Token（Classic Token，勾选 repo 权限）
2. 启动页 → ⚙ 设置 → Git 版本管理 → 输入仓库 URL + 粘贴 Token → 保存
3. 在设置页勾选需要同步到云端的作品

### 日常操作

- **提交推送**：启动页点「⬆ 推送」→ 输入提交消息 → 确认
- **查看状态**：启动页 Git 按钮显示提交数 + 脏标记 `⚠`
- **云端标识**：已同步的作品卡片右上角显示蓝色 `☁ 云端` 徽章
- **切换同步**：右键卡片 → 同步到云端 / 取消云端同步；或在设置中批量管理

---

## 数据导入导出

### 导出

启动页 → 选择作品 → 导出 → 生成 `.writepack`（ZIP 格式，包含作品全部数据）

### 导入

启动页 → 导入 → 选择文件（支持 `.writepack`、ZIP、Git 仓库 URL、Markdown、纯文本）

---

## 高级功能

### 全局搜索

`Ctrl+Shift+F` 跨所有模块搜索——章节正文（支持 RAG 语义搜索）、人物名、大纲条目、时间线事件、AI 批注，一键跳转。

### 面板自由布局

章节列表、人物卡、大纲、时间线、AI 对话、批注、地图——所有面板都可以拖出来变成独立窗口，也可以贴回任意边缘。

### 自动快照备份

- 打字即保存：每次按键直接写入文件
- 定时快照：每 5 分钟为**最近修改过**的章节备份到 `.autosave/snapshots/`
- 留存策略：按章节编号分组，**每个章节保留最近 5 份**；改名、重排、删章后遗留的旧快照也会被自动回收

### AI 对话回溯

- 撤回按钮：一键撤回上一条对话（用户消息 + AI 回复）
- 清空记忆：同时删除磁盘上的对话历史文件

---

## 目录结构

```
ReWrite/
├── src/                      # 源代码（82 个 .py）
│   ├── main.py               # 入口：主题/字体/图标 → Workspace → 启动页
│   ├── launcher/             # 启动页（作品卡片、新建、导入）
│   ├── editor/               # 编辑器核心
│   │   ├── editor_widget.py     # 富文本编辑器
│   │   ├── window.py            # 编辑器主窗口（模块装配 + Dock 布局）
│   │   ├── chapter_list.py      # 章节列表面板
│   │   ├── search.py            # 全局搜索（Ctrl+Shift+F）
│   │   ├── sync.py              # 文档 ↔ 编辑器同步
│   │   ├── statusbar.py         # 状态栏（字数统计）
│   │   ├── toolbar.py           # 工具栏
│   │   ├── autosave/            # engine.py 实时写入+快照；recovery.py 崩溃恢复
│   │   ├── annotations/         # AI 批注：manager / gutter / panel
│   │   └── modules/             # 可选功能模块（统一 BaseModule 接口）
│   │       ├── chapters.py          # 章节（必选）
│   │       ├── characters.py        # 人物卡（无限层级树）
│   │       ├── outline.py           # 大纲（树形 + 文档双视图）
│   │       ├── timeline.py          # 时间线（纪元+年号智能排序）
│   │       ├── worldview.py         # 世界观（所见即所得 Markdown）
│   │       ├── map.py               # 地图（QGraphicsView，节点/边界/路线）
│   │       ├── md_document.py       # 自研无损 Markdown 导出器
│   │       └── ai_assistant/        # AI 助手
│   │           ├── module.py            # 模块入口 + Qt 桥接
│   │           ├── agent.py             # 对话管理 + 长期记忆
│   │           ├── orchestrator.py      # AI 流程控制器（零 Qt 依赖）
│   │           ├── providers.py         # API 调用（DeepSeek/Claude/OpenAI）
│   │           ├── worker.py            # 后台线程（流式推理）
│   │           ├── prompt_templates.py  # 提示词模板
│   │           ├── contexts.py          # 上下文收集
│   │           ├── rag.py               # RAG 语义搜索（TF-IDF）
│   │           ├── undo_stack.py        # AI 写操作快照 / 撤回
│   │           ├── markdown_render.py   # Markdown → HTML
│   │           ├── memory_editor.py     # 长期记忆编辑器
│   │           ├── skills/              # Skill 系统（32 个）
│   │           └── ui/chat_panel.py     # AI 聊天面板（确认气泡 / 停止）
│   ├── storage/              # 路径、工作空间、Git、元数据
│   ├── settings/             # 设置页（通用 / AI / Git / 外观）
│   ├── import_export/        # 导入导出（.writepack / Markdown / 纯文本）
│   ├── ui/                   # 主题 + 自定义标题栏 + 动画
│   └── utils/                # 字数统计 + 日志（logging_setup.py）
├── tests/                    # 单元测试（标准库 unittest，无需额外依赖）
├── scripts/                  # 开发辅助脚本（打包、校验、本地实验）
├── assets/                   # 图标
├── docs/release-notes/       # 每版发布说明（本地保留，不入库）
├── ReWrite.spec              # PyInstaller 打包配置
├── requirements.txt          # 唯一依赖：PySide6
├── run.bat                   # 一键启动脚本
└── README.md

works/                        # 作品数据（本地 Git 仓库，不入库）
~/.rewrite/                   # 个人配置（Token / API Key / 设置 / 日志）
```

---

## 测试

测试只用标准库 `unittest`，**不引入 pytest 等新依赖**，也不需要启动 GUI（只覆盖不依赖 Qt 事件循环的纯逻辑）。

```bash
# 全部测试
python -m unittest discover -s tests -t .

# 单文件 + 详细输出
python -m unittest tests.test_snapshots -v
```

| 测试文件 | 覆盖内容 |
| -------- | -------- |
| `test_snapshots.py` | 快照分组与留存（回归「改名后旧快照永不回收」） |
| `test_chapter_resolver.py` | 章节名宽松解析（「第一章」/「第7章」都能命中；「第1章」不误撞「第11章」） |
| `test_ai_continuation.py` | 续写轮必须携带原始对话（回归「连续写作字数骤降」） |
| `test_ai_module_gating.py` | 工具按启用模块收窄（回归「关了的功能还在写」） |
| `test_ai_reasoning_memory.py` | 思考过程只显示不进上下文、🧠 不堆叠、压缩记忆保留任务原点 |
| `test_skill_registry.py` | 32 个 Skill 契约、名称容错匹配、OpenAI/Claude 工具 schema |
| `test_skill_path_safety.py` | AI 提供的 `work` 参数不能越出 `works/`（路径穿越防御） |
| `test_meta.py` | `work.json` 读写往返、损坏/未知字段容错 |
| `test_markdown_render.py` | AI 输出的 Markdown → HTML，含 HTML 注入转义 |
| `test_stats.py` | 中英文字数统计与格式化 |
| `test_logging_setup.py` | 日志命名空间、无副作用、落盘与级别过滤 |
| `test_work_io.py` | 目录名 slug 化 |

所有落盘测试都在临时目录里跑，**不会碰 `works/` 里的真实作品**。

新增 Skill 或修改留存策略时，请同步更新对应测试与本文档的表格。

---

## 日志与排错

日志写在 `%USERPROFILE%\.rewrite\logs\rewrite.log`，单文件 1 MB、保留 3 份历史（合计约 4 MB）。

- **默认 INFO 级**：启动、AI 请求失败、数据读写失败、快照写入/清理失败都会记录
- **未捕获异常**会连同堆栈一起写进日志，界面闪退后可以回查原因
- 想要更详细（含调试细节）：

  ```bash
  set REWRITE_LOG_LEVEL=DEBUG
  ```

- 想换日志目录：

  ```bash
  set REWRITE_LOG_DIR=D:\我的日志
  ```

- 日志模块本身失败时只降级为控制台输出，**不会让程序起不来**

---

## 技术栈

| 技术          | 用途                              |
| ------------- | --------------------------------- |
| Python 3.12   | 主力语言                          |
| PySide6 6.11  | 桌面 GUI（Qt6）                   |
| urllib        | AI API 调用（内置，无需额外依赖） |
| QGraphicsView | 地图引擎                          |
| TF-IDF        | RAG 语义检索                      |
| Git           | 版本管理                          |
| unittest      | 单元测试（标准库，零额外依赖）     |
| logging       | 运行日志（标准库轮转）             |

---

## 开源协议

MIT License

---

*在写了，在写了。*
