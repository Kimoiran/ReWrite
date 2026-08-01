"""AI 写操作撤销栈 — 执行前快照数据文件,撤回时恢复。

纯 Python、零 Qt 依赖,便于单独测试。

设计:
- 每次 AI 写工具执行前,把涉及的存储文件内容快照进内存栈
- 用户点「撤回」时弹出最近一次快照恢复文件,同时撤回对应对话
- 快照按工具名前缀映射到数据文件;章节操作快照整个 chapters/ 目录
"""

from pathlib import Path
from typing import Optional


# 工具名子串 → 数据文件名(update_character/create_character/get_map 等均含模块名)
_TOOL_FILE_MAP = [
    ("character", "characters.json"),
    ("outline", "outline.json"),
    ("timeline", "timeline.json"),
    ("worldview", "worldview.json"),
    ("map", "map.json"),
]


class AIUndoStack:
    """内存撤销栈。每个条目 = 一次 AI 写操作前的文件快照。"""

    def __init__(self):
        self._entries: list[dict] = []

    # ── 工具 → 文件映射 ──

    @staticmethod
    def files_for_tool(tool_name: str, work_path: Path) -> list[Path]:
        """根据工具名确定涉及的存储文件(不存在则返回空列表)。"""
        if "chapter" in tool_name:
            cd = work_path / "chapters"
            if cd.is_dir():
                return sorted(cd.glob("*.md")) + sorted(cd.glob("*.html"))
            return []
        for key, fname in _TOOL_FILE_MAP:
            if key in tool_name:
                f = work_path / fname
                return [f] if f.exists() else []
        return []

    @staticmethod
    def _snapshot(files: list[Path]) -> dict:
        backups = {}
        for f in files:
            try:
                backups[str(f)] = f.read_text(encoding="utf-8")
            except OSError:
                pass  # 读不到的文件跳过,恢复时也跳过
        return backups

    # ── 栈操作 ──

    def push(self, tool_name: str, args: dict, work_path: Path):
        """写操作执行前调用:快照涉及文件并入栈。"""
        files = self.files_for_tool(tool_name, work_path)
        backups = self._snapshot(files)
        self._entries.append({
            "tool": tool_name,
            "args": dict(args),
            "work": str(work_path),
            "files": list(backups.keys()),
            "backups": backups,
            # 执行成功后由 attach_result 关联实际创建的文件路径(精确回滚删除用)
            "created_paths": [],
        })

    def attach_result(self, result) -> None:
        """执行成功后调用:把工具实际创建/重命名到的文件路径关联到最近一次快照。

        只有明确返回 path 的文件才会在撤回时删除,绝不误伤用户手动创建的文件。
        """
        if not self._entries or not isinstance(result, dict):
            return
        p = result.get("path")
        if p:
            self._entries[-1]["created_paths"].append(str(p))

    def pop_rollback(self):
        """丢弃最近一次快照(执行失败时调用,避免把未生效的操作计入回滚)。"""
        if self._entries:
            self._entries.pop()

    def pop_restore(self) -> Optional[dict]:
        """恢复最近一次快照,返回 {'tool', 'restored': [路径...]};栈空返回 None。

        恢复内容:① 快照过的文件写回原内容;② 工具实际创建的文件(attach_result 关联)删除。
        """
        if not self._entries:
            return None
        entry = self._entries.pop()
        restored = []
        for path_str, content in entry["backups"].items():
            try:
                Path(path_str).write_text(content, encoding="utf-8")
                restored.append(path_str)
            except OSError:
                pass
        # 删除 AI 工具实际创建的文件(按精确路径,且校验在作品目录内),
        # 用户手动创建的文件绝不涉及
        work_dir = Path(entry.get("work", ""))
        try:
            work_resolved = work_dir.resolve()
        except OSError:
            work_resolved = work_dir
        for rel in entry.get("created_paths", []):
            fp = work_dir / rel
            try:
                fp_resolved = fp.resolve()
                fp_resolved.relative_to(work_resolved)  # 校验在作品目录内
            except (OSError, ValueError):
                continue
            if fp_resolved.is_file() and fp_resolved.suffix.lower() in (".md", ".html"):
                try:
                    fp_resolved.unlink()
                    restored.append(str(fp_resolved))
                except OSError:
                    pass
        return {"tool": entry["tool"], "restored": restored}

    def has_entries(self) -> bool:
        return bool(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
