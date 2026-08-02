"""全局日志模块（基于 Python 标准库 logging 重构）

提供统一的日志输出能力，终端彩色输出 + 文件持久化双通道，
底层完全基于原生 logging，保证并发线程安全、支持异常堆栈捕获与三方库日志拦截。

通过 ``get_logger`` 获取命名实例，或直接导入全局 ``logger`` 使用。
"""
from __future__ import annotations

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

# ── 级别常量映射 ───────────────────────────────────────────────

LEVEL_MAP: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
    "RESET": "\033[0m",
    "DIM": "\033[2m",
}


def _resolve_log_dir() -> Path:
    """解析日志目录：环境变量 ``LOG_DIR`` → 项目根 ``logs/`` → 当前目录 ``logs/``。"""
    if env_dir := os.getenv("LOG_DIR"):
        return Path(env_dir)

    candidates = [
        Path(__file__).resolve().parent.parent.parent,  # agent_lab/schema/logger.py → 项目根
        Path.cwd(),
    ]
    for c in candidates:
        logs_dir = c / "logs"
        if logs_dir.exists() or (c / "pyproject.toml").exists() or (c / "main.py").exists():
            return logs_dir
    return Path.cwd() / "logs"


LOG_DIR = _resolve_log_dir()


# ── 自定义 ANSI 彩色终端 Formatter ────────────────────────────────

class ColoredTerminalFormatter(logging.Formatter):
    """带 ANSI 彩色着色的终端 Formatter，支持异常堆栈（exc_info=True）渲染。"""

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level_name = record.levelname
        msg = record.getMessage()

        if self.use_color:
            color = _COLORS.get(level_name, "")
            reset = _COLORS["RESET"]
            dim = _COLORS["DIM"]
            line = (
                f"{dim}{timestamp}{reset} "
                f"{color}[{level_name:<7}]{reset} "
                f"{color}{record.name}{reset} "
                f"{msg}"
            )
        else:
            line = f"{timestamp} [{level_name:<7}] {record.name} {msg}"

        # 自动拼接 Traceback 异常堆栈信息
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                line += f"\n{record.exc_text}"

        return line


# ── 全局 Handler 管理 ──────────────────────────────────────────

_console_handler: Optional[logging.StreamHandler] = None
_file_handler: Optional[TimedRotatingFileHandler] = None


def configure(
        level: int | str | None = None,
        use_color: Optional[bool] = None,
        log_dir: Optional[str | Path] = None,
) -> logging.Logger:
    """一键配置全局日志系统。

    挂载控制台 Handler 与按天轮转文件 Handler 到 Root Logger。

    Args:
        level: 日志级别，如 ``"DEBUG"`` / ``logging.INFO``。
        use_color: 是否彩色输出；``None`` 时根据终端是否为 tty 自动判断。
        log_dir: 日志文件目录，默认 ``logs/``（项目根下）。

    Returns:
        全局默认的 ``logging.Logger`` 实例。
    """
    global _console_handler, _file_handler

    root_logger = logging.getLogger()

    # 1. 解析日志级别
    if level is None:
        _log_level_env = os.getenv("LOG_LEVEL", "INFO")
        if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
            _log_level_env = "DEBUG"
        level = LEVEL_MAP.get(_log_level_env.upper(), logging.INFO)
    elif isinstance(level, str):
        level = LEVEL_MAP.get(level.upper(), logging.INFO)

    root_logger.setLevel(level)

    # 2. 清理已有处理器，防止重复挂载导致日志重复打印
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    # 3. 配置文件控制台输出 (StreamHandler)
    if use_color is None:
        use_color = sys.stdout.isatty()

    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setFormatter(ColoredTerminalFormatter(use_color=use_color))
    root_logger.addHandler(_console_handler)

    # 4. 配置按天轮转文件输出 (TimedRotatingFileHandler)
    target_log_dir = Path(log_dir) if log_dir else LOG_DIR
    target_log_dir.mkdir(parents=True, exist_ok=True)

    log_file_path = target_log_dir / "agent.log"

    _file_handler = TimedRotatingFileHandler(
        filename=log_file_path,
        when="MIDNIGHT",      # 每天午夜 0 点自动轮转切分
        interval=1,
        backupCount=30,       # 保留最近 30 天日志
        encoding="utf-8",
    )
    # 文件存储保持纯文本格式（无 ANSI 颜色代码）
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    _file_handler.setFormatter(file_formatter)
    root_logger.addHandler(_file_handler)

    return root_logger


def get_logger(name: str = "Zimomo") -> logging.Logger:
    """获取一个带有指定名称标识的 Logger 实例。

    Args:
        name: 模块名或标识符（建议传入 ``__name__``）。

    Returns:
        标准的 ``logging.Logger`` 实例，继承全局级别与配置。
    """
    return logging.getLogger(name)


# ── 默认初始化（导入即用） ─────────────────────────────────────

# 模块被 import 时自动进行默认初始化
configure()

# 导出全局默认的 logger 变量
logger = get_logger("Zimomo")