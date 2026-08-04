"""Lume Application - main GTK application."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Gio, Gdk

from lume.config import load_config
from lume.tools.clipboard import ClipboardWatcher


class LumeApplication(Gtk.Application):
    """Lume GNOME Launcher application."""

    def __init__(self):
        super().__init__(
            application_id="com.lume.launcher",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._config = load_config()
        self._clipboard = None
        self._launcher_window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._load_css()

        # Start clipboard
        self._clipboard = ClipboardWatcher(
            max_entries=self._config.get("clipboard_max_entries", 50)
        )
        self._clipboard.start()
        print("Clipboard watcher started.")

        # GNOME custom keybindings run this app to trigger activation.
        toggle_action = Gio.SimpleAction.new("toggle", None)
        toggle_action.connect("activate", lambda *_: self._on_shortcut_activated())
        self.add_action(toggle_action)

        self.hold()

        shortcut = self._config.get("shortcut", "ALT+space")
        print(f"Lume Launcher ready. Press {shortcut} to open.")

    def _load_css(self):
        import os as _os
        from gi.repository import Gio as _Gio
        css_provider = Gtk.CssProvider()
        for p in (
            _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "lume", "resources", "style.css")),
            _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "resources", "style.css")),
        ):
            if _os.path.exists(p):
                try:
                    css_provider.load_from_file(_Gio.File.new_for_path(p))
                    display = Gdk.Display.get_default()
                    if display:
                        Gtk.StyleContext.add_provider_for_display(
                            display, css_provider,
                            Gtk.STYLE_PROVIDER_PRIORITY_USER,
                        )
                        print(f"CSS loaded from: {p}")
                    break
                except Exception as e:
                    print(f"CSS load error: {e}")

    def do_activate(self):
        self._on_shortcut_activated()

    def _on_shortcut_activated(self):
        print("DEBUG: Shortcut activated", flush=True)
        try:
            if self._launcher_window and self._launcher_window.get_visible():
                self._launcher_window.hide()
            else:
                self._show_launcher()
        except Exception as e:
            import traceback
            print(f"ERROR in shortcut handler: {e}")
            traceback.print_exc()

    def _show_launcher(self):
        if not self._launcher_window:
            from lume.window import LauncherWindow
            self._launcher_window = LauncherWindow(
                application=self,
                clipboard_watcher=self._clipboard,
                config=self._config,
                on_shortcut_changed=self._on_shortcut_changed,
            )
        self._launcher_window.show_launcher()
        print("DEBUG: Launcher shown", flush=True)

    def _on_shortcut_changed(self, new_shortcut):
        print(f"ℹ️ 快捷键已更改为 {new_shortcut}，重启 Lume 后生效。")

    def do_shutdown(self):
        if self._clipboard:
            self._clipboard.stop()
        Gtk.Application.do_shutdown(self)
