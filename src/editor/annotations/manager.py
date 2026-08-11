"""批注管理 — 支持正文位置标注 + 多模块批注(独立于 AI 模块)。"""

import json
import re as _re
import uuid
from pathlib import Path


class Annotation:
    """一条批注，章节批注带原文位置与锚点文本。"""

    def __init__(self, annotation_id: str = "",
                 target_type: str = "chapter",
                 target_path: str = "",
                 target_title: str = "",
                 suggestion: str = "",
                 highlight_text: str = "",   # 原文片段(锚点,编辑后重定位用)
                 start_pos: int = -1,        # 在纯文本中的起始位置
                 end_pos: int = -1,          # 在纯文本中的结束位置
                 status: str = "pending",
                 source: str = "ai"):
        self.id = annotation_id or uuid.uuid4().hex[:12]
        self.target_type = target_type
        self.target_path = target_path
        self.target_title = target_title
        self.suggestion = suggestion
        self.highlight_text = highlight_text
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.status = status
        self.source = source

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_path": self.target_path,
            "target_title": self.target_title,
            "suggestion": self.suggestion,
            "highlight_text": self.highlight_text,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "status": self.status,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        # 兼容历史存储:to_dict 输出 "id",构造参数为 annotation_id
        if "id" in d and "annotation_id" not in d:
            d = dict(d)
            d["annotation_id"] = d.pop("id")
        # 字段类型校验(恶意/损坏数据丢弃非法项,避免 TypeError 中断功能)
        for k in ("start_pos", "end_pos"):
            if not isinstance(d.get(k), int):
                return None
        for k in ("annotation_id", "target_type", "target_path",
                  "target_title", "suggestion", "highlight_text",
                  "status", "source"):
            if not isinstance(d.get(k), str):
                return None
        try:
            return cls(**d)
        except (TypeError, ValueError):
            return None

    @property
    def type_icon(self) -> str:
        return {"chapter": "📄", "character": "👤", "outline": "📋",
                "timeline": "📅"}.get(self.target_type, "📌")

    @property
    def type_label(self) -> str:
        return {"chapter": "正文", "character": "人物", "outline": "大纲",
                "timeline": "时间线"}.get(self.target_type, "其他")


# 标点容错搜索:忽略常见中英标点后匹配
_PUNCT = '，。！？、；：""''「」【】（）《》.,;:!?()'


def _strip_punct(text: str) -> str:
    return "".join(ch for ch in text if ch not in _PUNCT)


def _find_text(plain_text: str, search_text: str) -> tuple[int, int]:
    """在纯文本中搜索原文片段(带标点容错),返回 (start, end);未找到 (-1,-1)。

    容错路径:去标点后匹配,但返回的索引映射回原文本位置(避免坐标错位)。
    """
    if not search_text:
        return (-1, -1)
    idx = plain_text.find(search_text)
    if idx >= 0:
        return (idx, idx + len(search_text))
    # 构建去标点字符 → 原文本索引映射
    clean_positions = [i for i, ch in enumerate(plain_text) if ch not in _PUNCT]
    plain_clean = "".join(plain_text[i] for i in clean_positions)
    clean = _strip_punct(search_text)
    if clean:
        idx = plain_clean.find(clean)
        if idx >= 0:
            start = clean_positions[idx]
            end = clean_positions[idx + len(clean) - 1] + 1
            return (start, end)
    return (-1, -1)


class AnnotationManager:
    def __init__(self, work_path: Path):
        self.work_path = work_path
        self.data_path = work_path / ".annotations.json"
        self.annotations: list[Annotation] = []

    @staticmethod
    def _norm_path(work: Path, p: str) -> str:
        """路径归一:绝对路径转为相对作品根的 posix 形式,便于与相对路径匹配。

        旧版本数据存绝对路径;新代码按相对路径匹配,归一后两者兼容。
        """
        try:
            wp = Path(work).resolve()
            pp = Path(p)
            if pp.is_absolute():
                pp = pp.resolve().relative_to(wp)
            return pp.as_posix()
        except (ValueError, OSError):
            return str(p)

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.annotations = [a for a in
                            (Annotation.from_dict(x) for x in data.get("annotations", []))
                            if a is not None]
            except Exception:
                self.annotations = []
        if not self.annotations:
            self.annotations = []
        # 旧数据路径归一化:绝对路径 → 相对作品根(匹配/显示兼容)
        for a in self.annotations:
            a.target_path = self._norm_path(self.work_path, a.target_path)

    def save(self):
        try:
            data = {"annotations": [a.to_dict() for a in self.annotations]}
            self.data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except OSError as e:
            print(f"保存批注失败: {e}")
            return False

    def add_annotation(self, target_type: str, target_path: str, target_title: str,
                       suggestion: str, highlight_text: str = "",
                       start_pos: int = -1, end_pos: int = -1,
                       source: str = "ai") -> Annotation:
        ann = Annotation(
            target_type=target_type, target_path=target_path, target_title=target_title,
            suggestion=suggestion, highlight_text=highlight_text,
            start_pos=start_pos, end_pos=end_pos, source=source,
        )
        self.annotations.append(ann)
        return ann

    def get_chapter_annotations(self, chapter_path: str) -> list[Annotation]:
        key = self._norm_path(self.work_path, chapter_path)
        return [a for a in self.annotations
                if a.target_type == "chapter"
                and self._norm_path(self.work_path, a.target_path) == key]

    def get_by_type(self, target_type: str) -> list[Annotation]:
        return [a for a in self.annotations if a.target_type == target_type]

    def get_pending(self) -> list[Annotation]:
        return [a for a in self.annotations if a.status == "pending"]

    def get_pending_count(self) -> int:
        return sum(1 for a in self.annotations if a.status == "pending")

    def update_status(self, annotation_id: str, status: str) -> bool:
        for a in self.annotations:
            if a.id == annotation_id:
                a.status = status
                self.save()
                return True
        return False

    def delete_annotation(self, annotation_id: str) -> bool:
        self.annotations = [a for a in self.annotations if a.id != annotation_id]
        self.save()
        return True

    def get_sorted(self) -> list[Annotation]:
        pending = [a for a in self.annotations if a.status == "pending"]
        others = [a for a in self.annotations if a.status != "pending"]
        return pending + others

    # ── 锚点重定位(章节编辑后 start_pos 可能漂移/失效) ──

    def relocate_chapter(self, chapter_path: str, plain_text: str):
        """章节内容变化后,用 highlight_text 重新定位该章节的批注。

        位置仍有效(文本与锚点一致)则跳过;失效则重新搜索;
        搜索不到则标记 start_pos=-1(渲染时跳过,保留批注与建议)。
        """
        for a in self.annotations:
            if a.target_type != "chapter" or \
                    self._norm_path(self.work_path, a.target_path) != \
                    self._norm_path(self.work_path, chapter_path):
                continue
            if (a.start_pos >= 0 and a.end_pos > a.start_pos
                    and plain_text[a.start_pos:a.end_pos] == a.highlight_text):
                continue  # 锚点仍有效
            sp, ep = _find_text(plain_text, a.highlight_text)
            if sp >= 0:
                a.start_pos, a.end_pos = sp, ep
            else:
                a.start_pos = a.end_pos = -1
