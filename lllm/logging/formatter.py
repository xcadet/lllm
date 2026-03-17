"""
Colored terminal formatter and setup_logging() convenience function.

Uses only stdlib ANSI escapes — no third-party dependencies.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Logging formatter that adds ANSI color codes by log level."""

    _COLORS = {
        logging.DEBUG:    "\033[90m",      # dark gray
        logging.INFO:     "\033[92m",      # green
        logging.WARNING:  "\033[93m",      # yellow
        logging.ERROR:    "\033[91m",      # red
        logging.CRITICAL: "\033[1;91m",    # bold red
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        formatted = super().format(record)
        return f"{color}{formatted}{self._RESET}"


def setup_logging(
    level: str = "INFO",
    fmt: Optional[str] = None,
    color: bool = True,
) -> None:
    """
    Configure the root ``lllm`` logger with a StreamHandler.

    Calling this is optional — users can configure Python logging however
    they want.  This helper provides sensible defaults.

    Args:
        level: Log level string — "DEBUG", "INFO", "WARNING", "ERROR".
        fmt:   Format string.  Defaults to "%(levelname)s  %(name)s — %(message)s".
        color: Whether to use the ColoredFormatter (default True).
    """
    fmt = fmt or "%(levelname)-8s  %(name)s — %(message)s"

    handler = logging.StreamHandler(sys.stderr)
    formatter_cls = ColoredFormatter if color else logging.Formatter
    handler.setFormatter(formatter_cls(fmt))

    lllm_logger = logging.getLogger("lllm")
    # Avoid adding duplicate handlers if called multiple times
    if not any(isinstance(h, logging.StreamHandler) for h in lllm_logger.handlers):
        lllm_logger.addHandler(handler)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    lllm_logger.setLevel(numeric_level)
