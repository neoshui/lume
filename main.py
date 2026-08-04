#!/usr/bin/env python3
"""Lume Launcher - PySide6 entry point."""

import os
import sys
import argparse
from pathlib import Path
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


project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def _emit_cli_output(value: str) -> None:
    """Emit CLI output without crashing a windowed PyInstaller executable."""
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        # The Windows ``--windowed`` bootloader exposes a stdout wrapper that
        # can fail during interpreter shutdown even when print() succeeds.
        return
    try:
        print(value)
    except (AttributeError, OSError, ValueError):
        # ``--windowed`` builds may expose a non-writable stdout handle.
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except OSError:
            pass


def _cli(argv: list[str]) -> int | None:
    from lume.version import VERSION
    parser = argparse.ArgumentParser(prog="lume", description="Lume 浮光启动器")
    parser.add_argument("--version", action="store_true", help="显示版本")
    parser.add_argument("--diagnose", action="store_true", help="输出运行诊断信息")
    parser.add_argument("--reset-config", action="store_true", help="重置用户配置")
    args, unknown = parser.parse_known_args(argv[1:])
    if unknown:
        parser.error(f"未知参数: {' '.join(unknown)}")
    if args.version:
        _emit_cli_output(f"Lume {VERSION}")
        return 0
    if args.diagnose:
        from lume.diagnostics import format_diagnostics
        print(format_diagnostics())
        return 0
    if args.reset_config:
        from lume.config import CONFIG_FILE
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        print(f"已重置配置: {CONFIG_FILE}")
        return 0
    return None

if __name__ == "__main__":
    cli_result = _cli(sys.argv)
    if cli_result is not None:
        sys.exit(cli_result)
    from lume.qt_app import run
    sys.exit(run(sys.argv))
