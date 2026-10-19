"""日志组件测试 —— 命名空间、无副作用、文件落盘与轮转配置。"""

import logging
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src.utils import logging_setup
from src.utils.logging_setup import get_log_dir, get_logger, setup_logging


class GetLoggerTest(unittest.TestCase):
    def test_module_logger_under_rewrite_namespace(self):
        self.assertEqual(get_logger("src.utils.stats").name, "rewrite.utils.stats")

    def test_existing_rewrite_namespace_not_doubled(self):
        self.assertEqual(get_logger("rewrite.ai").name, "rewrite.ai")
        self.assertEqual(get_logger("rewrite").name, "rewrite")

    def test_empty_name_returns_root(self):
        self.assertEqual(get_logger("").name, "rewrite")

    def test_get_logger_has_no_filesystem_side_effect(self):
        """导入/取 logger 不得创建日志目录（测试可以安全 import）。"""
        with TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"REWRITE_LOG_DIR": tmp}):
                get_logger("src.some.module")
                self.assertFalse((Path(tmp) / "rewrite.log").exists())

    def test_get_log_dir_respects_env(self):
        with TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"REWRITE_LOG_DIR": tmp}):
                self.assertEqual(get_log_dir(), Path(tmp))


class SetupLoggingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.log_dir = Path(self._tmp.name) / "logs"
        self._env = mock.patch.dict(
            os.environ, {"REWRITE_LOG_DIR": str(self.log_dir)})
        self._env.start()
        self._reset()

    def tearDown(self):
        self._reset()
        self._env.stop()
        self._tmp.cleanup()

    @staticmethod
    def _reset():
        logging_setup._configured = False
        logger = logging.getLogger("rewrite")
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def _flush(self):
        for handler in logging.getLogger("rewrite").handlers:
            handler.flush()

    def test_creates_log_file_and_writes_message(self):
        logger = setup_logging("INFO")
        logger.info("测试日志消息")
        self._flush()

        log_file = self.log_dir / "rewrite.log"
        self.assertTrue(log_file.exists())
        self.assertIn("测试日志消息", log_file.read_text(encoding="utf-8"))

    def test_message_contains_level_and_logger_name(self):
        logger = setup_logging("DEBUG")
        logger.debug("调试消息")
        self._flush()

        content = (self.log_dir / "rewrite.log").read_text(encoding="utf-8")
        self.assertIn("DEBUG", content)
        self.assertIn("[rewrite", content)

    def test_level_filters_below_threshold(self):
        logger = setup_logging("WARNING")
        logger.info("不该出现")
        logger.warning("该出现")
        self._flush()

        content = (self.log_dir / "rewrite.log").read_text(encoding="utf-8")
        self.assertNotIn("不该出现", content)
        self.assertIn("该出现", content)

    def test_setup_is_idempotent(self):
        setup_logging("INFO")
        count = len(logging.getLogger("rewrite").handlers)
        setup_logging("INFO")
        self.assertEqual(len(logging.getLogger("rewrite").handlers), count)

    def test_unwritable_directory_does_not_raise(self):
        """日志目录不可写时只降级为控制台，绝不能让程序起不来。"""
        with mock.patch.object(logging_setup, "get_log_dir",
                               return_value=Path("\0非法路径")):
            logger = setup_logging("INFO")
            self.assertIsInstance(logger, logging.Logger)


class ExcepthookTest(unittest.TestCase):
    def test_install_and_restore(self):
        original = __import__("sys").excepthook
        try:
            logging_setup.install_excepthook()
            self.assertIsNot(__import__("sys").excepthook, original)
        finally:
            __import__("sys").excepthook = original


if __name__ == "__main__":
    unittest.main()
