"""全局日志模块

提供统一的日志输出能力，终端彩色输出 + 文件持久化双通道，
支持按级别过滤、按天轮转以及模块级标识。

通过 ``get_logger`` 获取命名实例，或直接导入全局 ``logger`` 使用。
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 级别常量 ──────────────────────────────────────────────────

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

    # 尝试定位项目根（main.py 所在目录的上一级 / agent_lab 的父级）
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


class Logger:
    """轻量级全局日志器 — 终端着色 + 文件持久化。

    特性:
    - 终端：自动着色，非 tty 环境自动关闭颜色
    - 文件：按天轮转（``logs/2026-07-26.log``），自动创建目录
    - 可通过 ``name`` 在日志前缀中标识来源模块
    - 全局可通过 :func:`configure` 统一调整级别与输出目录

    用法::

        from agent_lab.schema.logger import logger

        logger.info("模型初始化完成")
        logger.debug(f"请求参数: {params}")
        logger.error(f"调用失败: {e}")
    """

    def __init__(
            self,
            name: str = "root",
            level: int = logging.INFO,
            use_color: Optional[bool] = None,
            log_dir: Optional[Path] = None,
    ):
        self.name = name
        self.level = level
        self.use_color = use_color if use_color is not None else sys.stdout.isatty()
        self._log_dir = log_dir or LOG_DIR
        self._current_date: str = ""
        self._file_handle = None

    # ── 公开 API ───────────────────────────────────────────────

    def set_level(self, level: int | str) -> None:
        """动态调整日志级别。"""
        if isinstance(level, str):
            level = LEVEL_MAP.get(level.upper(), logging.INFO)
        self.level = level

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log("DEBUG", msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log("INFO", msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log("WARNING", msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log("ERROR", msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log("CRITICAL", msg, *args, **kwargs)

    # ── 内部 ───────────────────────────────────────────────────

    def _get_file_handle(self):
        """获取当天日志文件的句柄，跨天自动切换。"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            if self._file_handle:
                self._file_handle.close()

            self._log_dir.mkdir(parents=True, exist_ok=True)
            log_path = self._log_dir / f"{today}.log"
            self._file_handle = open(log_path, "a", encoding="utf-8")
            self._current_date = today
        return self._file_handle

    def _log(self, level_name: str, msg: str, *args, **kwargs) -> None:
        if LEVEL_MAP.get(level_name, 0) < self.level:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = msg % args if args else msg

        # 终端输出
        if self.use_color:
            color = _COLORS.get(level_name, "")
            reset = _COLORS["RESET"]
            dim = _COLORS["DIM"]
            terminal_line = (
                f"{dim}{timestamp}{reset} "
                f"{color}[{level_name:<7}]{reset} "
                f"{color}{self.name}{reset} "
                f"{formatted}"
            )
        else:
            terminal_line = f"{timestamp} [{level_name:<7}] {self.name} {formatted}"

        print(terminal_line, file=sys.stdout, flush=True)

        # 文件输出（无色）
        file_line = f"{timestamp} [{level_name:<7}] {self.name} {formatted}"
        try:
            fh = self._get_file_handle()
            print(file_line, file=fh, flush=True)
        except OSError:
            pass  # 文件写入失败不影响终端输出


# ── 全局实例 ───────────────────────────────────────────────────

_log_level = os.getenv("LOG_LEVEL", "INFO")
_default_level = LEVEL_MAP.get(_log_level.upper(), logging.INFO)

if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
    _default_level = logging.DEBUG

logger = Logger(name="SocketAgent", level=_default_level)


# ── 便捷函数 ───────────────────────────────────────────────────

def configure(
        level: int | str | None = None,
        use_color: Optional[bool] = None,
        log_dir: Optional[str] = None,
) -> Logger:
    """一键配置全局日志器。

    Args:
        level: 日志级别，如 ``"DEBUG"`` / ``logging.INFO``。
        use_color: 是否彩色输出；``None`` 自动判断。
        log_dir: 日志文件目录，默认 ``logs/``（项目根下）。

    Returns:
        全局 ``logger`` 实例。
    """
    if level is not None:
        logger.set_level(level)
    if use_color is not None:
        logger.use_color = use_color
    if log_dir is not None:
        logger._log_dir = Path(log_dir)
        logger._current_date = ""  # 强制下次重新打开文件
    return logger


def get_logger(name: str) -> Logger:
    """获取一个带名称前缀的子日志器。

    Args:
        name: 模块名或标识符。

    Returns:
        新的 Logger 实例，共享全局级别与目录配置。写入同一个日志文件。
    """
    return Logger(
        name=name,
        level=logger.level,
        use_color=logger.use_color,
        log_dir=logger._log_dir,
    )
