"""Lume floating launcher window - a GTK4 window with no decorations."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")

from gi.repository import Gtk, Gdk, GLib, Gio


class LauncherWindow(Gtk.Window):
    """A floating, centered launcher window that appears on global shortcut."""

    def __init__(self, application, clipboard_watcher, config, on_shortcut_changed=None,
                 suspend_shortcut=None, resume_shortcut=None):
        super().__init__(application=application)
        self._config = config
        self._clipboard = clipboard_watcher
        self._on_shortcut_changed = on_shortcut_changed
        self._suspend_shortcut = suspend_shortcut
        self._resume_shortcut = resume_shortcut
        self._settings_window = None
        self._was_shown = False

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_title("Lume Launcher")
        self.set_css_classes(["launcher-window"])
        self.connect("close-request", self._on_close_request)

        from lume.launcher import LauncherUI

        self._launcher_ui = LauncherUI(
            clipboard_watcher=clipboard_watcher,
            config=config,
            on_select=self._on_action,
            open_settings=self._open_settings,
        )
        self._launcher_ui.set_halign(Gtk.Align.CENTER)
        self._launcher_ui.set_valign(Gtk.Align.CENTER)
        self.set_child(self._launcher_ui)

        clipboard_watcher.set_on_update(self._launcher_ui.on_clipboard_updated)

        key_controller = Gtk.EventControllerKey()
        key_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Window size — outer margin is handled via CSS .launcher-box margin
        self.set_default_size(
            config.get("launcher_width", 680),
            config.get("launcher_height", 720)
        )

    def _on_action(self, action_type, action_data):
        if action_type == "close":
            self.hide()
        elif action_type != "clipboard":
            self.hide()

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def _open_settings(self):
        try:
            if self._settings_window is not None:
                try:
                    self._settings_window.present()
                    return
                except Exception:
                    self._settings_window = None

            from lume.settings_ui import SettingsWindow
            self._settings_window = SettingsWindow(
                parent_window=self,
                on_save=self._on_settings_saved,
                suspend_shortcut=self._suspend_shortcut,
                resume_shortcut=self._resume_shortcut,
                on_close=self._on_settings_closed,
            )
            self._settings_window.present()
        except Exception as e:
            import traceback
            print(f"ERROR opening settings: {e}")
            traceback.print_exc()
            self._settings_window = None

    def _on_settings_saved(self, new_config):
        try:
            old_shortcut = self._config.get("shortcut")
            new_shortcut = new_config.get("shortcut")
            self._config = new_config
            self._launcher_ui._config = new_config

            from lume.launcher import reload_css
            reload_css(new_config)

            w = new_config.get("launcher_width", 680)
            h = new_config.get("launcher_height", 720)
            self.set_default_size(w, h)
            self.set_size_request(w, h)
            self._launcher_ui.update_paned_position()

            if old_shortcut != new_shortcut and self._on_shortcut_changed:
                self._on_shortcut_changed(new_shortcut)

            self._launcher_ui._rebuild_results()
        except Exception as e:
            import traceback
            print(f"ERROR in settings save: {e}")
            traceback.print_exc()
        self._settings_window = None

    def _on_settings_closed(self):
        self._settings_window = None

    def _on_close_request(self, _window):
        self.hide()
        return True

    def show_launcher(self):
        print(f"DEBUG: show_launcher() called: _was_shown={self._was_shown}, realized={self.get_realized()}, visible={self.get_visible()}")
        if self._was_shown and not self.get_realized():
            print("DEBUG: show_launcher guard triggered — window unrealized, aborting")
            return
        self._was_shown = True
        w = self._config.get("launcher_width", 680)
        h = self._config.get("launcher_height", 720)
        self.set_default_size(w, h)
        self.set_size_request(w, h)
        self._launcher_ui.update_paned_position()
        self._launcher_ui.clear_search()
        print(f"DEBUG: calling present()")
        self.present()
        print(f"DEBUG: after present(), visible={self.get_visible()}")
        self._launcher_ui.focus_search()
        print(f"DEBUG: show_launcher() done")
