"""技能间共享工具函数。"""

import json
import re as _re
from pathlib import Path


def list_works() -> list:
    """列出所有作品（供 providers.py 使用）。"""
    wd = _works_dir()
    works = []
    for child in sorted(wd.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta = child / "work.json"
        if meta.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                works.append({
                    "name": child.name,
                    "title": m.get("title", child.name),
                    "type": m.get("work_type", ""),
                    "modules": m.get("modules", []),
                    "updated": m.get("updated", ""),
                })
            except Exception:
                pass
    return works


def _works_dir() -> Path:
    import os
    env = os.environ.get("REWRITE_WORKS_DIR", "")
    if env:
        return Path(env)
    try:
        return Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "works"
    except NameError:
        return Path.home() / "Documents" / "ReWrite" / "works"


def _work_path(name: str) -> Path:
    wd = _works_dir()
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name == name or child.name.endswith(f"-{name}"):
            return child
        meta = child / "work.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if data.get("title") == name:
                    return child
            except Exception:
                pass
    for child in wd.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if name.lower() in child.name.lower():
            return child
    return wd / name


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _date_sort_key(date_str: str):
    if not date_str:
        return (1, "", 0)
    if date_str.isdigit():
        return (0, "", int(date_str))
    nums = _re.findall(r'\d+', date_str)
    if nums:
        return (0, "", int(nums[0]))
    return (1, date_str, 0)
