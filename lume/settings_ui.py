"""Lume Settings UI - graphical settings editor."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gtk, Gdk, GLib, Pango

from lume.config import load_config, save_config, CONFIG_FILE


def _format_shortcut_display(sc: str) -> str:
    """Display a shortcut string nicely, e.g. 'ALT+space' -> 'Alt + Space'."""
    parts = sc.replace(" ", "").split("+")
    display_parts = [p.capitalize() for p in parts]
    return " + ".join(display_parts)


class SettingsWindow(Gtk.Window):
    """Settings dialog for Lume launcher appearance and behavior."""

    def __init__(self, parent_window=None, on_save=None, suspend_shortcut=None,
                 resume_shortcut=None, on_close=None):
        super().__init__(title="Lume 设置")
        self._on_save = on_save
        self._on_close = on_close
        self._closed_notified = False
        self._config = load_config()
        self._suspend_shortcut = suspend_shortcut
        self._resume_shortcut = resume_shortcut

        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_default_size(540, 600)
        self.set_resizable(False)
        self.connect("close-request", self._on_close_request)
        self.set_css_classes(["settings-window"])
        self._apply_settings_css()

        # Main container
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(16)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        self.set_child(vbox)

        # Title
        title = Gtk.Label(label="Lume 设置")
        title.set_markup("<b>Lume 设置</b>")
        title.set_halign(Gtk.Align.START)
        title.set_margin_bottom(20)
        vbox.append(title)

        # Stack + StackSwitcher for tabs
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)

        # --- Tab 1: 外观 ---
        appearance_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        appearance_box.set_margin_top(8)
        appearance_box.append(self._make_section_label("主题与显示"))

        # Theme presets selector
        from lume.themes import list_themes, get_theme
        theme_names = list_themes()
        saved_preset = self._config.get("theme_preset", "")
        self._initial_theme_preset = (
            saved_preset if saved_preset in theme_names else theme_names[0]
        )
        preset_row = self._make_combo_row("配色方案",
                                          theme_names,
                                          self._initial_theme_preset)
        appearance_box.append(preset_row.box)
        self._theme_preset_combo = preset_row.widget
        self._theme_preset_combo.connect("notify::selected", self._on_theme_preset_changed)
        self._theme_preview = self._make_theme_preview()
        appearance_box.append(self._theme_preview)

        # Theme
        theme_labels = ["跟随系统", "浅色", "深色"]
        theme_values = ["auto", "light", "dark"]
        current_theme = self._config.get("theme", "auto")
        theme_row = self._make_combo_row(
            "主题模式",
            theme_labels,
            theme_labels[theme_values.index(current_theme)]
            if current_theme in theme_values else theme_labels[0],
        )
        appearance_box.append(theme_row.box)
        self._theme_combo = theme_row.widget

        # Panel opacity
        opacity_row = self._make_scale_row("面板透明度", 0.1, 1.0, 0.05,
                                           self._config.get("appearance", {}).get("panel_opacity", 0.88))
        appearance_box.append(opacity_row.box)
        self._opacity_scale = opacity_row.widget

        # Border radius
        radius_row = self._make_spin_row("面板圆角 (px)", 0, 30, 1,
                                        self._config.get("appearance", {}).get("border_radius", 14))
        appearance_box.append(radius_row.box)
        self._radius_spin = radius_row.widget

        # Layout mode
        layout_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        layout_row.set_css_classes(["settings-row"])
        layout_lbl = Gtk.Label(label="结果布局")
        layout_lbl.set_size_request(124, -1)
        layout_lbl.set_halign(Gtk.Align.START)
        layout_row.append(layout_lbl)
        current_layout = self._config.get("layout", "list")
        self._layout_combo = Gtk.DropDown.new_from_strings(["列表 (List)", "网格 (Grid)"])
        self._layout_combo.set_selected(0 if current_layout == "list" else 1)
        self._layout_combo.set_size_request(180, -1)
        layout_row.append(self._layout_combo)
        appearance_box.append(layout_row)

        # Result density
        density_options = ["紧凑", "舒适", "宽松"]
        density_values = ["compact", "comfortable", "airy"]
        current_density = self._config.get("result_density", "comfortable")
        density_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        density_row.set_css_classes(["settings-row"])
        density_lbl = Gtk.Label(label="结果密度")
        density_lbl.set_size_request(124, -1)
        density_lbl.set_halign(Gtk.Align.START)
        density_row.append(density_lbl)
        self._density_combo = Gtk.DropDown.new_from_strings(density_options)
        self._density_combo.set_size_request(180, -1)
        self._density_combo.set_selected(
            density_values.index(current_density)
            if current_density in density_values else 1
        )
        density_row.append(self._density_combo)
        appearance_box.append(density_row)

        # Result descriptions
        desc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        desc_row.set_css_classes(["settings-row"])
        desc_lbl = Gtk.Label(label="结果说明")
        desc_lbl.set_size_request(124, -1)
        desc_lbl.set_halign(Gtk.Align.START)
        desc_row.append(desc_lbl)
        self._show_desc_check = Gtk.CheckButton(label="显示")
        self._show_desc_check.set_active(
            self._config.get("show_result_descriptions", True)
        )
        desc_row.append(self._show_desc_check)
        appearance_box.append(desc_row)

        appearance_box.append(self._make_section_label("颜色"))

        # Accent color
        accent_row = self._make_color_row("强调色 (选中/光标)",
                                          self._config.get("appearance", {}).get("accent_color", "rgb(91,127,255)"))
        appearance_box.append(accent_row.box)
        self._accent_color = accent_row.widget

        # Panel bg color
        bg_row = self._make_color_row("面板浅色背景色",
                                      self._config.get("appearance", {}).get("panel_bg_rgb", "246,247,251"))
        appearance_box.append(bg_row.box)
        self._bg_color = bg_row.widget

        appearance_box.append(self._make_section_label("窗口"))

        # Font size
        font_row = self._make_scale_row("UI 字体大小 (px)", 9, 24, 1,
                                        self._config.get("font_size", 13))
        appearance_box.append(font_row.box)
        self._font_size_scale = font_row.widget

        # Window width
        width_row = self._make_spin_row("窗口宽度 (px)", 400, 1200, 10,
                                       self._config.get("launcher_width", 680))
        appearance_box.append(width_row.box)
        self._width_spin = width_row.widget

        # Window height
        height_row = self._make_spin_row("窗口高度 (px)", 400, 1200, 10,
                                        self._config.get("launcher_height", 720))
        appearance_box.append(height_row.box)
        self._height_spin = height_row.widget

        # Scroll area
        scroll1 = Gtk.ScrolledWindow()
        scroll1.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll1.set_child(appearance_box)
        scroll1.set_min_content_height(400)
        stack.add_titled(scroll1, "appearance", "外观")

        # --- Tab 2: 快捷键 ---
        shortcut_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        shortcut_box.set_margin_top(8)

        # Shortcut capture button
        current_shortcut = self._config.get("shortcut", "ALT+space")
        self._capturing = False

        sc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        sc_lbl = Gtk.Label(label="快捷键")
        sc_lbl.set_size_request(140, -1)
        sc_lbl.set_halign(Gtk.Align.START)
        sc_row.append(sc_lbl)

        self._shortcut_btn = Gtk.Button(label=f"  {_format_shortcut_display(current_shortcut)}  ")
        self._shortcut_btn.set_hexpand(False)
        self._shortcut_btn.set_tooltip_text("点击后按下想要绑定的快捷键组合")
        self._shortcut_btn.connect("clicked", self._on_start_capture)
        sc_row.append(self._shortcut_btn)

        self._shortcut_hint = Gtk.Label()
        self._shortcut_hint.set_markup("<span size='small'>点击按钮，然后按下键盘快捷键</span>")
        self._shortcut_hint.set_halign(Gtk.Align.START)
        self._shortcut_hint.set_margin_start(152)

        shortcut_box.append(sc_row)
        shortcut_box.append(self._shortcut_hint)

        # Key capture controller (hidden keyboard listener for capture)
        self._capture_controller = Gtk.EventControllerKey()
        self._capture_controller.connect("key-pressed", self._on_capture_key)
        self._controller_was_added = False

        # Scroll area
        scroll2 = Gtk.ScrolledWindow()
        scroll2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll2.set_child(shortcut_box)
        scroll2.set_min_content_height(200)
        stack.add_titled(scroll2, "shortcut", "快捷键")

        # --- Tab 3: 搜索 & 网址 ---
        web_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        web_box.set_margin_top(8)

        # --- Search engine section ---
        se_label = Gtk.Label()
        se_label.set_markup("<b>搜索引擎</b>")
        se_label.set_halign(Gtk.Align.START)
        se_label.set_margin_bottom(4)
        web_box.append(se_label)

        # Preset engines
        SEARCH_ENGINE_PRESETS = {
            "Google": "https://www.google.com/search?q={query}",
            "Bing": "https://www.bing.com/search?q={query}",
            "DuckDuckGo": "https://duckduckgo.com/?q={query}",
            "Baidu": "https://www.baidu.com/s?wd={query}",
            "Brave": "https://search.brave.com/search?q={query}",
            "SearXNG": "https://searx.be/search?q={query}",
            "自定URL": "",
        }
        engine_names = list(SEARCH_ENGINE_PRESETS.keys())
        current_se = self._config.get("search_engine", {})
        current_name = current_se.get("name", "Google")
        current_url = current_se.get("url", "")

        engine_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        engine_lbl = Gtk.Label(label="预设")
        engine_lbl.set_size_request(50, -1)
        engine_row.append(engine_lbl)
        self._engine_combo = Gtk.DropDown.new_from_strings(engine_names)
        if current_name in engine_names:
            self._engine_combo.set_selected(engine_names.index(current_name))
        self._engine_combo.set_halign(Gtk.Align.START)
        self._engine_combo.connect("notify::selected", self._on_engine_preset_changed)
        engine_row.append(self._engine_combo)
        web_box.append(engine_row)

        # Custom URL entry
        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        url_lbl = Gtk.Label(label="URL")
        url_lbl.set_size_request(50, -1)
        url_row.append(url_lbl)
        self._engine_url_entry = Gtk.Entry()
        self._engine_url_entry.set_placeholder_text("https://...?q={query}")
        self._engine_url_entry.set_text(current_url)
        self._engine_url_entry.set_hexpand(True)
        url_row.append(self._engine_url_entry)
        web_box.append(url_row)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.set_margin_top(8)
        sep2.set_margin_bottom(8)
        web_box.append(sep2)

        # --- Web shortcuts section ---
        ws_label = Gtk.Label()
        ws_label.set_markup("<b>快捷网址</b>")
        ws_label.set_halign(Gtk.Align.START)
        ws_label.set_margin_bottom(4)
        web_box.append(ws_label)

        # Scrolled container for the shortcut list
        web_scroll = Gtk.ScrolledWindow()
        web_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        web_scroll.set_min_content_height(250)

        self._web_shortcuts_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        web_scroll.set_child(self._web_shortcuts_list)
        web_box.append(web_scroll)

        # Add button
        add_btn = Gtk.Button(label="+ 添加快捷网址")
        add_btn.connect("clicked", self._on_add_web_shortcut)
        web_box.append(add_btn)

        stack.add_titled(web_box, "web", "搜索 & 网址")

        # Track web shortcut rows
        self._web_rows = []
        self._rebuild_web_shortcuts_list()

        # --- Tab 4: 关于 ---
        about_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        about_box.set_margin_top(8)

        about_text = Gtk.Label()
        about_text.set_markup(
            "Lume GNOME 启动器\n\n"
            "配置文件位置：\n"
            f"<span size='small'>{CONFIG_FILE}</span>\n\n"
            "快捷键：Alt+Space 打开\n"
            "Escape 关闭\n"
            "回车启动应用"
        )
        about_text.set_halign(Gtk.Align.START)
        about_text.set_valign(Gtk.Align.START)
        about_box.append(about_text)

        stack.add_titled(about_box, "about", "关于")

        # Tab switcher
        switcher = Gtk.StackSwitcher()
        switcher.set_stack(stack)
        vbox.append(switcher)
        vbox.append(stack)

        # --- Buttons ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(16)

        cancel_btn = Gtk.Button(label="取消")
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_box.append(cancel_btn)

        save_btn = Gtk.Button(label="保存")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_clicked)
        btn_box.append(save_btn)

        vbox.append(btn_box)

        # Keyboard shortcut for Escape
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        # Restore saved theme preset after all controls exist
        self._restore_theme_preset()

    def _on_key_pressed(self, _ctrl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            # If currently capturing, clean up first
            if self._capturing:
                self._capturing = False
                self._shortcut_btn.set_sensitive(True)
                if self._controller_was_added:
                    self.remove_controller(self._capture_controller)
                    self._controller_was_added = False
                self._shortcut_btn.set_label(f"  {_format_shortcut_display(self._config.get('shortcut', 'ALT+space'))}  ")
                if self._resume_shortcut:
                    self._resume_shortcut()
            self.close()
            return True
        return False

    def _on_close_request(self, _window):
        self._cleanup_before_close()
        if self._on_close and not self._closed_notified:
            self._closed_notified = True
            self._on_close()
        return False

    def _on_start_capture(self, _btn):
        """Start recording a key combination."""
        try:
            if self._capturing:
                return
            self._capturing = True
            self._shortcut_btn.set_sensitive(False)
            self._shortcut_btn.set_label("  按下快捷键...  ")
            self._shortcut_hint.set_markup("<span size='small'>请在键盘上按下你想要的快捷键组合</span>")
            if self._suspend_shortcut:
                self._suspend_shortcut()
            # Safe remove + add controller
            try:
                self.remove_controller(self._capture_controller)
            except Exception:
                pass
            self.add_controller(self._capture_controller)
            self._controller_was_added = True
        except Exception as e:
            import traceback
            print(f"ERROR in capture start: {e}")
            traceback.print_exc()

    def _on_capture_key(self, _ctrl, keyval, _code, state):
        """Capture a key press during recording."""
        if not self._capturing:
            return False

        from gi.repository import Gdk as _Gdk

        # Build modifier string
        parts = []
        if state & _Gdk.ModifierType.CONTROL_MASK:
            parts.append("CTRL")
        if state & _Gdk.ModifierType.ALT_MASK:
            parts.append("ALT")
        if state & _Gdk.ModifierType.SHIFT_MASK:
            parts.append("SHIFT")
        if state & _Gdk.ModifierType.SUPER_MASK:
            parts.append("SUPER")
        # Map key name
        key_name = _Gdk.keyval_name(keyval).lower()
        # Translate common names to portal format
        name_map = {
            "space": "space", "return": "Return", "escape": "Escape",
            "tab": "Tab", "backspace": "BackSpace",
            "slash": "slash", "period": "period", "comma": "comma",
            "minus": "minus", "equal": "equal", "bracketleft": "bracketleft",
            "bracketright": "bracketright", "backslash": "backslash",
            "semicolon": "semicolon", "apostrophe": "apostrophe",
            "grave": "grave", "less": "less", "greater": "greater",
        }
        # If single letter/digit, use uppercase
        if len(key_name) == 1 and key_name.isalnum():
            key_name = key_name.upper()
        else:
            key_name = name_map.get(key_name, key_name.capitalize())

        if not parts:
            # No modifier - require at least one
            self._shortcut_hint.set_markup(
                "<span size='small' color='orange'>请同时按修饰键 (Ctrl/Alt/Super) + 按键</span>"
            )
            return True

        shortcut_str = "+".join(parts + [key_name])
        self._shortcut_btn.set_label(f"  {_format_shortcut_display(shortcut_str)}  ")
        self._captured_shortcut = shortcut_str
        self._finish_capture()
        return True

    def _finish_capture(self):
        """Clean up after capture completes (either by key or Escape/close)."""
        try:
            self._capturing = False
            self._shortcut_btn.set_sensitive(True)
            if self._controller_was_added:
                try:
                    self.remove_controller(self._capture_controller)
                except Exception:
                    pass
                self._controller_was_added = False
            self._shortcut_hint.set_markup("<span size='small'>快捷键已记录，保存后重启 daemon 生效</span>")
            if self._resume_shortcut:
                self._resume_shortcut()
        except Exception as e:
            import traceback
            print(f"ERROR in finish_capture: {e}")
            traceback.print_exc()

    def close(self):
        """Override close to ensure capture controller is cleaned up and shortcut resumed."""
        self._cleanup_before_close()
        if self._on_close and not self._closed_notified:
            self._closed_notified = True
            self._on_close()
        try:
            super().close()
        except Exception:
            pass

    def _cleanup_before_close(self):
        """Ensure capture controller is cleaned up and shortcut resumed."""
        try:
            if self._capturing:
                self._capturing = False
                self._shortcut_btn.set_sensitive(True)
                self._shortcut_btn.set_label(f"  {_format_shortcut_display(self._config.get('shortcut', 'ALT+space'))}  ")
                if self._resume_shortcut:
                    self._resume_shortcut()
            if self._controller_was_added:
                try:
                    self.remove_controller(self._capture_controller)
                except Exception:
                    pass
                self._controller_was_added = False
        except Exception as e:
            import traceback
            print(f"ERROR in settings close: {e}")
            traceback.print_exc()

    def _apply_settings_css(self):
        css = """
        window.settings-window {
            background: rgb(248, 249, 252);
        }
        window.settings-window label,
        window.settings-window checkbutton,
        window.settings-window button,
        window.settings-window dropdown,
        window.settings-window entry,
        window.settings-window spinbutton {
            color: rgba(30, 36, 48, 0.94);
        }
        window.settings-window entry,
        window.settings-window spinbutton,
        window.settings-window dropdown button {
            background: rgba(255, 255, 255, 0.86);
            border-color: rgba(190, 201, 218, 0.72);
        }
        window.settings-window button {
            background: rgba(255, 255, 255, 0.78);
            border-color: rgba(190, 201, 218, 0.72);
        }
        window.settings-window button:hover {
            background: rgba(255, 255, 255, 0.96);
        }
        window.settings-window button.suggested-action {
            color: white;
            background: rgb(105, 136, 181);
            border-color: rgb(105, 136, 181);
        }
        window.settings-window scale value {
            color: rgba(45, 54, 70, 0.78);
        }
        .settings-section-title {
            color: rgba(35, 44, 58, 0.72);
            padding: 2px 0 0 0;
        }
        .settings-row {
            padding: 3px 0;
        }
        .theme-preview-row {
            padding-top: 0;
            padding-bottom: 4px;
        }
        stackswitcher button {
            padding: 6px 12px;
        }
        """
        self._settings_css_provider = Gtk.CssProvider()
        self._settings_css_provider.load_from_string(css)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._settings_css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _make_combo_row(self, label, options, current):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_css_classes(["settings-row"])
        lbl = Gtk.Label(label=label)
        lbl.set_size_request(124, -1)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        combo = Gtk.DropDown.new_from_strings(options)
        if current in options:
            combo.set_selected(options.index(current))
        combo.set_size_request(180, -1)
        combo.set_halign(Gtk.Align.START)
        box.append(combo)

        return _Row(box, combo)

    def _make_section_label(self, text):
        lbl = Gtk.Label()
        lbl.set_markup(f"<span size='small' weight='bold'>{text}</span>")
        lbl.set_css_classes(["settings-section-title"])
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_top(10)
        lbl.set_margin_bottom(0)
        return lbl

    def _make_theme_preview(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_css_classes(["settings-row", "theme-preview-row"])
        label = Gtk.Label(label="")
        label.set_size_request(124, -1)
        box.append(label)

        self._preview_panel = self._make_swatch()
        self._preview_search = self._make_swatch()
        self._preview_accent = self._make_swatch()
        self._preview_text = self._make_swatch()
        for swatch in (
            self._preview_panel,
            self._preview_search,
            self._preview_accent,
            self._preview_text,
        ):
            box.append(swatch)
        return box

    def _make_swatch(self):
        area = Gtk.DrawingArea()
        area.set_size_request(34, 18)
        area._lume_color = (255, 255, 255, 1.0)
        area.set_draw_func(self._draw_swatch)
        return area

    def _draw_swatch(self, area, cr, width, height):
        r, g, b, alpha = getattr(area, "_lume_color", (255, 255, 255, 1.0))
        cr.set_source_rgba(0, 0, 0, 0.12)
        self._rounded_rect(cr, 0.5, 0.5, width - 1, height - 1, 6)
        cr.fill()
        cr.set_source_rgba(r / 255, g / 255, b / 255, alpha)
        self._rounded_rect(cr, 1.5, 1.5, width - 3, height - 3, 5)
        cr.fill()

    def _rounded_rect(self, cr, x, y, width, height, radius):
        degrees = 3.14159265 / 180
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -90 * degrees, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 90 * degrees)
        cr.arc(x + radius, y + height - radius, radius, 90 * degrees, 180 * degrees)
        cr.arc(x + radius, y + radius, radius, 180 * degrees, 270 * degrees)
        cr.close_path()

    def _parse_color_tuple(self, color_str):
        import re
        m = re.match(
            r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([0-9.]+))?',
            color_str.strip(),
        )
        if m:
            return (
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                float(m.group(4)) if m.group(4) else 1.0,
            )
        parts = color_str.replace(" ", "").split(",")
        if len(parts) >= 3:
            return (int(parts[0]), int(parts[1]), int(parts[2]), 1.0)
        return (255, 255, 255, 1.0)

    def _update_theme_preview(self, theme):
        if not theme or not hasattr(self, "_preview_panel"):
            return
        swatches = (
            (self._preview_panel, theme.get("panel_bg_rgb", "247, 249, 252")),
            (self._preview_search, theme.get("search_bg", "rgba(255, 255, 255, 0.86)")),
            (self._preview_accent, theme.get("accent_color", "rgb(105, 136, 181)")),
            (self._preview_text, theme.get("text_color", "rgba(18, 24, 34, 0.96)")),
        )
        for area, color in swatches:
            area._lume_color = self._parse_color_tuple(color)
            area.queue_draw()

    def _make_scale_row(self, label, min_v, max_v, step, current):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_css_classes(["settings-row"])
        lbl = Gtk.Label(label=label)
        lbl.set_size_request(124, -1)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_v, max_v, step)
        scale.set_value(current)
        scale.set_hexpand(False)
        scale.set_size_request(220, -1)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        box.append(scale)

        return _Row(box, scale)

    def _make_spin_row(self, label, min_v, max_v, step, current):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_css_classes(["settings-row"])
        lbl = Gtk.Label(label=label)
        lbl.set_size_request(124, -1)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        adj = Gtk.Adjustment(value=current, lower=min_v, upper=max_v, step_increment=step)
        spin = Gtk.SpinButton(adjustment=adj)
        spin.set_hexpand(False)
        box.append(spin)

        return _Row(box, spin)

    def _make_color_row(self, label, current_rgb):
        """Create a color row with Gtk.ColorButton. current_rgb like '246,247,251' or 'rgb(91,127,255)'."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_css_classes(["settings-row"])
        lbl = Gtk.Label(label=label)
        lbl.set_size_request(124, -1)
        lbl.set_halign(Gtk.Align.START)
        box.append(lbl)

        # Parse current RGB
        clean = current_rgb.replace("rgb(", "").replace(")", "").replace(" ", "")
        parts = clean.split(",")
        rgba = Gdk.RGBA()
        if len(parts) >= 3:
            rgba.red = int(parts[0]) / 255.0
            rgba.green = int(parts[1]) / 255.0
            rgba.blue = int(parts[2]) / 255.0
            rgba.alpha = 1.0

        btn = Gtk.ColorButton()
        btn.set_rgba(rgba)
        btn.set_hexpand(False)
        btn.set_size_request(180, -1)
        btn.set_halign(Gtk.Align.START)
        box.append(btn)

        return _Row(box, btn)

    def _restore_theme_preset(self):
        """Restore the saved theme preset and apply values to all controls."""
        from lume.themes import get_theme
        saved_preset = getattr(self, "_initial_theme_preset", self._config.get("theme_preset", ""))
        if not saved_preset:
            return
        model = self._theme_preset_combo.get_model()
        for i in range(model.get_n_items()):
            if model.get_string(i) == saved_preset:
                self._restoring = True
                self._theme_preset_combo.set_selected(i)
                self._restoring = False
                theme = get_theme(saved_preset)
                if theme:
                    if "panel_opacity" in theme:
                        self._opacity_scale.set_value(theme["panel_opacity"])
                    if "border_radius" in theme:
                        self._radius_spin.set_value(theme["border_radius"])
                    if "accent_color" in theme:
                        self._set_color_from_string(
                            self._accent_color, theme["accent_color"]
                        )
                    if "panel_bg_rgb" in theme:
                        self._set_color_from_string(
                            self._bg_color, f"rgb({theme['panel_bg_rgb']})"
                        )
                    self._update_theme_preview(theme)
                break

    def _on_theme_preset_changed(self, combo, _pspec=None):
        """Apply a color scheme preset to all appearance controls."""
        if getattr(self, '_restoring', False):
            return
        from lume.themes import get_theme
        active = combo.get_selected()
        if active < 0:
            return
        model = combo.get_model()
        name = model.get_string(active)
        theme = get_theme(name)
        if not theme:
            return

        # Fill in all appearance controls
        if "panel_opacity" in theme:
            self._opacity_scale.set_value(theme["panel_opacity"])
        if "border_radius" in theme:
            self._radius_spin.set_value(theme["border_radius"])
        if "accent_color" in theme:
            self._set_color_from_string(self._accent_color, theme["accent_color"])
        if "panel_bg_rgb" in theme:
            self._set_color_from_string(
                self._bg_color, f"rgb({theme['panel_bg_rgb']})"
            )
        self._update_theme_preview(theme)

    def _set_color_from_string(self, color_btn, color_str):
        """Set a Gtk.ColorButton from a color string like 'rgb(R,G,B)' or 'rgba(R,G,B,A)'."""
        import re
        m = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
        if m:
            r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
            color_btn.set_rgba(Gdk.RGBA(r / 255, g / 255, b / 255, 1.0))

    def _on_save_clicked(self, _btn):
        """Save settings and close."""
        try:
            appearance = self._config.get("appearance", {})

            # Shortcut (use captured if available, otherwise keep current)
            new_sc = getattr(self, '_captured_shortcut', None) or self._config.get("shortcut", "ALT+space")
            parts = new_sc.rsplit("+", 1)
            if len(parts) == 2:
                new_sc = parts[0].upper() + "+" + parts[1].lower()
            self._config["shortcut"] = new_sc

            theme_options = ["auto", "light", "dark"]
            theme_idx = self._theme_combo.get_selected()
            if theme_idx < 0 or theme_idx >= len(theme_options):
                theme_idx = 0
            theme = theme_options[theme_idx]
            self._config["theme"] = theme

            preset_idx = self._theme_preset_combo.get_selected()
            from lume.themes import get_theme
            model = self._theme_preset_combo.get_model()
            if preset_idx < 0 or preset_idx >= model.get_n_items():
                preset_idx = 0
            preset_name = model.get_string(preset_idx)
            self._config["theme_preset"] = preset_name
            preset_theme = get_theme(preset_name)
            if preset_theme:
                appearance = dict(preset_theme)

            appearance["panel_opacity"] = round(self._opacity_scale.get_value(), 2)
            appearance["border_radius"] = int(self._radius_spin.get_value())

            rgba = self._accent_color.get_rgba()
            appearance["accent_color"] = f"rgb({int(rgba.red*255)},{int(rgba.green*255)},{int(rgba.blue*255)})"

            rgba = self._bg_color.get_rgba()
            appearance["panel_bg_rgb"] = f"{int(rgba.red*255)}, {int(rgba.green*255)}, {int(rgba.blue*255)}"

            self._config["launcher_width"] = int(self._width_spin.get_value())
            self._config["launcher_height"] = int(self._height_spin.get_value())
            self._config["font_size"] = int(self._font_size_scale.get_value())

            layout_idx = self._layout_combo.get_selected()
            if layout_idx < 0 or layout_idx > 1:
                layout_idx = 0
            self._config["layout"] = "grid" if layout_idx == 1 else "list"

            density_idx = self._density_combo.get_selected()
            density_options = ["compact", "comfortable", "airy"]
            if density_idx < 0 or density_idx >= len(density_options):
                density_idx = 1
            self._config["result_density"] = density_options[density_idx]
            self._config["show_result_descriptions"] = self._show_desc_check.get_active()

            idx = self._engine_combo.get_selected()
            if idx >= 0:
                model = self._engine_combo.get_model()
                engine_name = model.get_string(idx)
                engine_url = self._engine_url_entry.get_text().strip()
                if engine_name == "自定URL":
                    engine_name = "自定义"
                self._config["search_engine"] = {"name": engine_name, "url": engine_url}

            web_list = []
            for row in self._web_rows:
                name = row["name"].get_text().strip()
                url = row["url"].get_text().strip()
                if name and url:
                    web_list.append({"name": name, "url": url})
            self._config["web_shortcuts"] = web_list

            self._config["appearance"] = appearance
            save_config(self._config)

            if self._on_save:
                self._on_save(self._config)

            self.close()
        except Exception as e:
            import traceback
            print(f"ERROR saving settings: {e}")
            traceback.print_exc()
            try:
                self.close()
            except Exception:
                pass

    def _on_engine_preset_changed(self, combo, _pspec=None):
        """When engine preset selected, fill the URL entry."""
        SEARCH_ENGINE_PRESETS = {
            "Google": "https://www.google.com/search?q={query}",
            "Bing": "https://www.bing.com/search?q={query}",
            "DuckDuckGo": "https://duckduckgo.com/?q={query}",
            "Baidu": "https://www.baidu.com/s?wd={query}",
            "Brave": "https://search.brave.com/search?q={query}",
            "SearXNG": "https://searx.be/search?q={query}",
            "自定URL": "",
        }
        idx = combo.get_selected()
        if idx < 0:
            return
        model = combo.get_model()
        name = model.get_string(idx)
        url = SEARCH_ENGINE_PRESETS.get(name, "")
        if url:
            self._engine_url_entry.set_text(url)

    def _rebuild_web_shortcuts_list(self):
        """Rebuild the web shortcuts list from config."""
        # Clear existing rows
        for row in self._web_rows:
            self._web_shortcuts_list.remove(row["box"])
        self._web_rows.clear()
        # Add rows from config
        for sc in self._config.get("web_shortcuts", []):
            self._add_web_row(sc.get("name", ""), sc.get("url", ""))

    def _add_web_row(self, name="", url=""):
        """Add a single web shortcut row."""
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("名称")
        name_entry.set_text(name)
        name_entry.set_hexpand(True)
        row_box.append(name_entry)

        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://...")
        url_entry.set_text(url)
        url_entry.set_hexpand(True)
        row_box.append(url_entry)

        del_btn = Gtk.Button(label="✕")
        del_btn.set_tooltip_text("删除")
        del_btn.connect("clicked", self._on_delete_web_row, row_box)
        row_box.append(del_btn)

        self._web_shortcuts_list.append(row_box)
        self._web_rows.append({"box": row_box, "name": name_entry, "url": url_entry})

    def _on_add_web_shortcut(self, _btn):
        """Add a new empty web shortcut row."""
        self._add_web_row()

    def _on_delete_web_row(self, _btn, row_box):
        """Remove a web shortcut row."""
        for i, row in enumerate(self._web_rows):
            if row["box"] is row_box:
                self._web_shortcuts_list.remove(row_box)
                self._web_rows.pop(i)
                break


class _Row:
    """Helper to return both box and widget from row builders."""
    def __init__(self, box, widget):
        self.box = box
        self.widget = widget
