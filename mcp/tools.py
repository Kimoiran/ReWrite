"""MCP 工具函数 — 可供 AI 助手和 MCP 服务器共同使用。"""

import json
import uuid
import os
from pathlib import Path

def _get_works_dir() -> Path:
    """获取作品目录（延迟计算，确保 env var 在 exe 模式下已设置）。"""
    env_works = os.environ.get("REWRITE_WORKS_DIR", "")
    if env_works:
        return Path(env_works)
    # 源码模式
    try:
        base = Path(__file__).resolve().parent.parent
        return base / "works"
    except NameError:
        # exe 模式且无 env var，尝试用户文档目录
        return Path.home() / "Documents" / "ReWrite" / "works"


def _work_path(name: str) -> Path:
    for child in _get_works_dir().iterdir():
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
    for child in _get_works_dir().iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if name.lower() in child.name.lower():
            return child
    return _get_works_dir() / name


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 工具函数 ──

def list_works(args: dict = None) -> list:
    works = []
    for child in sorted(_get_works_dir().iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        meta_path = child / "work.json"
        if meta_path.exists():
            meta = _load(meta_path)
            works.append({
                "name": child.name,
                "title": meta.get("title", child.name),
                "type": meta.get("work_type", ""),
                "modules": meta.get("modules", []),
                "updated": meta.get("updated", ""),
            })
    return works


def get_characters(args: dict) -> dict:
    return _load(_work_path(args["work"]) / "characters.json")


def update_character(args: dict) -> dict:
    work = _work_path(args["work"])
    data = _load(work / "characters.json")
    nodes = data.get("nodes") or data.get("characters") or []
    name, field, value = args["name"], args["field"], args["value"]

    VALID_FIELDS = {"name", "aliases", "age", "gender", "occupation",
                    "appearance", "personality", "background", "goals", "notes"}
    if field not in VALID_FIELDS:
        return {"success": False, "error": f"不支持字段: {field}"}

    def _find(nodes):
        for n in nodes:
            if n.get("name") == name and not n.get("is_group"):
                return n
            if n.get("children"):
                f = _find(n["children"])
                if f:
                    return f
        return None

    node = _find(nodes)
    if not node:
        return {"success": False, "error": f"未找到角色: {name}"}

    old = node.get(field, "")
    node[field] = value
    _save(work / "characters.json", {"nodes": nodes})
    return {"success": True, "name": name, "field": field, "old": old, "new": value}


def _find_group(nodes, name):
    """在树中查找分组。"""
    for n in nodes:
        if n.get("is_group") and n.get("name") == name:
            return n
        if n.get("children"):
            found = _find_group(n["children"], name)
            if found:
                return found
    return None


def create_character(args: dict) -> dict:
    work = _work_path(args["work"])
    data = _load(work / "characters.json")
    nodes = data.get("nodes") or data.get("characters") or []
    new_id = uuid.uuid4().hex[:12]

    entry = {
        "id": new_id, "name": args["name"], "is_group": args.get("is_group", False),
        "aliases": args.get("aliases", ""), "age": args.get("age", ""),
        "gender": args.get("gender", ""), "occupation": args.get("occupation", ""),
        "appearance": args.get("appearance", ""), "personality": args.get("personality", ""),
        "background": args.get("background", ""), "goals": args.get("goals", ""),
        "notes": args.get("notes", ""), "relationships": [], "children": [],
    }

    # 处理 group 参数：自动创建或查找分组
    group_name = args.get("group", "")
    if group_name:
        parent = _find_group(nodes, group_name)
        if parent:
            parent.setdefault("children", []).append(entry)
        else:
            # 创建分组
            group_id = uuid.uuid4().hex[:12]
            group_node = {
                "id": group_id, "name": group_name, "is_group": True,
                "children": [entry]}
            nodes.append(group_node)
    else:
        parent_id = args.get("parent_id", "")
        if parent_id:
            def _find(nodes):
                for n in nodes:
                    if n["id"] == parent_id:
                        return n
                    if n.get("children"):
                        f = _find(n["children"])
                        if f:
                            return f
                return None
            parent = _find(nodes)
            (parent.setdefault("children", []) if parent else nodes).append(entry)
        else:
            nodes.append(entry)

    _save(work / "characters.json", {"nodes": nodes})
    return {"id": new_id, "name": args["name"], "group": group_name}


def add_group(args: dict) -> dict:
    return create_character({**args, "is_group": True})


def get_outline(args: dict) -> dict:
    return _load(_work_path(args["work"]) / "outline.json")


def update_outline_entry(args: dict) -> dict:
    work = _work_path(args["work"])
    data = _load(work / "outline.json")
    entries = data.get("entries", [])
    name, field, value = args["name"], args["field"], args["value"]
    if field not in ("title", "content", "status"):
        return {"success": False, "error": f"不支持字段: {field}"}

    def _find(entries):
        for e in entries:
            if e.get("title") == name:
                return e
            if e.get("children"):
                f = _find(e["children"])
                if f:
                    return f
        return None

    entry = _find(entries)
    if not entry:
        return {"success": False, "error": f"未找到: {name}"}
    entry[field] = value
    _save(work / "outline.json", {"entries": entries})
    return {"success": True, "name": name, "field": field, "new": value}


def get_timeline(args: dict) -> dict:
    return _load(_work_path(args["work"]) / "timeline.json")


def update_timeline_event(args: dict) -> dict:
    work = _work_path(args["work"])
    data = _load(work / "timeline.json")
    events = data.get("events", [])
    name = args.get("title") or args.get("name", "")
    for e in events:
        if e.get("title") == name:
            e[args["field"]] = args["value"]
            _save(work / "timeline.json", {"events": events})
            return {"success": True}
    return {"success": False, "error": f"未找到: {name}"}


def get_worldview(args: dict) -> dict:
    return _load(_work_path(args["work"]) / "worldview.json")


def create_worldview_entry(args: dict) -> dict:
    work = _work_path(args["work"])
    data = _load(work / "worldview.json")
    entries = data.get("entries", [])
    entry = {"id": uuid.uuid4().hex[:12], "title": args["title"],
             "content": args.get("content", "<p></p>"), "children": [], "order": len(entries)}
    if args.get("parent_title"):
        def _find(entries):
            for e in entries:
                if e.get("title") == args["parent_title"]:
                    return e
                if e.get("children"):
                    f = _find(e["children"])
                    if f:
                        return f
            return None
        parent = _find(entries)
        (parent.setdefault("children", []) if parent else entries).append(entry)
    else:
        entries.append(entry)
    _save(work / "worldview.json", {"entries": entries})
    return {"id": entry["id"], "title": args["title"]}


def get_chapters(args: dict) -> list:
    chapters_dir = _work_path(args["work"]) / "chapters"
    chapters = []
    if chapters_dir.exists():
        for f in sorted(chapters_dir.iterdir()):
            if f.suffix.lower() == ".html" and not f.name.startswith("."):
                chapters.append({"name": f.stem, "path": str(f.relative_to(chapters_dir.parent)),
                                 "size": f.stat().st_size})
    return chapters


def read_chapter(args: dict) -> str:
    chapter_path = _work_path(args["work"]) / args.get("path", "")
    return chapter_path.read_text(encoding="utf-8") if chapter_path.exists() else ""


# ── 工具注册表 ──

TOOL_FUNCTIONS = {
    "list_works": list_works,
    "get_characters": get_characters,
    "update_character": update_character,
    "create_character": create_character,
    "add_group": add_group,
    "get_outline": get_outline,
    "update_outline_entry": update_outline_entry,
    "get_timeline": get_timeline,
    "update_timeline_event": update_timeline_event,
    "get_worldview": get_worldview,
    "create_worldview_entry": create_worldview_entry,
    "get_chapters": get_chapters,
    "read_chapter": read_chapter,
}


def call_tool(name: str, args: dict = None):
    """统一调用接口，给 AI 助手用。"""
    fn = TOOL_FUNCTIONS.get(name)
    if not fn:
        return {"success": False, "error": f"未知工具: {name}"}
    try:
        return fn(args or {})
    except Exception as e:
        return {"success": False, "error": str(e)}
