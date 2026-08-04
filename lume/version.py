"""Build and runtime identity for Lume."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.1.0"
APP_NAME = "Lume"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def runtime_identity() -> dict[str, str]:
    """Return stable identity fields useful in diagnostics and bug reports."""
    frozen = bool(getattr(sys, "frozen", False))
    executable = Path(sys.executable).resolve()
    return {
        "app": APP_NAME,
        "version": VERSION,
        "mode": "frozen" if frozen else "source",
        "executable": str(executable),
        "project_root": str(PROJECT_ROOT),
        "pid": str(os.getpid()),
        "python": sys.version.split()[0],
        "built_at": os.environ.get("LUME_BUILD_TIME", "development"),
    }


def build_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
