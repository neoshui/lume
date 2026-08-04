#!/usr/bin/env python3
"""Lume Launcher - compatibility entry point wrapper."""

import sys, os
# On Wayland, try native platform plugin (for multi-monitor
# via QWindow::setScreen).  Only fall back to xcb/XWayland when
# the Wayland plugin is unavailable but DISPLAY is set.
if os.environ.get("XDG_SESSION_TYPE") == "wayland" and "QT_QPA_PLATFORM" not in os.environ:
    try:
        from pathlib import Path as _P
        import PySide6 as _P6
        _wp = _P(_P6.__file__).parent / "Qt" / "plugins" / "platforms" / "libqwayland.so"
        if _wp.exists():
            os.environ["QT_QPA_PLATFORM"] = "wayland"
        elif os.environ.get("DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "xcb"
    except Exception:
        if os.environ.get("DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "xcb"


# Ensure the project root is in sys.path
_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from lume.qt_app import run

sys.exit(run(sys.argv))
