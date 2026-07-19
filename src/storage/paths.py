"""路径管理 — 存档位置和配置位置可自定义，支持自动迁移。"""

import json
import shutil
from pathlib import Path
from typing import Optional

# 固定锚点：location.json 始终在 ~/.rewrite/，永不迁移
LOCATION_FILE = Path.home() / ".rewrite" / "location.json"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_works_dir() -> Path:
    """打包后默认为 exe 同目录下的 works/，源码为项目下 works。"""
    import sys
    if getattr(sys, 'frozen', False):
        # 优先 exe 所在目录下的 works/
        exe_dir = Path(sys.executable).parent
        return exe_dir / "works"
    # 源码：由调用方传入项目根
    return Path.cwd() / "works"


def get_default_config_dir() -> Path:
    """配置始终在 ~/.rewrite/。"""
    return Path.home() / ".rewrite"


def load_location_config() -> dict:
    """加载位置配置，返回 {works_path, config_path}。空字符串表示使用默认值。"""
    if LOCATION_FILE.exists():
        try:
            data = json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
            return {
                "works_path": data.get("works_path", ""),
                "config_path": data.get("config_path", ""),
            }
        except (json.JSONDecodeError, OSError):
            pass
    return {"works_path": "", "config_path": ""}


def _sanitize_path(path: str) -> str:
    """清除路径中的不可见 Unicode 控制字符（从文件管理器复制路径时常带）。"""
    import re
    # 移除 Unicode bidi 控制字符、零宽字符等
    return re.sub(r'[‎‏‪-‮⁠⁦-⁩﻿]', '', path).strip()


def save_location_config(works_path: str = "", config_path: str = ""):
    """保存位置配置。"""
    works_path = _sanitize_path(works_path)
    config_path = _sanitize_path(config_path)
    _ensure_dir(LOCATION_FILE.parent)
    LOCATION_FILE.write_text(
        json.dumps({"works_path": works_path, "config_path": config_path},
                    ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _path_log(msg: str):
    """写入路径诊断日志（打包后无终端，只能写文件）。"""
    try:
        log = Path.home() / ".rewrite" / "path_debug.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def get_works_dir(project_root: Path = None) -> Path:
    """获取当前生效的 works 目录。可跨源码/打包环境使用。"""
    loc = load_location_config()
    import sys
    is_frozen = getattr(sys, 'frozen', False)
    _path_log(f"get_works_dir: frozen={is_frozen}, home={Path.home()}, exe={sys.executable if is_frozen else 'N/A'}, location_config={loc}")
    if loc["works_path"]:
        p = Path(_sanitize_path(loc["works_path"]))
        _path_log(f"  -> custom: {p} (exists={p.exists()})")
        return p
    if is_frozen:
        exe_dir = Path(sys.executable).parent
        p = exe_dir / "works"
        _path_log(f"  -> frozen default: {p} (exists={p.exists()})")
        return p
    if project_root is not None:
        p = project_root / "works"
        _path_log(f"  -> source default: {p} (exists={p.exists()})")
        return p
    p = Path.cwd() / "works"
    _path_log(f"  -> cwd fallback: {p} (exists={p.exists()})")
    return p


def get_config_dir() -> Path:
    """获取当前生效的配置目录。"""
    loc = load_location_config()
    if loc["config_path"]:
        return Path(loc["config_path"])
    return Path.home() / ".rewrite"


def migrate_works(new_path: str) -> tuple[bool, str]:
    """迁移作品到新位置。如果目标已存在，合并内容。"""
    new_path = _sanitize_path(new_path)
    if not new_path:
        save_location_config(works_path="")
        return True, "已恢复默认位置"

    dst = Path(new_path)

    # 获取当前作品目录
    loc = load_location_config()
    old = Path(loc["works_path"]) if loc["works_path"] else None
    if old is None:
        import sys
        if getattr(sys, 'frozen', False):
            old = Path(sys.executable).parent / "works"
        else:
            old = Path.cwd() / "works"

    # 新旧路径相同 → 直接更新配置即可
    if (loc["works_path"] and dst.resolve() == Path(loc["works_path"]).resolve()) or \
       (not loc["works_path"] and dst.resolve() == old.resolve()):
        save_location_config(works_path=str(dst.resolve()))
        return True, f"路径未变，已更新配置"

    if not old.exists():
        _ensure_dir(dst)
        save_location_config(works_path=str(dst.resolve()))
        return True, f"已设置作品位置为 {dst}"

    try:
        _ensure_dir(dst)
        # 复制每个作品到目标（合并，不覆盖相同名称的）
        count = 0
        for item in old.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                target = dst / item.name
                if not target.exists():
                    shutil.copytree(item, target)
                    count += 1
                else:
                    count += 1  # 已存在也算成功
        save_location_config(works_path=str(dst.resolve()))
        save_location_config(works_path=str(dst.resolve()))
        return True, f"已迁移 {len(list(dst.iterdir()))} 个作品到 {dst}"
    except (OSError, shutil.Error) as e:
        return False, f"迁移失败：{e}"


def migrate_config(new_path: str) -> tuple[bool, str]:
    """迁移配置文件到新位置。"""
    if not new_path.strip():
        save_location_config(config_path="")
        return True, "已恢复默认配置位置"

    dst = Path(new_path.strip())
    if dst.exists() and any(dst.iterdir()):
        return False, f"目标目录已存在且不为空：{dst}"

    old = Path.home() / ".rewrite"

    if not old.exists():
        _ensure_dir(dst)
        save_location_config(config_path=str(dst.resolve()))
        return True, f"已设置配置位置为 {dst}"

    try:
        _ensure_dir(dst.parent)
        # 只迁移配置文件，不迁移 location.json 自身
        for f in old.iterdir():
            if f.is_file() and f.name != "location.json":
                shutil.copy2(str(f), str(dst / f.name))
        # 迁移 history 子目录
        history_src = old / "history"
        if history_src.exists():
            shutil.copytree(str(history_src), str(dst / "history"), dirs_exist_ok=True)
        save_location_config(config_path=str(dst.resolve()))
        return True, f"已迁移配置到 {dst}（原始 ~/.rewrite 未删除）"
    except (OSError, shutil.Error) as e:
        return False, f"迁移失败：{e}"
