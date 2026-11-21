"""「假装做过」与「只建空章」的检测测试。

真实故障（《天上之仙》第十一章）：模型在回复里写下

    [工具记录] create_chapter "第十一章 化形妖修"：✅ 已创建章节「第十一章 化形妖修」（第 11 章）

但日志里没有任何 create_chapter 调用、`chapters/` 里也没有那个文件——
它是**模仿**我们注入历史的日志格式，凭空声称做过。
"""

import unittest

from src.editor.modules.ai_assistant.providers import looks_fabricated_tool_record


class FabricatedRecordTest(unittest.TestCase):
    def test_detects_fabricated_log_line(self):
        text = '[工具记录] create_chapter "第十一章 化形妖修"：✅ 已创建章节'
        self.assertTrue(looks_fabricated_tool_record(text))

    def test_plain_summary_is_not_fabrication(self):
        """真正写过之后的正常汇报，不能被误判。"""
        self.assertFalse(looks_fabricated_tool_record("第一章已经写好了，约 5000 字。"))

    def test_empty_text(self):
        self.assertFalse(looks_fabricated_tool_record(""))
        self.assertFalse(looks_fabricated_tool_record(None))


class CreateChapterEmptyFlagTest(unittest.TestCase):
    """create_chapter 只建标题时必须报告 ``empty``，调用方据此要求继续写正文。"""

    def setUp(self):
        import os
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest import mock
        from src.storage.meta import WorkMeta, save_meta

        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.work = root / "novel-测试"
        self.work.mkdir()
        save_meta(self.work / "work.json", WorkMeta.new("测试"))
        self._env = mock.patch.dict(os.environ, {"REWRITE_WORKS_DIR": str(root)})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def test_empty_when_no_content(self):
        from src.editor.modules.ai_assistant.skills.chapter_skills import CreateChapterSkill
        result = CreateChapterSkill().execute({"title": "第十一章 化形妖修",
                                               "work": "测试"}, "")
        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("empty"))
        summary = CreateChapterSkill().summarize(result, {})
        self.assertIn("正文仍为空", summary)
        self.assertIn("update_chapter", summary)

    def test_not_empty_when_content_given(self):
        from src.editor.modules.ai_assistant.skills.chapter_skills import CreateChapterSkill
        result = CreateChapterSkill().execute(
            {"title": "第一章", "content": "正文内容", "work": "测试"}, "")
        self.assertTrue(result.get("success"))
        self.assertFalse(result.get("empty"))
        self.assertNotIn("正文仍为空", CreateChapterSkill().summarize(result, {}))


if __name__ == "__main__":
    unittest.main()
