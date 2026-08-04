"""Unified logging for Lume — replaces scattered print() calls.

Usage:
    from lume.log_utils import get_logger
    log = get_logger(__name__)
    log.info("Lume ready")
    log.warning("Config load failed: %s", e)
    log.error("Fatal error", exc_info=True)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_LOG_DIR = Path.home() / ".local" / "share" / "lume"
_LOG_FILE = _LOG_DIR / "lume.log"
_LOG_LEVEL = logging.INFO
_MAX_LOG_BYTES = 2 * 1024 * 1024
_LOG_BACKUPS = 3

_initialized = False


def get_logger(name: str) -> logging.Logger:
    """Get a Lume logger with file + stderr output.

    All loggers are placed under the ``lume.`` namespace so that the
    shared file/stderr handlers on the ``lume`` root propagate correctly.

    The file handler is set up once; subsequent calls only create the
    named logger (no duplicate handlers).
    """
    global _initialized
    if not _initialized:
        _initialized = True
        _setup_root_logger()
    # Ensure every logger is under ``lume.`` so handlers propagate
    if name == "__main__":
        full = "lume.__main__"
    elif not name.startswith("lume"):
        full = f"lume.{name}"
    else:
        full = name
    return logging.getLogger(full)


def set_level(level: int):
    """Override the global log level (e.g. logging.DEBUG)."""
    logging.getLogger("lume").setLevel(level)


def _setup_root_logger():
    """Configure the 'lume' root logger with file and stderr handlers."""
    root = logging.getLogger("lume")
    root.setLevel(_LOG_LEVEL)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(name)s %(lineno)d %(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler (append)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        str(_LOG_FILE), maxBytes=_MAX_LOG_BYTES, backupCount=_LOG_BACKUPS,
        encoding="utf-8", delay=False,
    )
    fh.setLevel(_LOG_LEVEL)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Stderr handler (always show warnings and above in terminal)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    root.addHandler(sh)


# Convenience shortcut
logger = get_logger("lume")
