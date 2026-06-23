"""Git 操作封装 + GitHub API 集成。"""

import json
import subprocess
from pathlib import Path

from .paths import get_config_dir


def _get_token_path() -> Path:
    return get_config_dir() / "git_config.json"


def _load_token() -> tuple[str, str]:
    """加载 GitHub Token 和用户名。"""
    path = _get_token_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("github_token", ""), data.get("github_user", "")
        except (json.JSONDecodeError, OSError):
            return "", ""
    return "", ""


def _save_token(token: str, user: str):
    """保存 GitHub Token 和用户名。"""
    try:
        path = _get_token_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"github_token": token, "github_user": user}
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        print(f"保存 Token 失败")


def test_remote_connection(url: str) -> tuple[bool, str]:
    """测试远程仓库是否可达。返回 (可达?, 信息)。"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        result = subprocess.run(
            ["git", "ls-remote", url],
            capture_output=True,
            timeout=30,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
        )
        if result.returncode == 0:
            return True, "连接成功，仓库可达"
        err = result.stderr.decode("utf-8", errors="replace").strip()
        if "Repository not found" in err:
            return False, "仓库不存在，请检查 URL 或权限"
        if "could not read Username" in err or "Authentication failed" in err:
            return False, "需要身份验证，请在设置中配置 GitHub Token"
        if "could not resolve host" in err:
            return False, "无法解析主机，请检查网络连接"
        return False, f"连接失败: {err[:100]}"
    except subprocess.TimeoutExpired:
        return False, "连接超时（30秒）"
    except FileNotFoundError:
        return False, "未安装 Git，请先安装 git-scm.com"
    except Exception as e:
        return False, f"未知错误: {e}"


def create_github_repo(token: str, repo_name: str, private: bool = True,
                        description: str = "") -> tuple[bool, str]:
    """通过 GitHub API 自动创建仓库。返回 (成功?, URL 或错误信息)。"""
    import urllib.request
    import urllib.error

    data = {
        "name": repo_name,
        "private": private,
        "description": description or f"ReWrite 创作: {repo_name}",
        "auto_init": False,
    }
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "ReWrite",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            clone_url = result.get("clone_url", "")
            if clone_url:
                return True, clone_url
            return False, "仓库创建成功但无法获取地址"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            return False, "Token 无效或已过期，请重新配置"
        if e.code == 422:
            return False, "仓库名已存在，请换个名字"
        return False, f"创建失败 (HTTP {e.code}): {body[:100]}"
    except urllib.error.URLError:
        return False, "网络错误，请检查网络连接"
    except Exception as e:
        return False, f"未知错误: {e}"


class GitManager:
    """管理单个作品目录的 Git 操作。"""

    def __init__(self, work_path: Path):
        self.work_path = work_path
        self._token, self._user = _load_token()

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        """执行 Git 命令，失败返回模拟失败对象。"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return subprocess.run(
                args,
                cwd=self.work_path,
                capture_output=True,
                timeout=30,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        except FileNotFoundError:
            msg = "Git not found. Please install from https://git-scm.com"
            return subprocess.CompletedProcess(args, 1, b"", msg.encode("utf-8"))
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(args, 1, b"", b"Operation timed out (30s)")

    def _remote_with_token(self, remote_url: str) -> str:
        """将 Token 嵌入远程 URL 用于认证推送。"""
        if not self._token or not remote_url:
            return remote_url
        # https://github.com/user/repo.git
        # -> https://TOKEN@github.com/user/repo.git
        if remote_url.startswith("https://"):
            return remote_url.replace("https://", f"https://{self._token}@", 1)
        return remote_url

    def is_repo(self) -> bool:
        """检查是否已是 Git 仓库。"""
        return (self.work_path / ".git").exists()

    def init(self) -> tuple[bool, str]:
        """初始化 Git 仓库。"""
        if self.is_repo():
            return True, "已经是 Git 仓库"
        r = self._run(["git", "init"])
        if r.returncode != 0:
            return False, r.stderr.decode("utf-8", errors="replace").strip()

        # 创建 .gitignore
        (self.work_path / ".gitignore").write_text(
            ".DS_Store\nThumbs.db\n*.tmp\n*.log\n", encoding="utf-8"
        )
        return True, "初始化成功"

    def status(self) -> dict:
        """获取仓库状态。"""
        if not self.is_repo():
            return {"dirty": False, "staged": 0, "unstaged": 0,
                    "commit_count": 0, "ahead": 0, "behind": 0,
                    "has_remote": False}

        r = self._run(["git", "status", "--porcelain"])
        lines = [l for l in r.stdout.decode("utf-8", errors="replace").split("\n") if l.strip()]
        staged = sum(1 for l in lines if not l.startswith("?"))
        unstaged = sum(1 for l in lines if l.startswith(" ?") or l.startswith("??"))

        # 提交数
        r2 = self._run(["git", "rev-list", "--count", "HEAD"])
        count_str = r2.stdout.decode("utf-8", errors="replace").strip()
        commit_count = int(count_str) if count_str and count_str.isdigit() else 0

        # 远程状态
        r3 = self._run(["git", "remote", "-v"])
        has_remote = bool(r3.stdout.decode("utf-8", errors="replace").strip())

        ahead = behind = 0
        if has_remote:
            r4 = self._run(["git", "rev-list", "--count", "--left-right",
                           "HEAD...@{upstream}"])
            out = r4.stdout.decode("utf-8", errors="replace").strip()
            if out:
                parts = out.split()
                for p in parts:
                    if p.startswith("<"):
                        behind += int(p[1:])
                    elif p.startswith(">"):
                        ahead += int(p[1:])

        return {
            "dirty": len(lines) > 0,
            "staged": staged,
            "unstaged": unstaged,
            "commit_count": commit_count,
            "ahead": ahead,
            "behind": behind,
            "has_remote": has_remote,
        }

    def add_all(self) -> tuple[bool, str]:
        """暂存所有更改。"""
        r = self._run(["git", "add", "-A"])
        if r.returncode == 0:
            return True, "暂存成功"
        return False, r.stderr.decode("utf-8", errors="replace").strip()

    def commit(self, message: str = "") -> tuple[bool, str]:
        """提交暂存的更改。"""
        msg = message or "ReWrite: 更新内容"
        r = self._run(["git", "commit", "-m", msg])
        if r.returncode == 0:
            out = r.stdout.decode("utf-8", errors="replace").strip()
            return True, out or "提交成功"
        err = r.stderr.decode("utf-8", errors="replace").strip()
        if "nothing to commit" in err or "nothing added" in err:
            return True, "没有需要提交的更改"
        return False, err

    def set_remote(self, url: str) -> tuple[bool, str]:
        """设置远程仓库。"""
        # 删除已有 remote
        self._run(["git", "remote", "remove", "origin"])
        r = self._run(["git", "remote", "add", "origin", url])
        if r.returncode == 0:
            return True, "远程仓库已绑定"
        return False, r.stderr.decode("utf-8", errors="replace").strip()

    def get_remote_url(self) -> str:
        """获取远程仓库 URL。"""
        r = self._run(["git", "remote", "get-url", "origin"])
        return r.stdout.decode("utf-8", errors="replace").strip()

    def _current_branch(self) -> str:
        """获取当前分支名。"""
        r = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        name = r.stdout.decode("utf-8", errors="replace").strip()
        return name if name else "main"

    def push(self) -> tuple[bool, str]:
        """推送到远程仓库。自动使用 Token 认证。"""
        if not self.is_repo():
            return False, "不是 Git 仓库"

        url = self.get_remote_url()
        if not url:
            return False, "未配置远程仓库"

        branch = self._current_branch()
        push_url = self._remote_with_token(url)
        r = self._run(["git", "push", "-u", push_url, branch])
        if r.returncode == 0:
            out = r.stdout.decode("utf-8", errors="replace").strip()
            return True, out or "推送成功"

        err = r.stderr.decode("utf-8", errors="replace").strip()
        if "could not read Username" in err or "Authentication failed" in err:
            _save_token("", self._user)
            return False, "认证失败，Token 已清空，请重新配置"
        return False, err[:200]

    def commit_and_push(self, message: str = "") -> tuple[bool, str]:
        """一键提交并推送。"""
        ok, msg = self.add_all()
        if not ok:
            return False, f"暂存失败: {msg}"
        ok, msg = self.commit(message)
        if not ok:
            return False, f"提交失败: {msg}"
        if self.get_remote_url():
            ok, msg = self.push()
            if not ok:
                return False, f"推送失败: {msg}"
        return True, "提交并推送成功"


def open_token_settings():
    """打开用户设置以配置 GitHub Token。"""
    path = _get_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _save_token("", "")
    import subprocess as sp
    sp.run(f'notepad "{path}"', shell=True)
