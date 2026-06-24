"""MCP 服务器管理器 — 随软件启动，后台静默运行。"""

import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal


def _server_script() -> Path:
    """返回 mcp/server.py 的路径。"""
    base = Path(__file__).resolve().parent.parent
    return base / "mcp" / "server.py"


def _works_dir_for_config() -> Path:
    """获取 MCP 配置用的 works 路径。"""
    import sys as _sys
    base = Path(__file__).resolve().parent.parent
    if getattr(_sys, 'frozen', False):
        return Path.home() / "Documents" / "ReWrite" / "works"
    return base / "works"


def _write_mcp_entry(path: Path, entry: dict):
    """将 MCP 条目写入配置文件，不覆盖已有配置。"""
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            servers = existing.setdefault("mcpServers", {})
            if "rewrite" not in servers:
                servers["rewrite"] = entry
                path.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except Exception:
            pass
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        config = {"mcpServers": {"rewrite": entry}}
        path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def install_mcp_config():
    """将 MCP 配置写入用户目录和项目目录，让客户端自动发现。"""
    script = _server_script()
    if not script.exists():
        return

    entry = {
        "command": sys.executable,
        "args": [str(script)],
        "env": {
            "PYTHONUNBUFFERED": "1",
            "REWRITE_WORKS_DIR": str(_works_dir_for_config()),
        },
    }

    # Claude Desktop: ~/.claude/mcp.json
    _write_mcp_entry(Path.home() / ".claude" / "mcp.json", entry)

    # VS Code: .vscode/mcp.json（项目内）
    project_root = Path(__file__).resolve().parent.parent
    _write_mcp_entry(project_root / ".vscode" / "mcp.json", entry)


class MCPManager(QObject):
    """管理 MCP 服务器子进程的生命周期。"""

    status_changed = Signal(str)  # "running" | "stopped" | "error"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        """启动 MCP 服务器子进程。"""
        if self._running:
            return
        script = _server_script()
        if not script.exists():
            self.status_changed.emit("error")
            return

        try:
            self._process = subprocess.Popen(
                [sys.executable, str(script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self._running = True
            self.status_changed.emit("running")
            print("[MCP] 服务器已启动")
        except Exception as e:
            self._running = False
            self.status_changed.emit("error")
            print(f"[MCP] 启动失败: {e}")

    def stop(self):
        """停止 MCP 服务器。"""
        if self._process and self._running:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
            self._running = False
            self.status_changed.emit("stopped")
            print("[MCP] 服务器已停止")
