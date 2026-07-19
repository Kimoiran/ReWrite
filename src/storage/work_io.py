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


def _update_gitignore(works_dir: Path, dir_name: str, exclude: bool):
    """更新 .gitignore：exclude=True 将作品加入忽略列表，False 移除。"""
    gitignore = works_dir / ".gitignore"
    entry = f"/{dir_name}"
    lines = []
    if gitignore.exists():
        lines = gitignore.read_text(encoding="utf-8").splitlines()
    if exclude:
        if entry not in lines:
            lines.append(entry)
    else:
        lines = [l for l in lines if l != entry]
    gitignore.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_work(works_dir: Path, title: str, work_type: str = "novel",
                modules: list = None, date_era: str = "",
                cloud_enabled: bool = False) -> Optional[Path]:
    """创建新作品目录和元数据。返回作品路径，失败返回 None。

    目录命名使用 work_id（UUID 前 8 位），支持同名作品。
    cloud_enabled=False 时写入 .gitignore，不会被提交/推送。
    """
    if not works_dir.exists():
        works_dir.mkdir(parents=True, exist_ok=True)

    # 先生成 meta（含 UUID），用 UUID 命名目录
    meta = WorkMeta.new(title=title, work_type=work_type, modules=modules,
                        cloud_enabled=cloud_enabled, date_era=date_era)
    dir_name = f"{work_type}-{meta.work_id[:8]}"
    work_path = works_dir / dir_name

    if work_path.exists():
        print(f"错误: 作品目录已存在 {work_path}")
        return None

    try:
        # 先更新 .gitignore，再创建目录
        if cloud_enabled:
            _update_gitignore(works_dir, dir_name, exclude=False)
        else:
            _update_gitignore(works_dir, dir_name, exclude=True)

        work_path.mkdir(parents=True)
        (work_path / "chapters").mkdir()
        (work_path / ".autosave").mkdir()

        save_meta(work_path / "work.json", meta)

        # 工作空间 Git 初始化（仅首次）
        _init_workspace_git(works_dir)

        return work_path

    except OSError as e:
        print(f"错误: 创建作品失败 {work_path}: {e}")
        if work_path.exists():
            shutil.rmtree(work_path, ignore_errors=True)
        return None


def set_work_cloud_enabled(work_path: Path, enabled: bool) -> bool:
    """切换作品的云端同步状态。更新 work.json 和 .gitignore。"""
    meta_path = work_path / "work.json"
    meta = load_meta(meta_path)
    if meta is None:
        return False
    meta.cloud_enabled = enabled
    if not save_meta(meta_path, meta):
        return False
    _update_gitignore(work_path.parent, work_path.name, exclude=not enabled)
    return True


def delete_work(work_path: Path) -> bool:
    if not work_path.exists() or not work_path.is_dir():
        return False
    try:
        dir_name = work_path.name
        works_dir = work_path.parent
        shutil.rmtree(work_path)
        # 清理 .gitignore 中的条目
        _update_gitignore(works_dir, dir_name, exclude=False)
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


def _init_workspace_git(works_dir: Path) -> bool:
    """初始化整个工作空间目录为 Git 仓库（每个工作空间只有一个仓库）。"""
    from .git_manager import GitManager
    gm = GitManager(works_dir)
    if gm.is_repo():
        return True
    ok, _ = gm.init()
    if not ok:
        return False
    gm.add_all()
    gm.commit("ReWrite: 初始化作品库")
    return True
