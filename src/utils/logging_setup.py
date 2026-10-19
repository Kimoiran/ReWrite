"""轻量日志 —— 标准库 logging，写入 ~/.rewrite/logs/rewrite.log。

设计原则：

- **零依赖**：只用标准库 ``logging`` + ``RotatingFileHandler``。
- **无副作用**：模块导入和 ``get_logger()`` 都不创建目录、不打开文件；
  只有显式调用 :func:`setup_logging` 才会落盘（测试因此可以安全 import）。
- **不可反噬**：日志文件创建失败只降级为控制台输出，绝不影响主流程。
- **可覆盖**：``REWRITE_LOG_DIR`` 指定目录，``REWRITE_LOG_LEVEL`` 指定级别。

用法::

    from src.utils.logging_setup import get_logger
    log = get_logger(__name__)
    log.warning("快照清理失败: %s", err)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 1024 * 1024  # 单个日志文件 1 MB
_BACKUP_COUNT = 3          # 保留 3 份历史，合计约 4 MB

_ROOT_NAME = "rewrite"
_configured = False


def get_log_dir() -> Path:
    """日志目录：优先环境变量，否则 ``<配置目录>/logs``。"""
    env = os.environ.get("REWRITE_LOG_DIR", "").strip()
    if env:
        return Path(env)
    try:
        from ..storage.paths import get_config_dir
        return get_config_dir() / "logs"
    except Exception:  # 配置系统不可用时也不能让日志本身崩掉
        return Path.home() / ".rewrite" / "logs"


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """配置日志：控制台 + 轮转文件。重复调用只生效一次。"""
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if _configured:
        return root
    _configured = True

    level_name = (level or os.environ.get("REWRITE_LOG_LEVEL") or "INFO").upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "rewrite.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except (OSError, ValueError) as e:
        root.warning("无法创建日志文件，仅输出到控制台: %s", e)

    return root


def get_logger(name: str = "") -> logging.Logger:
    """取得模块级 logger。不会触发日志系统初始化。"""
    if not name:
        return logging.getLogger(_ROOT_NAME)
    if name.startswith("src."):
        name = name[4:]
    elif name == "src":
        name = "app"
    if name == _ROOT_NAME or name.startswith(_ROOT_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def install_excepthook() -> None:
    """把未捕获异常写进日志，崩溃不再无声无息。"""
    log = get_logger("crash")
    previous = sys.excepthook

    def _hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc, tb)
            return
        log.error("未捕获异常", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    sys.excepthook = _hook
