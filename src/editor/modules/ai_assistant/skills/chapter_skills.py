"""章节技能 — 读取/修改正文。"""

from typing import Any

from .base_skill import Skill
from ._shared import _work_path, _load, _save


class GetChaptersSkill(Skill):
    @property
    def name(self) -> str: return "get_chapters"
    @property
    def description(self) -> str: return "获取作品章节列表"
    @property
    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        chapters_dir = work / "chapters"
        chapters = []
        if chapters_dir.exists():
            for f in sorted(chapters_dir.iterdir()):
                if f.suffix.lower() == ".html" and not f.name.startswith("."):
                    chapters.append({"name": f.stem, "path": str(f.relative_to(work)),
                                     "size": f.stat().st_size})
        return chapters
    def summarize(self, result, args=None):
        return "已读取章节列表"


class ReadChapterSkill(Skill):
    @property
    def name(self) -> str: return "read_chapter"
    @property
    def description(self) -> str: return "读取指定章节的正文内容（HTML）"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chapter": {"type": "string", "description": "章节名（如「第一章」或文件名）"},
            },
            "required": ["chapter"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        chapter = args.get("chapter", "")
        chapters_dir = work / "chapters"
        if chapters_dir.exists():
            for f in chapters_dir.iterdir():
                name = f.stem
                # 匹配: 0001_第一章 → 第一章 / 第一章
                display = name.split("_", 1)[-1] if "_" in name else name
                if display == chapter or name == chapter:
                    return {"content": f.read_text(encoding="utf-8"), "path": str(f.relative_to(work))}
        return {"success": False, "error": f"未找到章节: {chapter}"}
    def summarize(self, result, args=None):
        c = (args or {}).get("chapter", "")
        if "content" in result:
            return f"已读取章节「{c}」({len(result['content'])}字符)"
        return f"❌ 未找到章节「{c}」"


class UpdateChapterSkill(Skill):
    """修改章节正文。注意：diff 确认由 _execute_and_continue 处理，此技能仅做实际写入。"""

    @property
    def name(self) -> str: return "update_chapter"
    @property
    def description(self) -> str: return "修改指定章节的正文内容（HTML 格式），会弹出 diff 对比确认"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chapter": {"type": "string", "description": "章节名（如「第一章」）"},
                "content": {"type": "string", "description": "新的完整 HTML 内容"},
            },
            "required": ["chapter", "content"],
        }
    def execute(self, args, work_name=""):
        """直接写入（调用方已通过 diff 确认）。"""
        work = _work_path(args.get("work", work_name))
        chapter = args.get("chapter", "")
        new_content = args.get("content", "")
        chapters_dir = work / "chapters"

        if not chapters_dir.exists():
            return {"success": False, "error": "chapters 目录不存在"}

        target_path = None
        for f in chapters_dir.iterdir():
            name = f.stem
            display = name.split("_", 1)[-1] if "_" in name else name
            if display == chapter or name == chapter:
                target_path = f
                break

        if not target_path:
            return {"success": False, "error": f"未找到章节: {chapter}"}

        _save(target_path, new_content)
        return {"success": True, "chapter": chapter}

    def summarize(self, result, args=None):
        c = (args or {}).get("chapter", "")
        if result.get("success"):
            return f"✅ 已修改章节「{c}」"
        return f"❌ 修改失败: {result.get('error')}"
