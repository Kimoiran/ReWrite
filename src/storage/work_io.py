"""作品目录的增删改查操作。"""

import re
import shutil
from pathlib import Path
from typing import Optional

from .meta import WorkMeta, load_meta, save_meta


def slugify(name: str) -> str:
    """将作品名转为安全的目录名。"""
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    name = re.sub(r'-+', '-', name)
    return name[:120]


def create_work(works_dir: Path, title: str, work_type: str = "novel",
                modules: list = None, git_enabled: bool = True,
                git_remote: str = "", git_auto_push: bool = False,
                date_era: str = "") -> Optional[Path]:
    """创建新作品目录和元数据。返回作品路径，失败返回 None。"""
    dir_name = f"{work_type}-{slugify(title)}"
    work_path = works_dir / dir_name

    if work_path.exists():
        print(f"错误: 作品目录已存在 {work_path}")
        return None

    if not works_dir.exists():
        works_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 创建目录结构
        work_path.mkdir(parents=True)
        (work_path / "chapters").mkdir()
        (work_path / ".autosave").mkdir()
        # assets 目录暂不创建，需要时再建

        # 创建元数据
        meta = WorkMeta.new(
            title=title,
            work_type=work_type,
            modules=modules,
            git_enabled=git_enabled,
            git_remote=git_remote,
            git_auto_push=git_auto_push,
            date_era=date_era,
        )
        save_meta(work_path / "work.json", meta)

        # 可选 Git 初始化
        if git_enabled:
            _git_init(work_path, git_remote)

        return work_path

    except OSError as e:
        print(f"错误: 创建作品失败 {work_path}: {e}")
        if work_path.exists():
            shutil.rmtree(work_path, ignore_errors=True)
        return None


def delete_work(work_path: Path) -> bool:
    """删除作品目录。"""
    if not work_path.exists() or not work_path.is_dir():
        return False
    try:
        shutil.rmtree(work_path)
        return True
    except OSError as e:
        print(f"错误: 删除作品失败 {work_path}: {e}")
        return False


def update_work_meta(work_path: Path, **updates) -> bool:
    """选择性更新作品元数据字段。"""
    meta_path = work_path / "work.json"
    meta = load_meta(meta_path)
    if meta is None:
        return False
    for key, value in updates.items():
        if hasattr(meta, key):
            setattr(meta, key, value)
    from datetime import datetime, timezone
    meta.updated = datetime.now(timezone.utc).isoformat()
    return save_meta(meta_path, meta)


def work_exists(works_dir: Path, title: str) -> bool:
    """检查是否已经存在同名作品。"""
    dir_name_pattern = f"-{slugify(title)}"
    for child in works_dir.iterdir():
        if child.is_dir() and dir_name_pattern in child.name:
            return True
    return False


def _git_init(work_path: Path, remote_url: str = "") -> bool:
    """在作品目录初始化 Git 仓库。使用 GitManager。"""
    from .git_manager import GitManager
    gm = GitManager(work_path)
    ok, _ = gm.init()
    if not ok:
        return False
    # 初始提交
    gm.add_all()
    gm.commit("ReWrite: 初始化作品")
    if remote_url:
        gm.set_remote(remote_url)
    return True
