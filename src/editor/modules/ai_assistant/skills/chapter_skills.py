"""章节技能 — 读取/创建/修改/重命名/删除正文。"""

import re
from typing import Any

from .base_skill import Skill
from ._shared import _work_path, make_chapter_md


_HTML_TAG_RE = re.compile(r"<[^>]+>")

def _strip_html_tags(text: str) -> str:
    """清理 AI 输出中可能混入的 HTML 标签(工具描述已要求 Markdown,此处兜底):
    <br>/<p> → 换行;<h1>~<h6> → # 标题;其余标签剥离保留内容。"""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h([1-6])\s*>", "", text, flags=re.IGNORECASE)  # 闭合标题标签删除
    text = re.sub(r"<h([1-6])\s*>", lambda m: "#" * int(m.group(1)) + " ",
                  text, flags=re.IGNORECASE)  # 开标题标签 → Markdown 标题
    text = _HTML_TAG_RE.sub("", text)
    return text


def normalize_chapter_content(content: str, fallback_title: str = "") -> str:
    """AI 写入正文前的格式规范化,修复"标题与正文粘连/回车换行消失":

    1. 统一换行符为 \\n;
    2. 剥离 AI 混入的 HTML 标签(<h1>/<p>/<br> 等);
    3. 首行不是 # 标题且给出 fallback_title → 补标题行;
    4. 标题行后强制空行分隔(修复标题与正文连起来);
    5. 相邻普通段落(非列表/引用/代码块)之间补空行——
       md 渲染会把单换行合并,AI 用单换行分段会导致"换行消失"。
    """
    if content is None:
        return ""
    text = str(content).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return text
    text = _strip_html_tags(text).strip()
    if not text:
        return text
    lines = text.split("\n")

    # 首行不是标题且可回退 → 补标题行(去 # 前缀防双重标题)
    if not lines[0].lstrip().startswith("#") and fallback_title.strip():
        fb = fallback_title.lstrip("#").strip()
        if fb:
            lines.insert(0, f"# {fb}")
            lines.insert(1, "")

    out: list[str] = []
    prev_blank = True
    prev_special = False
    need_blank_after_title = False
    in_code = False  # 围栏代码块 ``` 状态:块内不做任何段落化/插空行
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            prev_blank = True
            need_blank_after_title = False  # 已有空行,标题分隔已满足
            continue
        if s.startswith("```"):
            # 围栏代码块:切换状态,内容原样保留(不 strip,保留缩进)
            in_code = not in_code
            out.append(ln)
            prev_blank = False
            prev_special = True
            continue
        if in_code:
            out.append(ln)  # 代码块内原样输出,绝不插空行
            prev_blank = False
            prev_special = True
            continue
        if s.startswith("#"):
            # 标题行:前空行(若相邻)+ 标题 + 延迟补后空行(避免重复)
            if out and out[-1] != "":
                out.append("")
            out.append(s)
            prev_blank = False
            need_blank_after_title = True
            continue
        special = (s.startswith(("- ", "* ", "> "))
                   or ln.startswith("    ")  # 缩进块(用原始行判定)
                   or bool(re.match(r"^\d+[.．、]", s)))  # 有序列表(含两位数)
        if ln[:1] in (" ", "\t") and prev_special:
            special = True  # 上一行是列表/引用/缩进块 → 本缩进行是其续行(不拆散列表项)
        if need_blank_after_title:
            out.append("")  # 标题与正文之间保证空行
            need_blank_after_title = False
            prev_blank = True
        # 相邻非空行之间补空行;仅"特殊行↔特殊行"(连续列表/引用)保持紧凑
        if not prev_blank and not (prev_special and special):
            out.append("")  # 单换行 → 段落分隔
        out.append(s)
        prev_blank = False
        prev_special = special
    return "\n".join(out).strip() + "\n"


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
                if f.suffix.lower() in (".md", ".html") and not f.name.startswith("."):
                    chapters.append({"name": f.stem, "path": str(f.relative_to(work)),
                                     "size": f.stat().st_size, "format": f.suffix.lower().lstrip(".")})
        return {"chapters": chapters}
    def summarize(self, result, args=None):
        return "已读取章节列表"


class ReadChapterSkill(Skill):
    @property
    def name(self) -> str: return "read_chapter"
    @property
    def description(self) -> str: return "读取指定章节的正文内容(Markdown 纯文本)"
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
    """创建新章节。自动分配序号，生成 Markdown 文件。"""

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
                "content": {"type": "string", "description": "（可选）初始正文（Markdown），不填则只生成标题"},
            },
            "required": ["title"],
        }
    def execute(self, args, work_name=""):
        work = _work_path(args.get("work", work_name))
        title = args.get("title", "").strip()
        if not title:
            return {"success": False, "error": "章节标题不能为空"}
        if not (work / "work.json").exists():
            # 作品目录无效(含非法 work 名回退路径):直接报错,不创建隐藏目录
            return {"success": False, "error": "未找到作品目录"}

        chapters_dir = work / "chapters"
        if not chapters_dir.exists():
            chapters_dir.mkdir(parents=True)

        # 确定下一个序号
        max_order = 0
        for f in chapters_dir.iterdir():
            if f.suffix.lower() in (".md", ".html") and not f.name.startswith("."):
                stem = f.stem
                order_part = stem.split("_", 1)[0] if "_" in stem else ""
                if order_part.isdigit():
                    max_order = max(max_order, int(order_part))
        next_order = max_order + 1

        safe_title = re.sub(r'[\\/:*?"<>|]', "", title).strip()[:80]
        filename = f"{next_order:04d}_{safe_title}.md"
        filepath = chapters_dir / filename

        content = args.get("content", "")
        md = make_chapter_md(safe_title, content)

        filepath.write_text(md, encoding="utf-8")
        return {"success": True, "title": safe_title, "order": next_order,
                "path": str(filepath.relative_to(work))}

    def summarize(self, result, args=None):
        if result.get("success"):
            return f"✅ 已创建章节「{result['title']}」（第 {result['order']} 章）"
        return f"❌ 创建失败: {result.get('error')}"


class UpdateChapterSkill(Skill):
    """修改章节正文。注意：diff 确认由 module 层处理，此技能仅做实际写入。"""

    @property
    def name(self) -> str: return "update_chapter"
    @property
    def description(self) -> str:
        return ("修改指定章节的正文内容(Markdown 纯文本:标题用 # 开头,段落间用空行分隔,"
                "禁止使用任何 HTML 标签)。用户要求写/续写/重写/修改正文时，"
                "必须调用本工具把正文写入文件——不要在聊天回复中直接输出正文。"
                "会弹出 diff 对比确认。")
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "chapter": {"type": "string", "description": "章节名（如「第一章」）"},
                "content": {"type": "string", "description": "新的完整 Markdown 纯文本内容(标题用 # 开头,段落间空行,禁止 HTML 标签)"},
            },
            "required": ["chapter", "content"],
        }
    def execute(self, args, work_name=""):
        """直接写入(调用方已通过 diff 确认)。"""
        work = _work_path(args.get("work", work_name))
        chapter = args.get("chapter", "")
        new_content = args.get("content", "")
        if not chapter or new_content is None:
            return {"success": False, "error": "chapter 与 content 参数不能为空"}
        if not str(new_content).strip():
            return {"success": False, "error": "content 内容为空"}
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

        # 章节是 Markdown 文本文件,直接写文本(不能用 _save,它会 JSON 序列化损坏内容)
        # 写入前规范化:标题行/段落空行(修复 AI 输出导致的标题粘连与换行消失)
        old_text = ""
        try:
            old_text = target_path.read_text(encoding="utf-8")
        except OSError:
            pass
        fallback = (old_text.splitlines()[0].lstrip("#").strip()
                    if old_text.strip() and old_text.splitlines()[0].lstrip().startswith("#")
                    else display)
        new_content = normalize_chapter_content(new_content, fallback)
        if not new_content.strip():
            # 规范化后为空(如内容只有 <br> 等标签)→ 不写入,避免空章节
            return {"success": False, "error": "content 规范化后为空(仅含标签/空白),未写入"}
        target_path.write_text(new_content, encoding="utf-8")
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

        # 保留序号与原后缀(避免 .md 章节被改写成 .html 造成格式漂移)
        order = target.stem.split("_", 1)[0] if "_" in target.stem else ""
        safe_name = re.sub(r'[\\/:*?"<>|]', "", new_name).strip()[:80]
        ext = target.suffix if target.suffix.lower() in (".md", ".html") else ".md"
        if order:
            new_filename = f"{int(order):04d}_{safe_name}{ext}"
        else:
            new_filename = f"{safe_name}{ext}"

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
