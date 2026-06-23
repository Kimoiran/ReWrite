"""创建 GitHub Release 并上传 exe。"""

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.storage.git_manager import _load_token

TOKEN, USER = _load_token()
if not TOKEN:
    print("错误：未配置 GitHub Token。请在设置中配置。")
    print("生成地址：https://github.com/settings/tokens（需要 repo 权限）")
    sys.exit(1)

REPO = "Kimoiran/ReWrite"
TAG = "v1.0.0"
EXE_PATH = Path(__file__).resolve().parent.parent / "dist" / "ReWrite.exe"

if not EXE_PATH.exists():
    print(f"错误：未找到 exe 文件：{EXE_PATH}")
    sys.exit(1)

def api(method: str, path: str, data: dict = None) -> dict:
    url = f"https://api.github.com/repos/{REPO}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ReWrite-Release-Script",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"API 错误 (HTTP {e.code}): {err[:300]}")
        sys.exit(1)

# 检查标签是否已有 Release
try:
    existing = api("GET", f"/releases/tags/{TAG}")
    print(f"发现已有 Release: {existing.get('html_url', '')}")
    release_id = existing["id"]
except SystemExit:
    sys.exit(1)
except:
    existing = None

if existing:
    # 上传到已有的 Release
    release_id = existing["id"]
    upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name=ReWrite.exe"
else:
    # 创建 Release
    print(f"创建 Release {TAG}...")
    release = api("POST", "/releases", {
        "tag_name": TAG,
        "name": f"ReWrite v1.0.0",
        "body": "## ReWrite v1.0.0\n\n一个开源的桌面写作软件。\n\n### 功能\n- 作品选择页（卡片网格）\n- 富文本编辑器 + 实时写入\n- 章节管理 + 自动快照\n- 人物设定卡\n- 大纲（文档/树形双视图 + 详情编辑）\n- 时间线（智能日期排序）\n- AI 写作助手（对话 + 跨模块批注 + 长期记忆）\n- 导入导出（ZIP / Git / Markdown / Word / 纯文本）\n- Git 集成（一键提交推送 + GitHub Token）\n- 全局搜索 + 多窗口同步\n- 无边框窗口 + 浅色主题\n- 设置（字体/自动保存/数据位置迁移）\n\n### 安装\n下载 ReWrite.exe 双击运行即可。作品自动保存在 Documents/ReWrite/works/。",
        "draft": False,
        "prerelease": False,
    })
    release_id = release["id"]
    upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name=ReWrite.exe"

# 上传 exe
print(f"正在上传 {EXE_PATH.stat().st_size / 1024 / 1024:.0f} MB...")
exe_data = EXE_PATH.read_bytes()
upload_req = urllib.request.Request(
    upload_url,
    data=exe_data,
    method="POST",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(exe_data)),
        "User-Agent": "ReWrite-Release-Script",
    })
try:
    with urllib.request.urlopen(upload_req, timeout=300) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"上传成功！下载地址：{result.get('browser_download_url', '')}")
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8", errors="replace")
    print(f"上传失败 (HTTP {e.code}): {err[:300]}")
    sys.exit(1)
