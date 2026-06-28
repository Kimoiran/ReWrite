"""章节技能 — 读取/创建/修改/重命名/删除正文。"""

import re
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


class CreateChapterSkill(Skill):
    """创建新章节。自动分配序号，生成带标题的 HTML 文件。"""

    @property
    def name(self) -> str: return "create_chapter"
    @property
    def description(self) -> str: return "创建新章节"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "章节标题（如「第一章」）"},
                "content": {"type": "string", "description": "（可选）初始正文 HTML，不填则只生成标题"},
            },
            "required": ["title"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        title = args.get("title", "").strip()
        if not title:
            return {"success": False, "error": "章节标题不能为空"}

        chapters_dir = work / "chapters"
        if not chapters_dir.exists():
            chapters_dir.mkdir(parents=True)

        # 确定下一个序号
        max_order = 0
        for f in chapters_dir.iterdir():
            if f.suffix.lower() == ".html" and not f.name.startswith("."):
                stem = f.stem
                order_part = stem.split("_", 1)[0] if "_" in stem else ""
                if order_part.isdigit():
                    max_order = max(max_order, int(order_part))
        next_order = max_order + 1

        safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
        filename = f"{next_order:04d}_{safe_title}.html"
        filepath = chapters_dir / filename

        content = args.get("content", "")
        if content:
            html = content
        else:
            html = (
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" '
                '"http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" />'
                '<meta charset="utf-8" />'
                '<style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "hr { height: 1px; border-width: 0; }\n"
                "li.unchecked::marker { content: \"\\2610\"; }\n"
                "li.checked::marker { content: \"\\2612\"; }\n"
                '</style></head><body style="'
                "font-family:'Microsoft YaHei UI','Microsoft YaHei','Segoe UI','sans-serif';"
                " font-size:14px; font-weight:400; font-style:normal;\">\n"
                f'<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; '
                f'margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
                f'<span style=" font-size:17pt; font-weight:700;">{safe_title}</span></p>\n'
                "</body></html>"
            )

        filepath.write_text(html, encoding="utf-8")
        return {"success": True, "title": safe_title, "order": next_order,
                "path": str(filepath.relative_to(work))}

    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已创建章节「{result['title']}」（第 {result['order']} 章）"
        return f"❌ 创建失败: {result.get('error')}"


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


class RenameChapterSkill(Skill):
    @property
    def name(self) -> str: return "rename_chapter"
    @property
    def description(self) -> str: return "重命名章节"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chapter": {"type": "string", "description": "当前章节名"},
                "new_name": {"type": "string", "description": "新章节名"},
            },
            "required": ["chapter", "new_name"],
        }
    def execute(self, args, work_name=""):
        import os as _os
        work = _work_path(args.get("work", work_name))
        chapter = args.get("chapter", "")
        new_name = args.get("new_name", "")
        chapters_dir = work / "chapters"

        if not chapters_dir.exists():
            return {"success": False, "error": "chapters 目录不存在"}

        target = None
        for f in chapters_dir.iterdir():
            display = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
            if display == chapter or f.stem == chapter:
                target = f
                break

        if not target:
            return {"success": False, "error": f"未找到章节: {chapter}"}

        # 保留序号
        order = target.stem.split("_", 1)[0] if "_" in target.stem else ""
        safe_name = re.sub(r'[\\/:*?"<>|]', "", new_name).strip()[:80]
        if order:
            new_filename = f"{int(order):04d}_{safe_name}.html"
        else:
            new_filename = f"{safe_name}.html"

        new_path = chapters_dir / new_filename
        _os.rename(str(target), str(new_path))
        return {"success": True, "old_name": chapter, "new_name": safe_name,
                "path": str(new_path.relative_to(work))}

    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已重命名章节「{result['old_name']}」→「{result['new_name']}」"
        return f"❌ 重命名失败: {result.get('error')}"


class DeleteChapterSkill(Skill):
    @property
    def name(self) -> str: return "delete_chapter"
    @property
    def description(self) -> str: return "删除指定章节"
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chapter": {"type": "string", "description": "章节名"},
            },
            "required": ["chapter"],
        }
    def execute(self, args, work_name=""):
        import os as _os
        work = _work_path(args.get("work", work_name))
        chapter = args.get("chapter", "")
        chapters_dir = work / "chapters"

        if not chapters_dir.exists():
            return {"success": False, "error": "chapters 目录不存在"}

        target = None
        for f in chapters_dir.iterdir():
            display = f.stem.split("_", 1)[-1] if "_" in f.stem else f.stem
            if display == chapter or f.stem == chapter:
                target = f
                break

        if not target:
            return {"success": False, "error": f"未找到章节: {chapter}"}

        _os.remove(str(target))
        return {"success": True, "name": chapter}

    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已删除章节「{(args or {}).get('chapter', '')}」"
        return f"❌ 删除失败: {result.get('error')}"
