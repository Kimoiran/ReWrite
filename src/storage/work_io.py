"""作品目录的增删改查操作。"""
import re, shutil, json
from pathlib import Path
from typing import Optional
from .meta import WorkMeta, load_meta, save_meta


def slugify(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    name = re.sub(r'-+', '-', name)
    return name[:120]


# 工作空间 Git 配置文件（替代原来每个作品的 work.json 中的 git 字段）
def _workspace_git_config_path(works_dir: Path) -> Path:
    return works_dir / ".rewrite_git.json"


def load_workspace_git_config(works_dir: Path) -> dict:
    """加载工作空间级 Git 配置。"""
    path = _workspace_git_config_path(works_dir)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"enabled": True, "remote_url": "", "auto_push": False}


def save_workspace_git_config(works_dir: Path, config: dict):
    """保存工作空间级 Git 配置。"""
    path = _workspace_git_config_path(works_dir)
    try:
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        print("保存工作空间 Git 配置失败")


def create_work(works_dir: Path, title: str, work_type: str = "novel",
                modules: list = None, date_era: str = "",
                git_enabled: bool = True, git_remote: str = "") -> Optional[Path]:
    """创建新作品目录和元数据。返回作品路径，失败返回 None。

    Git 现在是工作空间级的：首次建作品时初始化整个 works/ 目录为 Git 仓库。
    """
    dir_name = f"{work_type}-{slugify(title)}"
    work_path = works_dir / dir_name
    if work_path.exists():
        print(f"错误: 作品目录已存在 {work_path}")
        return None
    if not works_dir.exists():
        works_dir.mkdir(parents=True, exist_ok=True)

    try:
        work_path.mkdir(parents=True)
        (work_path / "chapters").mkdir()
        (work_path / ".autosave").mkdir()

        meta = WorkMeta.new(title=title, work_type=work_type, modules=modules,
                            date_era=date_era)
        save_meta(work_path / "work.json", meta)

        # 工作空间 Git 初始化（仅首次）
        if git_enabled:
            _init_workspace_git(works_dir, git_remote)

        return work_path

    except OSError as e:
        print(f"错误: 创建作品失败 {work_path}: {e}")
        if work_path.exists():
            shutil.rmtree(work_path, ignore_errors=True)
        return None


def delete_work(work_path: Path) -> bool:
    if not work_path.exists() or not work_path.is_dir():
        return False
    try:
        shutil.rmtree(work_path)
        return True
    except OSError as e:
        print(f"错误: 删除作品失败 {work_path}: {e}")
        return False


def update_work_meta(work_path: Path, **updates) -> bool:
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
    for child in works_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta_path = child / "work.json"
        if meta_path.exists():
            meta = load_meta(meta_path)
            if meta and meta.title == title:
                return True
    return False


def _init_workspace_git(works_dir: Path, remote_url: str = "") -> bool:
    """初始化整个工作空间目录为 Git 仓库（每个工作空间只有一个仓库）。"""
    from .git_manager import GitManager
    gm = GitManager(works_dir)
    if gm.is_repo():
        # 已存在，更新远程 URL（如果传了新的）
        if remote_url:
            gm.set_remote(remote_url)
        return True
    ok, _ = gm.init()
    if not ok:
        return False
    gm.add_all()
    gm.commit("ReWrite: 初始化作品库")
    # 保存远程 URL 到配置文件（供后续使用）
    if remote_url:
        gm.set_remote(remote_url)
        save_workspace_git_config(works_dir, {"remote_url": remote_url})
    return True
