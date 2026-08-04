#!/usr/bin/env python3
"""Emit GNOME clipboard changes for the PySide6 Lume frontend.

This intentionally uses the system Python's PyGObject installation.  GNOME's
GDK clipboard signal works on the regular Wayland protocol; unlike wl-paste
watch mode, it does not require the optional data-control protocol.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gdk, GLib


IMAGES = Path.home() / ".local" / "share" / "lume" / "clipboard_images"


def emit(kind: str, payload: str):
    print(f"{kind}\t{payload}", flush=True)


def read_texture(clipboard):
    clipboard.read_texture_async(None, on_texture, None)


def on_texture(clipboard, result, _data):
    try:
        texture = clipboard.read_texture_finish(result)
        if not texture:
            return
        IMAGES.mkdir(parents=True, exist_ok=True)
        path = IMAGES / f"gdk_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
        texture.save_to_png(str(path))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        emit("IMAGE", f"{path}\t{digest}")
    except Exception as exc:
        print(f"texture read failed: {exc}", file=sys.stderr, flush=True)


def on_text(clipboard, result, _data):
    try:
        text = clipboard.read_text_finish(result)
        if text:
            emit("TEXT", base64.b64encode(text.encode("utf-8")).decode("ascii"))
            return
    except Exception:
        pass
    read_texture(clipboard)


def on_changed(clipboard, *_args):
    clipboard.read_text_async(None, on_text, None)


def main() -> int:
    display = Gdk.Display.get_default()
    if display is None:
        print("Gdk.Display is unavailable", file=sys.stderr, flush=True)
        return 2
    clipboard = display.get_clipboard()
    clipboard.connect("changed", on_changed)
    # Capture the current selection too, so a launch does not miss it.
    on_changed(clipboard)
    GLib.MainLoop().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
