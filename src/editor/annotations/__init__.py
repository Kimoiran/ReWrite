"""批注 — 独立的建议管理层(Word 式:建议存于独立文件,按锚点定位,渲染于原文)。

设计:
- 批注存 .annotations.json(不写入正文文件)
- 定位:start_pos/end_pos(纯文本位置)+ highlight_text(原文片段,用于失效重锚定)
- 来源:AI 分析自动生成 / 用户手动创建;与 AI 模块解耦(AI 只作为来源之一)
"""

from .manager import Annotation, AnnotationManager
from .panel import AnnotationListPanel

__all__ = ["Annotation", "AnnotationManager", "AnnotationListPanel"]
