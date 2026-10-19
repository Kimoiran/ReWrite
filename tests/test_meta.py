"""作品元数据（work.json）测试 —— 读写往返与容错。"""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.storage.meta import (
    WorkMeta,
    load_meta,
    module_to_name,
    save_meta,
    type_to_name,
)


class WorkMetaTest(unittest.TestCase):
    def test_chapters_module_is_always_present(self):
        meta = WorkMeta.new("测试书", modules=["characters"])
        self.assertEqual(meta.modules[0], "chapters")
        self.assertIn("characters", meta.modules)

    def test_default_modules(self):
        self.assertEqual(WorkMeta.new("测试书").modules, ["chapters"])

    def test_new_assigns_unique_work_id(self):
        a = WorkMeta.new("甲")
        b = WorkMeta.new("乙")
        self.assertEqual(len(a.work_id), 32)
        self.assertNotEqual(a.work_id, b.work_id)

    def test_new_sets_timestamps_and_cover_color(self):
        meta = WorkMeta.new("测试书")
        self.assertTrue(meta.created)
        self.assertEqual(meta.created, meta.updated)
        self.assertTrue(meta.cover_color.startswith("#"))

    def test_git_dict_is_coerced_to_dataclass(self):
        meta = WorkMeta(title="书", git={"enabled": False,
                                        "remote": {"enabled": True,
                                                   "url": "git@example.com:x/y.git"}})
        self.assertFalse(meta.git.enabled)
        self.assertTrue(meta.git.remote.enabled)
        self.assertEqual(meta.git.remote.url, "git@example.com:x/y.git")

    def test_git_dict_without_remote(self):
        meta = WorkMeta(title="书", git={"enabled": False})
        self.assertFalse(meta.git.enabled)
        self.assertFalse(meta.git.remote.enabled)


class MetaRoundTripTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "work.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_then_load_preserves_fields(self):
        meta = WorkMeta.new("测试书", modules=["chapters", "map"], date_era="神启")
        meta.total_words = 12345
        meta.ai_system_prompt = "文风：冷峻"

        self.assertTrue(save_meta(self.path, meta))
        loaded = load_meta(self.path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, "测试书")
        self.assertEqual(loaded.modules, ["chapters", "map"])
        self.assertEqual(loaded.date_era, "神启")
        self.assertEqual(loaded.total_words, 12345)
        self.assertEqual(loaded.ai_system_prompt, "文风：冷峻")
        self.assertEqual(loaded.work_id, meta.work_id)

    def test_saved_file_is_utf8_without_ascii_escapes(self):
        save_meta(self.path, WorkMeta.new("新生神明与实习教皇"))
        raw = self.path.read_text(encoding="utf-8")
        self.assertIn("新生神明与实习教皇", raw)
        self.assertNotIn("\\u", raw)

    def test_saved_file_is_indented_json(self):
        save_meta(self.path, WorkMeta.new("书"))
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["title"], "书")
        self.assertIn("\n  ", raw)

    def test_load_missing_file_returns_none(self):
        self.assertIsNone(load_meta(self.path))

    def test_load_corrupted_json_returns_none(self):
        self.path.write_text("{ 这不是 JSON", encoding="utf-8")
        self.assertIsNone(load_meta(self.path))

    def test_load_unknown_field_returns_none_instead_of_crashing(self):
        """work.json 混入未知字段时不能让整个启动流程崩掉。"""
        self.path.write_text(json.dumps({"title": "书", "未知字段": 1}),
                             encoding="utf-8")
        self.assertIsNone(load_meta(self.path))

    def test_save_creates_parent_directory(self):
        nested = Path(self._tmp.name) / "作品" / "work.json"
        self.assertTrue(save_meta(nested, WorkMeta.new("书")))
        self.assertTrue(nested.exists())


class DisplayNameTest(unittest.TestCase):
    def test_type_to_name(self):
        self.assertEqual(type_to_name("novel"), "小说")
        self.assertEqual(type_to_name("poem"), "诗歌")

    def test_type_to_name_unknown_falls_back(self):
        self.assertEqual(type_to_name("unknown-type"), "unknown-type")

    def test_module_to_name(self):
        self.assertEqual(module_to_name("chapters"), "章节管理")
        self.assertEqual(module_to_name("ai_assistant"), "AI 写作助手")

    def test_module_to_name_unknown_falls_back(self):
        self.assertEqual(module_to_name("插件"), "插件")


if __name__ == "__main__":
    unittest.main()
