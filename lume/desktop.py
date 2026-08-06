"""Desktop/session capability detection used by platform integrations."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DesktopInfo:
    desktop: str
    session: str
    is_linux: bool
    is_gnome: bool
    is_wayland: bool

    @property
    def needs_gnome_extension(self) -> bool:
        return self.is_linux and self.is_gnome and self.is_wayland

    @property
    def clipboard_backend(self) -> str:
        return "gnome-shell" if self.needs_gnome_extension else "qt"


def detect_desktop(env: Mapping[str, str] | None = None, system: str | None = None) -> DesktopInfo:
    """Detect the desktop/session relevant to Lume integrations."""
    env = env if env is not None else os.environ
    desktop = str(env.get("XDG_CURRENT_DESKTOP", "") or env.get("DESKTOP_SESSION", ""))
    session = str(env.get("XDG_SESSION_TYPE", "")).lower()
    is_wayland = session == "wayland" or (not session and bool(env.get("WAYLAND_DISPLAY")))
    is_gnome = "gnome" in desktop.lower() or "gnome" in str(env.get("DESKTOP_SESSION", "")).lower()
    return DesktopInfo(
        desktop=desktop,
        session=session or ("wayland" if env.get("WAYLAND_DISPLAY") else ""),
        is_linux=(system or sys.platform) == "linux",
        is_gnome=is_gnome,
        is_wayland=is_wayland,
    )
