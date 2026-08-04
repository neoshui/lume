#!/usr/bin/env python3
"""Lume GNOME Launcher daemon — GLib MainLoop with portal GlobalShortcuts."""

import sys
import os
import traceback

# Ensure paths (when daemon.py is imported from main.py)
_dir = os.path.dirname(os.path.abspath(__file__))
_proj = os.path.dirname(_dir)
for p in (_proj, _dir):
    if p not in sys.path:
        sys.path.insert(0, p)

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Gdk, GLib, Gio

from lume.config import load_config
from lume.global_shortcut import GlobalShortcutManager
from lume.tools.clipboard import ClipboardWatcher


def main():
    try:
        config = load_config()
        print(f"Lume config loaded: theme={config.get('theme')}, layout={config.get('layout')}")

        clipboard = ClipboardWatcher(
            max_entries=config.get("clipboard_max_entries", 50)
        )
        clipboard.start()
        print("Clipboard watcher started.")

        shortcut = GlobalShortcutManager(
            shortcut=config.get("shortcut", "ALT+space")
        )

        launcher_window = None

        def on_shortcut():
            nonlocal launcher_window
            try:
                from lume.window import LauncherWindow

                if launcher_window is not None:
                    try:
                        if not launcher_window.get_realized():
                            print("DEBUG: window not realized, recreating")
                            launcher_window = None
                    except Exception as e:
                        print(f"DEBUG: window check failed: {e}")
                        launcher_window = None

                if launcher_window and launcher_window.get_visible():
                    print("DEBUG: window already visible, skipping")
                    return
                if not launcher_window:
                    print("DEBUG: creating new launcher window")

                    def _on_sc_changed(new_sc):
                        print(f"ℹ️ 快捷键已更改为 {new_sc}，重启 daemon 后生效。")

                    launcher_window = LauncherWindow(
                        application=None,
                        clipboard_watcher=clipboard,
                        config=config,
                        on_shortcut_changed=_on_sc_changed,
                        suspend_shortcut=shortcut.suspend,
                        resume_shortcut=shortcut.resume,
                    )
                    print("DEBUG: launcher window created")
                print("DEBUG: calling show_launcher()")
                launcher_window.show_launcher()
                print("DEBUG: show_launcher() returned")
            except Exception as e:
                print(f"ERROR in shortcut handler: {e}")
                traceback.print_exc()

        shortcut.set_on_activated(on_shortcut)
        shortcut.setup()

        shortcut_display = config.get("shortcut", "ALT+space")
        print(f"Lume Launcher started. Press {shortcut_display} to open.")

        loop = GLib.MainLoop()
        try:
            loop.run()
        except Exception as e:
            print(f"Main loop error: {e}")
            traceback.print_exc()
    except KeyboardInterrupt:
        print("Lume stopped by user.")
    except Exception as e:
        print(f"FATAL: {e}")
        traceback.print_exc()
    finally:
        try:
            clipboard.stop()
        except Exception:
            pass
        try:
            shortcut.cleanup()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
