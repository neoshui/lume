"""Utility functions for Lume Qt UI — color helpers, icon resolution, GNOME shortcut binding."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QFileInfo
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QStyle, QFileIconProvider

from lume.search import SearchResult


GNOME_SHORTCUT_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/lume/"
GNOME_SHORTCUT_SCHEMA = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{GNOME_SHORTCUT_PATH}"
_FILE_ICON_PROVIDER = QFileIconProvider()


def _qcolor(value: str, fallback: str = "#6988b5") -> QColor:
    """Parse a color string into QColor, falling back if invalid."""
    color = QColor(value)
    if color.isValid():
        return color
    color = QColor(fallback)
    return color if color.isValid() else QColor("#6988b5")


def _rgb_text(value: str, fallback: str) -> str:
    """Normalize an R,G,B triple string, clamping values 0-255."""
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) != 3:
        return fallback
    try:
        numbers = [max(0, min(255, int(part))) for part in parts]
    except ValueError:
        return fallback
    return ", ".join(str(number) for number in numbers)


def _mix(color: str, other: str, amount: float) -> str:
    """Blend two CSS color strings by *amount* (0=color, 1=other)."""
    first, second = _qcolor(color), _qcolor(other, other)
    amount = max(0.0, min(1.0, amount))
    r = round(first.red() * (1 - amount) + second.red() * amount)
    g = round(first.green() * (1 - amount) + second.green() * amount)
    b = round(first.blue() * (1 - amount) + second.blue() * amount)
    return QColor(r, g, b).name()


def _icon(value: str) -> QIcon:
    """Resolve an icon by path or theme name, falling back to generic executable."""
    if value:
        clean_value = str(value).split(",", 1)[0].strip().strip('"')
        path = Path(clean_value)
        if path.exists():
            if sys.platform == "win32":
                icon = _FILE_ICON_PROVIDER.icon(QFileInfo(str(path)))
                if not icon.isNull():
                    return icon
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    icon = QIcon.fromTheme(value or "application-x-executable")
    return icon if not icon.isNull() else QIcon.fromTheme("application-x-executable")


def _fallback_icon(result: SearchResult) -> QIcon:
    """Return an appropriate fallback icon per action type."""
    icon = _icon(result.icon)
    if not icon.isNull():
        return icon
    style = QApplication.style()
    if result.action_type == "folder":
        return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
    if result.action_type in ("web", "search"):
        return style.standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon)
    if result.action_type in ("calculator", "timestamp", "note"):
        return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
    return style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)


def _gnome_binding(shortcut: str) -> str:
    """Convert the portable Lume shortcut form to GNOME accelerator syntax."""
    key = shortcut.strip()
    if not key:
        return ""
    parts = key.split("+")
    if len(parts) > 1:
        mods = {"ALT": "<Alt>", "CTRL": "<Control>", "SHIFT": "<Shift>", "LOGO": "<Super>"}
        return "".join(mods.get(p.upper(), "") for p in parts[:-1]) + parts[-1].lower()
    return key.lower()


def register_gnome_shortcut(shortcut: str) -> bool:
    """Create/update the complete GNOME custom keybinding used by Lume."""
    binding = _gnome_binding(shortcut)
    launcher = str(Path.home() / ".local/bin/lume-launcher")
    try:
        current = subprocess.run(
            ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        try:
            paths = ast.literal_eval(current)
        except (ValueError, SyntaxError):
            paths = []
        if GNOME_SHORTCUT_PATH not in paths:
            paths.append(GNOME_SHORTCUT_PATH)
            subprocess.run(
                ["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", repr(paths)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        for key, value in (("name", "Lume Launcher"), ("command", launcher), ("binding", binding)):
            subprocess.run(["gsettings", "set", GNOME_SHORTCUT_SCHEMA, key, value], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False
