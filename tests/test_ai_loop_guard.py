"""死循环防护 + 记忆降噪测试。

真实故障（《天上之仙》）：AI 对同一章连续调用 ``update_chapter`` 27 次，
其中最后 9 次写入的内容**逐字节相同**（1223 字符 / 983 字），每 9 秒一轮，
只能靠用户按「停止」打断。

两个成因都在这里被钉住：

1. 内容没变化也算「写入成功」→ AI 收到「✅ 已修改章节」就继续下一轮；
2. 历史里塞满了工具回执和空壳 assistant 消息 → 每轮上下文几乎一样 → 输出也一样。
"""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.editor.modules.ai_assistant.agent import filter_substantive_history
from src.storage.meta import WorkMeta, load_meta, save_meta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FilterSubstantiveHistoryTest(unittest.TestCase):
    def test_tool_acks_are_dropped(self):
        messages = [
            {"role": "user", "content": "写第一章"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "1", "type": "function",
                 "function": {"name": "update_chapter", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "1", "content": "✅ 已修改章节「第一章」"},
        ]
        kept = filter_substantive_history(messages)
        self.assertEqual([m["role"] for m in kept], ["user"])

    def test_assistant_text_is_kept(self):
        messages = [
            {"role": "assistant", "content": "第一章写完了，接下来写第二章。"},
        ]
        self.assertEqual(len(filter_substantive_history(messages)), 1)

    def test_empty_assistant_dropped(self):
        messages = [{"role": "assistant", "content": "   "}]
        self.assertEqual(filter_substantive_history(messages), [])

    def test_large_loop_collapses_to_substance(self):
        """27 轮工具往返只应留下真正的对话。"""
        messages = [{"role": "user", "content": "写第一章，5000 字"}]
        for _ in range(27):
            messages.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": "c", "type": "function",
                 "function": {"name": "update_chapter", "arguments": "{}"}}]})
            messages.append({"role": "tool", "tool_call_id": "c",
                             "content": "✅ 已修改章节「第一章 拜师引路」"})
        kept = filter_substantive_history(messages)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["content"], "写第一章，5000 字")

    def test_empty_input(self):
        self.assertEqual(filter_substantive_history([]), [])
        self.assertEqual(filter_substantive_history(None), [])


class CompressSkipsToolAcksTest(unittest.TestCase):
    def test_summary_ignores_tool_messages(self):
        from src.editor.modules.ai_assistant.agent import AIAgent

        agent = AIAgent({}, work_name="")
        agent.history = [{"role": "user", "content": "写《天上之仙》第一章，每章 5000 字"}]
        for i in range(45):
            agent.history.append({"role": "assistant", "content":
                                  f"第{i}次尝试，正在展开开篇场景。"})
            agent.history.append({"role": "tool", "tool_call_id": "c",
                                  "content": "✅ 已修改章节「第一章 拜师引路」"})
        agent._compress()

        summary = str(agent.history[0]["content"])
        self.assertIn("历史对话摘要", summary)
        self.assertNotIn("✅ 已修改章节", summary)
        self.assertIn("5000 字", "\n".join(str(m.get("content", "")) for m in agent.history))


class LengthRulePersistenceTest(unittest.TestCase):
    """篇幅规则要随 work.json 持久化，重启后「每章 5000 字」不该丢。"""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "work.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip(self):
        meta = WorkMeta.new("天上之仙")
        meta.ai_length_rule = "每一章目标篇幅：约 5000 字（允许 ±1000 字自然浮动）"
        self.assertTrue(save_meta(self.path, meta))

        loaded = load_meta(self.path)
        self.assertIn("5000", loaded.ai_length_rule)

    def test_default_is_empty(self):
        self.assertEqual(WorkMeta.new("书").ai_length_rule, "")

    def test_old_work_json_without_field_still_loads(self):
        self.path.write_text(json.dumps({"title": "旧作品"}), encoding="utf-8")
        loaded = load_meta(self.path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.ai_length_rule, "")


def _make_module(tmp: Path):
    """构造一个不接界面的 AIAssistantModule（需要 PySide6 但不需要窗口）。"""
    from src.editor.modules.ai_assistant.module import AIAssistantModule
    from src.storage.meta import save_meta
    chapters = tmp / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    save_meta(tmp / "work.json", WorkMeta.new("测试作品"))
    return AIAssistantModule(tmp), chapters


try:
    from src.editor.modules.ai_assistant.module import AIAssistantModule as _Probe  # noqa: F401
    _IMPORT_ERROR = None
except Exception as e:                                   # pragma: no cover
    _IMPORT_ERROR = e


@unittest.skipIf(_IMPORT_ERROR is not None, f"无法导入 AIAssistantModule: {_IMPORT_ERROR}")
class UnchangedChapterWriteTest(unittest.TestCase):
    """同一章写入相同内容 → 必须判定为「没有变化」，而不是成功。"""

    CHAPTER = "第一章 拜师引路"
    BODY = "# 第一章 拜师引路\n\n合欢宗，云岚洞府。\n\n她跪在暖玉阶前。"

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.module, self.chapters = _make_module(self.root)
        self.chapters_junk = None

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self, body):
        (self.chapters / f"0001_{self.CHAPTER}.md").write_text(body, encoding="utf-8")

    def _write(self, body):
        return self.module._do_chapter_diff(
            {"chapter": self.CHAPTER, "content": body}, auto=True)

    def test_identical_content_is_rejected(self):
        self._seed("# 第一章 拜师引路\n\n（空）")
        first = self._write(self.BODY)
        self.assertTrue(first.get("success"), first)

        second = self._write(self.BODY)          # 同样的内容再写一次
        self.assertFalse(second.get("success"))
        self.assertTrue(second.get("unchanged"))
        self.assertIn("完全一致", second.get("error", ""))

    def test_changed_content_still_writes(self):
        self._seed(self.BODY)
        changed = self.BODY + "\n\n她把头垂得更低。"
        result = self._write(changed)
        self.assertTrue(result.get("success"))
        disk = (self.chapters / f"0001_{self.CHAPTER}.md").read_text(encoding="utf-8")
        self.assertIn("把头垂得更低", disk)

    def test_unchanged_error_mentions_next_step(self):
        """拒绝时要告诉 AI「别重复写」，否则它会换个说法继续撞墙。"""
        self._seed(self.BODY)
        result = self._write(self.BODY)
        self.assertIn("不要重复写入", result.get("error", ""))


if __name__ == "__main__":
    unittest.main()
