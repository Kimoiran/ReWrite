"""导入导出模块
.writepack 格式 = ZIP 包，包含作品的全部数据。
"""

import json
import zipfile
import hashlib
from pathlib import Path
from typing import Optional

from ..storage.meta import WorkMeta, load_meta, save_meta


def pack_work(work_path: Path, output_path: Path) -> tuple[bool, str]:
    """将作品打包为 .writepack 文件。"""
    meta_path = work_path / "work.json"
    if not meta_path.exists():
        return False, "未找到 work.json，不是有效的作品目录"

    meta = load_meta(meta_path)
    if not meta:
        return False, "work.json 解析失败"

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            files_to_pack = []

            # work.json
            files_to_pack.append(meta_path)

            # chapters/
            chapters_dir = work_path / "chapters"
            if chapters_dir.exists():
                for f in sorted(chapters_dir.iterdir()):
                    if f.suffix == ".html":
                        files_to_pack.append(f)

            # 模块数据文件
            for fname in ["characters.json", "outline.json", "timeline.json"]:
                fp = work_path / fname
                if fp.exists():
                    files_to_pack.append(fp)

            # assets/
            assets_dir = work_path / "assets"
            if assets_dir.exists():
                for f in assets_dir.rglob("*"):
                    if f.is_file():
                        files_to_pack.append(f)

            # 写入文件并计算哈希
            manifest = {
                "version": "1.0",
                "created": meta.updated,
                "title": meta.title,
                "files": [],
            }
            for fpath in files_to_pack:
                rel = fpath.relative_to(work_path)
                data = fpath.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                zf.writestr(str(rel), data)
                manifest["files"].append({
                    "path": str(rel),
                    "size": len(data),
                    "sha256": sha,
                })

            # 写入 manifest
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return True, f"打包成功: {output_path.name}"

    except (OSError, zipfile.BadZipFile) as e:
        return False, f"打包失败: {e}"


def unpack_work(pack_path: Path, output_dir: Path) -> tuple[bool, str, Optional[WorkMeta]]:
    """解包 .writepack 到目标目录。"""
    if not pack_path.exists():
        return False, "文件不存在", None

    try:
        with zipfile.ZipFile(pack_path, "r") as zf:
            # 验证 manifest
            if "manifest.json" not in zf.namelist():
                return False, "无效的 writepack 文件（无 manifest）", None

            # 提取所有文件
            zf.extractall(output_dir)

            # 验证哈希（抽样检查前 5 个）
            manifest = json.loads(zf.read("manifest.json"))
            for entry in manifest.get("files", [])[:5]:
                fpath = output_dir / entry["path"]
                if fpath.exists():
                    actual_sha = hashlib.sha256(fpath.read_bytes()).hexdigest()
                    if actual_sha != entry.get("sha256", ""):
                        return False, f"文件校验失败: {entry['path']}", None

            # 读取 WorkMeta
            meta = load_meta(output_dir / "work.json")
            if meta:
                return True, "解包成功", meta
            return True, "解包成功（无元数据）", None

    except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as e:
        return False, f"解包失败: {e}", None
