"""批注管理 — 支持正文位置标注 + 多模块批注。"""

import json
import uuid
from pathlib import Path


class Annotation:
    """一条批注，章节批注带原文位置。"""

    def __init__(self, annotation_id: str = "",
                 target_type: str = "chapter",
                 target_path: str = "",
                 target_title: str = "",
                 suggestion: str = "",
                 highlight_text: str = "",   # 原文片段
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
        return cls(**d)

    @property
    def type_icon(self) -> str:
        return {"chapter": "📄", "character": "👤", "outline": "📋", "timeline": "📅"}.get(self.target_type, "📌")

    @property
    def type_label(self) -> str:
        return {"chapter": "正文", "character": "人物", "outline": "大纲", "timeline": "时间线"}.get(self.target_type, "其他")


class AnnotationManager:
    def __init__(self, work_path: Path):
        self.work_path = work_path
        self.data_path = work_path / ".annotations.json"
        self.annotations: list[Annotation] = []

    def load(self):
        if self.data_path.exists():
            try:
                data = json.loads(self.data_path.read_text(encoding="utf-8"))
                self.annotations = [Annotation.from_dict(a) for a in data.get("annotations", [])]
            except Exception:
                self.annotations = []
        if not self.annotations:
            self.annotations = []

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
                       start_pos: int = -1, end_pos: int = -1) -> Annotation:
        ann = Annotation(
            target_type=target_type, target_path=target_path, target_title=target_title,
            suggestion=suggestion, highlight_text=highlight_text,
            start_pos=start_pos, end_pos=end_pos,
        )
        self.annotations.append(ann)
        return ann

    def get_chapter_annotations(self, chapter_path: str) -> list[Annotation]:
        return [a for a in self.annotations if a.target_type == "chapter" and a.target_path == chapter_path]

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
