"""Lume PySide6 entry point — re-exports the run function from the refactored qt package."""

from __future__ import annotations

from lume.qt.main_window import run

__all__ = ["run"]
