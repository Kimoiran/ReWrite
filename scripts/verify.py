"""全量验证：所有模块导入正常。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.editor.window import EditorWindow
from src.editor.editor_widget import EditorWidget
from src.editor.modules.ai_assistant.module import AIAssistantModule
from src.editor.modules.ai_assistant.annotation_manager import Annotation
from src.editor.sync import document_sync
from src.editor.chapter_list import ChapterListPanel
from src.editor.statusbar import EditorStatusBar
from src.editor.search import SearchDialog
from src.editor.modules.outline import OutlineDock, OutlineModule
from src.editor.modules.chapters import ChapterModule
from src.editor.modules.characters import CharacterModule
from src.editor.modules.timeline import TimelineModule
from src.launcher.window import LauncherWindow
from src.ui.titlebar import TitleBar, make_frameless, attach_title_bar
from src.ui.theme import Color, setup_palette, global_stylesheet

print("VERIFY: ALL MODULES IMPORT OK")
print(f"  EditorWidget has apply_sync: {hasattr(EditorWidget, 'apply_sync')}")
print(f"  EditorWidget has content_synced: {hasattr(EditorWidget, 'content_synced')}")
print(f"  Module imports: {len(dir())} symbols loaded")
