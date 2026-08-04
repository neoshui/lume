"""Lume Launcher - searchable app launcher UI."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gtk, Gdk, GLib, Gio, GObject, Pango
from datetime import datetime
import shutil
from lume.config import get_data_dir, save_config
from lume.search import search, launch_app, open_folder, open_url, SearchResult
from pathlib import Path
from lume.tools.clipboard import ClipboardEntry


# Shared CSS provider (content generated from config)
_LAUNCHER_CSS = Gtk.CssProvider()
_CSS_PRIORITY = Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
_global_theme_applied = False


def _build_css_string(config: dict, is_dark: bool) -> str:
    """Build CSS string from config.

    config = full config dict (includes appearance, launcher_height, etc.)
    is_dark = True for dark theme, False for light
    """
    a = config.get("appearance", {})
    launcher_height = config.get("launcher_height", 720)
    launcher_width = config.get("launcher_width", 680)

    # Font size scaling (base = font_size config, default 13)
    fs_base = config.get("font_size", 13)
    density = config.get("result_density", "comfortable")
    density_specs = {
        "compact": {"row_height": 46, "row_margin": 2, "row_padding_y": 5, "icon_box": 30, "icon_px": 20, "icon_pad": 5},
        "comfortable": {"row_height": 58, "row_margin": 3, "row_padding_y": 7, "icon_box": 34, "icon_px": 22, "icon_pad": 6},
        "airy": {"row_height": 68, "row_margin": 4, "row_padding_y": 9, "icon_box": 38, "icon_px": 24, "icon_pad": 7},
    }
    ds = density_specs.get(density, density_specs["comfortable"])

    if is_dark:
        panel_rgb = a.get("panel_bg_dark_rgb", "28, 28, 32")
        panel_bg = f"rgba({panel_rgb}, 0.96)"
        search_bg = a.get("search_bg_dark", "rgb(48, 48, 54)")
        search_focus = "rgba(58, 62, 72, 0.96)"
        text_c = a.get("text_dark_color", "rgba(255, 255, 255, 0.92)")
        desc_c = a.get("desc_dark_color", "rgba(255, 255, 255, 0.38)")
        hover = "rgba(255, 255, 255, 0.075)"
        scroll_slider = "rgba(226, 233, 244, 0.18)"
        clip_bg = "rgba(255, 255, 255, 0.08)"
        clip_hover = "rgba(255, 255, 255, 0.13)"
        clip_text = "rgba(238, 242, 249, 0.72)"
        divider = "rgba(225, 232, 244, 0.10)"
        hint_c = "rgba(225, 232, 244, 0.38)"
        empty_c = "rgba(225, 232, 244, 0.34)"
        header_c = "rgba(225, 232, 244, 0.48)"
        border_c = "rgba(255, 255, 255, 0.10)"
        icon_bg = "rgba(255, 255, 255, 0.08)"
        result_bg = "rgba(255, 255, 255, 0.055)"
        result_border = "rgba(255, 255, 255, 0.06)"
        result_surface = "rgba(255, 255, 255, 0.035)"
        shadow = "0 20px 48px rgba(0, 0, 0, 0.28)"
    else:
        panel_rgb = a.get("panel_bg_rgb", "246, 247, 251")
        panel_bg = f"rgba({panel_rgb}, {a.get('panel_opacity', 0.88)})"
        search_bg = a.get("search_bg", "rgba(255, 255, 255, 0.6)")
        search_focus = "rgba(255, 255, 255, 0.96)"
        text_c = a.get("text_color", "rgba(0, 0, 0, 0.85)")
        desc_c = a.get("desc_color", "rgba(0, 0, 0, 0.42)")
        hover = "rgba(98, 120, 154, 0.12)"
        scroll_slider = "rgba(84, 101, 126, 0.22)"
        clip_bg = "rgba(255, 255, 255, 0.82)"
        clip_hover = "rgba(255, 255, 255, 0.98)"
        clip_text = "rgba(31, 42, 58, 0.84)"
        divider = "rgba(91, 110, 138, 0.18)"
        hint_c = "rgba(58, 71, 91, 0.58)"
        empty_c = "rgba(58, 71, 91, 0.56)"
        header_c = "rgba(42, 54, 72, 0.68)"
        border_c = "rgba(198, 210, 226, 0.72)"
        icon_bg = "rgba(255, 255, 255, 0.86)"
        result_bg = "rgba(255, 255, 255, 0.54)"
        result_border = "rgba(203, 214, 228, 0.68)"
        result_surface = "rgba(255, 255, 255, 0.28)"
        shadow = "0 20px 52px rgba(52, 67, 92, 0.18)"

    accent = a.get("accent_color", "rgb(91, 127, 255)")
    _accent_sel = accent.replace("rgb(", "rgba(").rstrip(")") + ",0.18)"
    radius = a.get("border_radius", 14)
    # Outer margin for floating look (proportional, ~9%)
    _outer_margin = max(28, min(82, int(min(launcher_width, launcher_height) * 0.075)))
    return f"""
    window.launcher-window {{
        background: rgba({panel_rgb}, 0.18);
        border-radius: {radius + 8}px;
    }}
    .launcher-box {{
        background: {panel_bg};
        border: 1px solid {border_c};
        border-radius: {max(radius, 12)}px;
        box-shadow: {shadow};
        padding: 12px;
        margin: {_outer_margin}px;
        min-width: {launcher_width - _outer_margin * 2}px;
        min-height: {launcher_height - _outer_margin * 2}px;
    }}
    .search-box {{
        background: transparent;
        margin: 0 0 8px 0;
    }}
    .results-list {{
        background: transparent;
        border: none;
        padding: 4px 0;
    }}
    .results-scroll {{
        background: {result_surface};
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: {max(radius - 4, 10)}px;
        padding: 4px 6px;
    }}
    .results-scroll > scrollbar {{
        background: transparent;
    }}
    .results-scroll > scrollbar > range > slider {{
        background: {scroll_slider};
        border-radius: 4px;
        min-width: 6px;
    }}
    .search-entry {{
        background: {search_bg};
        border: 1px solid {border_c};
        border-radius: {max(radius - 2, 12)}px;
        padding: 12px 16px;
        font-size: {fs_base + 1}px;
        color: {text_c};
        caret-color: {accent};
        margin: 0 6px 0 0;
    }}
    .search-entry:focus {{
        background: {search_focus};
        border-color: {accent};
    }}
    .settings-button {{
        background: {search_bg};
        border: 1px solid {border_c};
        border-radius: {max(radius - 4, 10)}px;
        min-width: 42px;
        min-height: 42px;
        color: {hint_c};
        padding: 0;
    }}
    .settings-button:hover {{
        background: {search_focus};
        color: {text_c};
    }}
    .result-row {{
        background: {result_bg};
        border: 1px solid {result_border};
        border-radius: {max(radius - 6, 10)}px;
        min-height: {ds['row_height']}px;
        padding: 0;
        margin: {ds['row_margin']}px 0;
    }}
    .result-row:hover {{
        background: {hover};
        border-color: {accent};
    }}
    .launcher-box .result-row:selected,
    .results-list row:selected,
    .result-row.selected {{
        background-color: {_accent_sel};
        border-color: {accent};
    }}
    .results-list row:selected .result-name,
    .results-list row:selected .result-desc {{
        color: {text_c};
    }}
    .result-hbox {{
        background: transparent;
    }}
    .result-icon {{
        background: {icon_bg};
        border-radius: {max(radius - 8, 10)}px;
        padding: {ds['icon_pad']}px;
        min-width: {ds['icon_box']}px;
        min-height: {ds['icon_box']}px;
    }}
    .result-name {{
        background: transparent;
        color: {text_c};
        font-weight: 500;
        font-size: {fs_base}px;
    }}
    .result-desc {{
        background: transparent;
        color: {desc_c};
        font-size: {max(fs_base - 3, 10)}px;
    }}
    .shortcut-hint {{
        background: rgba(255, 255, 255, 0.42);
        border: 1px solid {result_border};
        border-radius: 999px;
        color: {hint_c};
        font-size: {max(fs_base - 3, 10)}px;
        padding: 3px 8px;
    }}
    .empty-label {{
        background: transparent;
        color: {empty_c};
        font-size: {max(fs_base - 1, 10)}px;
        padding: 20px;
    }}
    .clipboard-section {{
        background: transparent;
        border-top: 1px solid {divider};
        padding: 8px 0 0 0;
    }}
    .clipboard-header {{
        background: transparent;
        color: {header_c};
        font-size: {max(fs_base - 2, 10)}px;
        padding: 0 4px 6px 4px;
    }}
    .clipboard-item {{
        background: {clip_bg};
        border: 1px solid {border_c};
        color: {clip_text};
        font-size: {max(fs_base - 1, 11)}px;
        padding: 4px 10px;
        border-radius: 999px;
        min-height: 20px;
    }}
    .clipboard-item:hover {{
        background: {clip_hover};
    }}
    .clipboard-pinned {{
        color: {accent};
    }}
    .clipboard-image-item {{
        background: {clip_bg};
        border: 1px solid {border_c};
        border-radius: 10px;
        padding: 3px;
        min-height: 42px;
    }}
    .clipboard-image-item:hover {{
        background: {clip_hover};
    }}
    .clipboard-thumb {{
        border-radius: 8px;
    }}
    .clipboard-context-btn {{
        font-size: 12px;
        padding: 4px 12px;
        min-height: 24px;
    }}
    .clipboard-clear {{
        color: {hint_c};
        font-size: {max(fs_base - 2, 9)}px;
        padding: 2px 8px;
        background: transparent;
        border: none;
        border-radius: 999px;
    }}
    .clipboard-clear:hover {{
        color: {text_c};
    }}
    .clipboard-scroll {{
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
    }}
    .clipboard-scroll > scrollbar {{
        background: transparent;
        border: none;
        margin: 0;
        padding: 0;
    }}
    .clipboard-scroll > scrollbar > range > slider {{
        background: {scroll_slider};
        border-radius: 4px;
        min-width: 5px;
        min-height: 24px;
    }}
    .clipboard-scroll > scrollbar > range > slider:hover {{
        background: {hint_c};
    }}
    .main-paned {{
        background: transparent;
    }}
    .main-paned > separator {{
        background: {divider};
        min-height: 1px;
        margin: 8px 8px;
        border-radius: 999px;
    }}
    .main-paned > separator:hover {{
        background: {accent};
        min-height: 3px;
    }}
    .results-grid {{
        background: transparent;
        border: none;
        padding: 0;
    }}
    .grid-cell {{
        background: rgba(255, 255, 255, 0.22);
        border-radius: {max(radius - 6, 10)}px;
        min-width: 76px;
        min-height: 72px;
        padding: 8px 6px 6px;
        border: 1px solid transparent;
    }}
    .grid-cell:hover {{
        background: {hover};
    }}
    .grid-cell:selected {{
        background: {_accent_sel};
        border: 1px solid {accent};
    }}
    .grid-icon {{
        background: {icon_bg};
        border-radius: 12px;
        padding: 6px;
    }}
    .grid-name {{
        color: {text_c};
        font-size: {max(fs_base - 2, 10)}px;
    }}
    .grid-desc {{
        color: {desc_c};
        font-size: {max(fs_base - 3, 9)}px;
    }}
"""


def reload_css(config: dict):
    """Force re-build CSS from config (for settings hot-reload)."""
    global _global_theme_applied
    _global_theme_applied = False
    _apply_css(config)


def _style_widget(w):
    """Apply the CSS provider to a widget's style context."""
    w.get_style_context().add_provider(_LAUNCHER_CSS, _CSS_PRIORITY)


def _apply_css(config: dict):
    """Build and apply CSS from config, once per session."""
    global _global_theme_applied
    if _global_theme_applied:
        return
    _global_theme_applied = True

    theme = config.get("theme", "auto")
    if theme == "dark":
        is_dark = True
    elif theme == "light":
        is_dark = False
    else:  # auto — detect system dark theme
        is_dark = False
        settings = Gtk.Settings.get_default()
        if settings:
            theme_name = settings.get_property('gtk-theme-name') or ""
            is_dark = "dark" in theme_name.lower()

    css_str = _build_css_string(config, is_dark)
    _LAUNCHER_CSS.load_from_string(css_str)

    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display, _LAUNCHER_CSS, _CSS_PRIORITY
        )


class LauncherUI(Gtk.Box):
    """Main launcher UI with search bar, results, and clipboard section."""

    def __init__(self, clipboard_watcher, config, on_select=None, open_settings=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._config = config
        self._clipboard = clipboard_watcher
        self._on_select = on_select
        self._open_settings = open_settings
        self._all_results: list[SearchResult] = []

        # Apply CSS from config (once per session)
        _apply_css(config)

        self.set_css_classes(["launcher-box"])
        _style_widget(self)

        # --- Search entry + settings button ---
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        search_box.set_css_classes(["search-box"])
        search_box.set_margin_start(0)
        search_box.set_margin_end(0)
        _style_widget(search_box)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("搜索应用、文件夹、网页…")
        self._search_entry.set_css_classes(["search-entry"])
        self._search_entry.set_hexpand(True)
        self._search_changed_hid = self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", self._on_search_activate)
        self._search_entry.connect("keynav-failed", lambda *a: True)
        _style_widget(self._search_entry)
        search_box.append(self._search_entry)

        # Settings gear button
        gear_btn = Gtk.Button()
        gear_btn.set_icon_name("emblem-system-symbolic")
        gear_btn.set_tooltip_text("设置")
        gear_btn.add_css_class("flat")
        gear_btn.add_css_class("settings-button")
        gear_btn.set_valign(Gtk.Align.CENTER)
        gear_btn.connect("clicked", lambda _: self._open_settings() if self._open_settings else None)
        _style_widget(gear_btn)
        search_box.append(gear_btn)

        self.append(search_box)

        # --- Results container ---
        # ListBox for list layout
        self._results_list = Gtk.ListBox()
        self._results_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._results_list.set_activate_on_single_click(True)
        self._results_list.connect("row-activated", self._on_row_activated)
        self._results_list.set_css_classes(["results-list"])
        _style_widget(self._results_list)

        # FlowBox for grid layout
        self._results_grid = Gtk.FlowBox()
        self._results_grid.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._results_grid.set_activate_on_single_click(True)
        self._results_grid.connect("child-activated", self._on_grid_child_activated)
        self._results_grid.set_min_children_per_line(4)
        self._results_grid.set_max_children_per_line(7)
        self._results_grid.set_homogeneous(True)
        self._results_grid.set_row_spacing(2)
        self._results_grid.set_column_spacing(2)
        self._results_grid.set_css_classes(["results-grid"])
        _style_widget(self._results_grid)

        self._results_container = self._results_list  # active one
        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_child(self._results_container)
        self._scrolled.set_min_content_height(80)
        self._scrolled.set_vexpand(True)
        self._scrolled.set_css_classes(["results-scroll"])
        _style_widget(self._scrolled)

        # --- Clipboard section ---
        self._clipboard_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._clipboard_box.set_vexpand(True)
        self._clipboard_box.set_css_classes(["clipboard-section"])
        _style_widget(self._clipboard_box)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_label = Gtk.Label(label="剪贴板")
        header_label.set_css_classes(["clipboard-header"])
        header_label.set_halign(Gtk.Align.START)
        header_label.set_hexpand(True)
        _style_widget(header_label)
        header_box.append(header_label)

        self._clear_all_btn = Gtk.Button(label="清空")
        self._clear_all_btn.add_css_class("flat")
        self._clear_all_btn.add_css_class("clipboard-clear")
        self._clear_all_btn.connect("clicked", self._on_clipboard_clear_all)
        _style_widget(self._clear_all_btn)
        header_box.append(self._clear_all_btn)

        # Clipboard container (Gtk.Box for manual wrapping) inside a ScrolledWindow
        self._clipboard_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self._clipboard_grid.set_vexpand(True)
        _style_widget(self._clipboard_grid)

        self._clipboard_scroll = Gtk.ScrolledWindow()
        self._clipboard_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._clipboard_scroll.set_min_content_height(40)
        self._clipboard_scroll.set_vexpand(True)
        self._clipboard_scroll.set_css_classes(["clipboard-scroll"])
        _style_widget(self._clipboard_scroll)
        self._clipboard_scroll.set_child(self._clipboard_grid)

        self._clipboard_box.append(header_box)
        self._clipboard_box.append(self._clipboard_scroll)

        # --- Paned: drag-to-resize splitter between results and clipboard ---
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self._paned.set_vexpand(True)
        self._paned.set_resize_start_child(True)
        self._paned.set_shrink_start_child(True)
        self._paned.set_resize_end_child(True)
        self._paned.set_shrink_end_child(True)
        self._paned.set_start_child(self._scrolled)
        self._paned.set_end_child(self._clipboard_box)
        # Initial position: restore saved divider position, else default ~200px for clipboard
        saved = self._config.get("paned_position", 0)
        if saved > 0:
            self._paned.set_position(saved)
        else:
            h = self._config.get("launcher_height", 720)
            self._paned.set_position(max(200, h - 220))
        # Save divider position on each drag
        self._paned.connect("notify::position", self._on_paned_position_changed)
        self._paned.set_css_classes(["main-paned"])
        _style_widget(self._paned)
        self.append(self._paned)

        # Populate clipboard history
        self._refresh_clipboard()

        # Initial search (show all apps on first open)
        self._all_results = search("", self._config)
        self._rebuild_results()

    def _on_search_changed(self, entry):
        """Handle search text changes."""
        query = entry.get_text()
        self._all_results = search(query, self._config)
        self._rebuild_results()

    def _rebuild_results(self):
        """Rebuild the results list based on layout mode."""
        layout = self._config.get("layout", "list")
        current = getattr(self, "_current_layout", "list")

        # Skip redundant switch if layout unchanged and container already correct
        if layout == current and self._scrolled.get_child() == self._results_container:
            # Just refresh contents without switching
            self._refresh_results_content(layout)
            return

        self._current_layout = layout

        if layout == "grid":
            self._results_grid.remove_all()
            self._results_container = self._results_grid
            self._scrolled.set_child(self._results_grid)

            if not self._all_results:
                empty = Gtk.Label(label="未找到结果")
                empty.set_css_classes(["empty-label"])
                _style_widget(empty)
                self._results_grid.append(empty)
            else:
                for result in self._all_results:
                    cell = self._create_grid_cell(result)
                    self._results_grid.append(cell)
        else:
            child = self._results_list.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._results_list.remove(child)
                child = next_child
            self._results_container = self._results_list
            self._scrolled.set_child(self._results_list)

            if not self._all_results:
                empty = Gtk.Label(label="未找到结果")
                empty.set_css_classes(["empty-label"])
                _style_widget(empty)
                self._results_list.append(empty)
            else:
                for result in self._all_results:
                    row = self._create_result_row(result)
                    self._results_list.append(row)

        # Select first item
        if layout == "grid":
            first = self._results_grid.get_child_at_index(0)
            if first:
                self._results_grid.select_child(first)
        else:
            first = self._results_list.get_row_at_index(0)
            if first:
                self._results_list.select_row(first)

    def _refresh_results_content(self, layout):
        """Refresh content without switching container."""
        if layout == "grid":
            self._results_grid.remove_all()
            if not self._all_results:
                empty = Gtk.Label(label="未找到结果")
                empty.set_css_classes(["empty-label"])
                _style_widget(empty)
                self._results_grid.append(empty)
            else:
                for result in self._all_results:
                    cell = self._create_grid_cell(result)
                    self._results_grid.append(cell)
            first = self._results_grid.get_child_at_index(0)
            if first:
                self._results_grid.select_child(first)
        else:
            child = self._results_list.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self._results_list.remove(child)
                child = next_child
            if not self._all_results:
                empty = Gtk.Label(label="未找到结果")
                empty.set_css_classes(["empty-label"])
                _style_widget(empty)
                self._results_list.append(empty)
            else:
                for result in self._all_results:
                    row = self._create_result_row(result)
                    self._results_list.append(row)
            first = self._results_list.get_row_at_index(0)
            if first:
                self._results_list.select_row(first)

    def _create_result_row(self, result: SearchResult) -> Gtk.ListBoxRow:
        """Minimal list row: icon + name only."""
        density = self._config.get("result_density", "comfortable")
        density_specs = {
            "compact": {"icon_px": 20, "icon_box": 30, "pad_y": 5, "spacing": 9},
            "comfortable": {"icon_px": 22, "icon_box": 34, "pad_y": 7, "spacing": 10},
            "airy": {"icon_px": 24, "icon_box": 38, "pad_y": 9, "spacing": 12},
        }
        ds = density_specs.get(density, density_specs["comfortable"])
        show_desc = self._config.get("show_result_descriptions", True)

        row = Gtk.ListBoxRow()
        row._result = result
        row.set_css_classes(["result-row"])
        _style_widget(row)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=ds["spacing"])
        hbox.set_margin_start(8)
        hbox.set_margin_end(8)
        hbox.set_margin_top(ds["pad_y"])
        hbox.set_margin_bottom(ds["pad_y"])
        hbox.set_css_classes(["result-hbox"])
        _style_widget(hbox)
        row.set_child(hbox)

        icon_name = result.icon or "application-x-executable"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(ds["icon_px"])
        icon.set_css_classes(["result-icon"])
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_size_request(ds["icon_box"], ds["icon_box"])
        _style_widget(icon)
        hbox.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)
        text_box.set_size_request(1, -1)
        _style_widget(text_box)

        name_label = Gtk.Label(label=result.name)
        name_label.set_css_classes(["result-name"])
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        _style_widget(name_label)
        text_box.append(name_label)

        if show_desc and result.description:
            desc = result.description.strip().replace("\n", " ")
            if len(desc) > 88:
                desc = desc[:88] + "..."
            desc_label = Gtk.Label(label=desc)
            desc_label.set_css_classes(["result-desc"])
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_hexpand(True)
            desc_label.set_ellipsize(Pango.EllipsizeMode.END)
            _style_widget(desc_label)
            text_box.append(desc_label)

        hbox.append(text_box)

        # Very subtle type indicator on hover
        hint_map = {
            "app": "↵",
            "folder": "文件夹",
            "web": "网页",
            "search": "搜索",
            "calculator": "复制",
            "timestamp": "复制",
            "note": "保存",
        }
        hint = hint_map.get(result.action_type, "")
        if hint:
            hint_label = Gtk.Label(label=hint)
            hint_label.set_css_classes(["shortcut-hint"])
            hint_label.set_valign(Gtk.Align.CENTER)
            hint_label.set_halign(Gtk.Align.END)
            _style_widget(hint_label)
            hbox.append(hint_label)

        return row

    def _create_grid_cell(self, result: SearchResult) -> Gtk.FlowBoxChild:
        """Create a grid cell like Windows Start pinned tiles: icon + name below."""
        cell = Gtk.FlowBoxChild()
        cell._result = result
        classes = ["grid-cell"]
        if result.action_type == "app":
            classes.append("grid-cell-app")
        elif result.action_type == "folder":
            classes.append("grid-cell-folder")
        elif result.action_type == "web":
            classes.append("grid-cell-web")
        cell.set_css_classes(classes)
        _style_widget(cell)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        vbox.set_halign(Gtk.Align.CENTER)
        vbox.set_valign(Gtk.Align.CENTER)
        _style_widget(vbox)

        # App icon (larger, 28px)
        icon_name = result.icon or "application-x-executable"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(28)
        icon.set_css_classes(["grid-icon"])
        _style_widget(icon)
        vbox.append(icon)

        # Name label below
        name_label = Gtk.Label(label=result.name)
        name_label.set_css_classes(["grid-name"])
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(12)
        name_label.set_lines(1)
        name_label.set_halign(Gtk.Align.CENTER)
        _style_widget(name_label)
        vbox.append(name_label)

        cell.set_child(vbox)
        return cell

    def _on_row_activated(self, _listbox, row):
        """Handle row activation in list layout."""
        self._do_launch(row)

    def _on_grid_child_activated(self, _flowbox, child):
        """Handle child activation in grid layout."""
        self._do_launch(child)

    def _do_launch(self, widget):
        """Launch the result from a widget (ListBoxRow or FlowBoxChild)."""
        result = getattr(widget, "_result", None)
        if result:
            self._do_launch_from_result(result)

    def _on_search_activate(self, _entry):
        """Handle Enter key: auto-execute command results, or activate selected item."""
        # If there's a command result (calculator, timestamp, note), auto-execute it
        if self._all_results:
            first = self._all_results[0]
            if first.action_type in ("calculator", "timestamp", "note"):
                self._do_launch_from_result(first)
                return
        # Otherwise use the selected row
        layout = self._config.get("layout", "list")
        if layout == "grid":
            selected = self._results_grid.get_selected_child()
            if selected:
                self._do_launch(selected)
            elif self._all_results:
                self._do_launch_from_result(self._all_results[0])
        else:
            selected = self._results_list.get_selected_row()
            if selected:
                self._on_row_activated(self._results_list, selected)
            else:
                first = self._results_list.get_row_at_index(0)
                if first:
                    self._on_row_activated(self._results_list, first)

    def _do_launch_from_result(self, result):
        """Execute a SearchResult directly (without widget)."""
        if result.action_type == "app":
            launch_app(result.action_data)
        elif result.action_type == "folder":
            open_folder(result.action_data)
        elif result.action_type in ("web", "search"):
            open_url(result.action_data)
        elif result.action_type == "calculator":
            self._copy_to_clipboard(result.action_data)
        elif result.action_type == "timestamp":
            self._copy_to_clipboard(result.action_data)
        elif result.action_type == "note":
            self._save_quick_note(result.action_data)
        from lume.tools.usage import record_launch
        record_launch(result.action_data)
        self._close_launcher()

    def _refresh_clipboard(self):
        """Refresh clipboard items — manual wrapping for text + image thumbnails."""
        child = self._clipboard_grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._clipboard_grid.remove(child)
            child = nxt

        entries = self._clipboard.get_history()
        if not entries:
            self._clear_all_btn.set_visible(False)
            return
        self._clear_all_btn.set_visible(True)

        panel_w = self._config.get("launcher_width", 680)
        avail_w = panel_w - 12
        spacing = 6

        # Temp label for text measurement
        temp = Gtk.Label()
        temp.set_css_classes(["clipboard-item"])
        _style_widget(temp)
        ctx = temp.get_pango_context()
        pango = Pango.Layout(ctx)

        rows = []
        cur_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
        cur_row.set_halign(Gtk.Align.START)
        cur_row.set_valign(Gtk.Align.CENTER)
        remaining = avail_w

        for entry in entries:
            if entry.content_type == "image":
                item_w = self._make_clipboard_image(entry, cur_row, avail_w, remaining, rows, spacing)
                cur_row = item_w["row"]
                remaining = item_w["remaining"]
                continue

            # --- Text entry (original logic) ---
            prefix = "📌 " if entry.pinned else ""
            text = prefix + entry.text
            if len(text) > 8:
                display = text[:8] + "…"
            else:
                display = text

            pango.set_text(display)
            txt_w, txt_h = pango.get_pixel_size()
            item_w = txt_w + 16

            if item_w > remaining and remaining < avail_w:
                rows.append(cur_row)
                cur_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
                cur_row.set_halign(Gtk.Align.START)
                cur_row.set_valign(Gtk.Align.CENTER)
                remaining = avail_w

            lbl = Gtk.Label(label=display)
            lbl.set_xalign(0)
            lbl.set_valign(Gtk.Align.CENTER)
            wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            wrapper._clipboard_entry = entry
            wrapper.set_tooltip_text(entry.text)
            wrapper.set_valign(Gtk.Align.CENTER)
            wrapper.set_vexpand(False)
            wrapper.set_size_request(-1, 30)
            wrapper_css = ["clipboard-item"]
            if entry.pinned:
                wrapper_css.append("clipboard-pinned")
            wrapper.set_css_classes(wrapper_css)
            _style_widget(wrapper)
            wrapper.append(lbl)

            gesture = Gtk.GestureClick()
            gesture.set_button(0)
            gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            gesture.connect("pressed", self._on_clipboard_gesture, wrapper)
            wrapper.add_controller(gesture)

            cur_row.append(wrapper)
            remaining -= item_w + spacing

        if cur_row.get_first_child():
            rows.append(cur_row)

        for row in rows:
            self._clipboard_grid.append(row)

    def _make_clipboard_image(self, entry, cur_row, avail_w, remaining, rows, spacing):
        """Build image thumbnail with hover preview and right-click context menu."""
        THUMB_HEIGHT = 42
        MAX_THUMB_WIDTH = 96
        MIN_THUMB_WIDTH = 42

        thumb_w = MIN_THUMB_WIDTH
        texture = None
        if entry.image_path and Path(entry.image_path).exists():
            try:
                texture = Gdk.Texture.new_from_filename(entry.image_path)
                w = texture.get_width() or 1
                h = texture.get_height() or 1
                thumb_w = max(MIN_THUMB_WIDTH, min(MAX_THUMB_WIDTH, int(THUMB_HEIGHT * w / h)))
            except GLib.GError:
                texture = None

        item_w = thumb_w + 12

        if item_w > remaining and remaining < avail_w:
            rows.append(cur_row)
            cur_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
            cur_row.set_halign(Gtk.Align.START)
            cur_row.set_valign(Gtk.Align.CENTER)
            remaining = avail_w

        wrapper = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        wrapper._clipboard_entry = entry
        wrapper._clipboard_texture = texture
        wrapper.set_tooltip_text("📷 左键复制 · 右键菜单" if texture else "图片缓存暂不可用")
        wrapper.set_size_request(item_w, THUMB_HEIGHT + 8)
        wrapper.set_hexpand(False)
        wrapper.set_valign(Gtk.Align.CENTER)
        wrapper.set_vexpand(False)
        wrapper_css = ["clipboard-image-item"]
        if entry.pinned:
            wrapper_css.append("clipboard-pinned")
        wrapper.set_css_classes(wrapper_css)
        _style_widget(wrapper)

        motion = Gtk.EventControllerMotion()
        motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        motion.connect("enter", lambda m, x, y, w=wrapper: self._on_img_enter(w))
        motion.connect("leave", lambda m, w=wrapper: self._on_img_leave(w))
        wrapper.add_controller(motion)

        if texture:
            pic = Gtk.Picture.new_for_paintable(texture)
            pic.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
            pic.set_size_request(thumb_w, THUMB_HEIGHT)
            pic.set_halign(Gtk.Align.CENTER)
            pic.set_valign(Gtk.Align.CENTER)
            pic.set_css_classes(["clipboard-thumb"])
            _style_widget(pic)
            wrapper.append(pic)
        else:
            icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic")
            icon.set_pixel_size(22)
            icon.set_size_request(thumb_w, THUMB_HEIGHT)
            icon.set_halign(Gtk.Align.CENTER)
            icon.set_valign(Gtk.Align.CENTER)
            _style_widget(icon)
            wrapper.append(icon)

        # Same as text items: CAPTURE phase to reliably receive all clicks
        gesture = Gtk.GestureClick()
        gesture.set_button(0)
        gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        gesture.connect("pressed", self._on_clipboard_gesture, wrapper)
        wrapper.add_controller(gesture)

        cur_row.append(wrapper)
        remaining -= item_w + spacing
        return {"row": cur_row, "remaining": remaining}
    # ---- Image hover preview (Popover on wrapper, single parent) ----
    def _on_img_enter(self, wrapper):
        wrapper._hovering = True
        t = getattr(wrapper, '_hover_timer', None)
        if t:
            GLib.source_remove(t)
        wrapper._hover_timer = GLib.timeout_add(300, self._show_preview_pop, wrapper)

    def _on_img_leave(self, wrapper):
        wrapper._hovering = False
        t = getattr(wrapper, '_hover_timer', None)
        if t:
            GLib.source_remove(t)
            wrapper._hover_timer = None
        pop = getattr(wrapper, '_preview_pop', None)
        if pop:
            try: pop.popdown()
            except: pass

    def _show_preview_pop(self, wrapper):
        wrapper._hover_timer = None
        if not getattr(wrapper, '_hovering', False):
            return False
        if getattr(wrapper, '_context_open', False):
            return False
        texture = getattr(wrapper, '_clipboard_texture', None)
        if not texture:
            entry = getattr(wrapper, '_clipboard_entry', None)
            if entry and entry.image_path and Path(entry.image_path).exists():
                try:
                    texture = Gdk.Texture.new_from_filename(entry.image_path)
                    wrapper._clipboard_texture = texture
                except GLib.GError as e:
                    print(f"Clipboard preview load failed: {e}")
        if not texture:
            return False

        pop = getattr(wrapper, '_preview_pop', None)
        if not pop:
            pop = Gtk.Popover()
            pop.set_autohide(False)
            pop.set_has_arrow(True)
            pop.set_position(Gtk.PositionType.TOP)
            pop.set_parent(wrapper)
            wrapper._preview_pop = pop

        pic = Gtk.Picture.new_for_paintable(texture)
        pic.set_content_fit(Gtk.ContentFit.SCALE_DOWN)
        pic.set_size_request(280, 200)
        pic.set_css_classes(["clipboard-thumb"])
        _style_widget(pic)
        pop.set_child(pic)
        try:
            pop.popup()
        except Exception:
            pass
        return False    # ---- Image context menu (created lazily on right-click) ----
    def _show_img_context(self, wrapper):
        entry = wrapper._clipboard_entry
        if not entry:
            return
        ctx = getattr(wrapper, '_ctx_menu', None)
        if not ctx:
            ctx = Gtk.Popover()
            ctx.set_autohide(True)
            ctx.set_has_arrow(False)
            ctx_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            ctx_box.set_margin_top(2)
            ctx_box.set_margin_bottom(2)
            ctx_box.set_margin_start(2)
            ctx_box.set_margin_end(2)

            save_btn = Gtk.Button(label="💾 保存截图...")
            save_btn.add_css_class("flat")
            save_btn.add_css_class("clipboard-context-btn")
            save_btn._entry = entry
            save_btn._ctx = ctx
            save_btn.connect("clicked", self._on_ctx_save)
            ctx_box.append(save_btn)

            del_btn = Gtk.Button(label="🗑 删除")
            del_btn.add_css_class("flat")
            del_btn.add_css_class("clipboard-context-btn")
            del_btn._entry = entry
            del_btn._ctx = ctx
            del_btn.connect("clicked", self._on_ctx_delete)
            ctx_box.append(del_btn)

            ctx.set_child(ctx_box)
            ctx.set_parent(wrapper)
            ctx.connect("closed", lambda *a, w=wrapper: setattr(w, '_context_open', False))
            wrapper._ctx_menu = ctx
        # Hide preview popover if visible while context menu is open
        pop = getattr(wrapper, '_preview_pop', None)
        if pop:
            try: pop.popdown()
            except: pass
        try:
            ctx.popup()
            wrapper._context_open = True
        except Exception:
            pass

    def _on_ctx_save(self, btn):
        entry = getattr(btn, '_entry', None)
        ctx = getattr(btn, '_ctx', None)
        if ctx:
            try: ctx.popdown()
            except: pass
        if not entry:
            return
        now = datetime.now()
        default_name = now.strftime("%Y-%m-%d-%H-%M-%S") + ".png"
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(default_name)
        dialog.set_title("保存截图")
        parent_win = self.get_root() if self.get_root() is not None else None
        dialog.save(parent_win, None, self._on_img_save_done, entry)

    def _on_ctx_delete(self, btn):
        entry = getattr(btn, '_entry', None)
        ctx = getattr(btn, '_ctx', None)
        if ctx:
            try: ctx.popdown()
            except: pass
        if entry:
            self._clipboard.remove_entry(entry.entry_id)
            self._refresh_clipboard()

    def _on_img_save_done(self, dialog, result, entry):
        try:
            gfile = dialog.save_finish(result)
            dst = gfile.get_path()
            if dst and entry.image_path:
                shutil.copy(entry.image_path, dst)
        except GLib.GError:
            pass
    def _on_clipboard_gesture(self, gesture, n_press, x, y, child):
        """Handle clipboard item gestures with delay for single/double click distinction."""
        entry = child._clipboard_entry
        if not entry:
            return

        button = gesture.get_current_button()

        if button == 3:  # Right click
            self._cancel_pending(child)
            if entry.content_type == "image":
                self._show_img_context(child)
                return
            else:
                # Text: delete entry
                self._clipboard.remove_entry(entry.entry_id)
                self._refresh_clipboard()
                return

        if button == 1:  # Left click
            if getattr(child, '_context_open', False):
                return
            if n_press == 1:
                self._cancel_pending(child)
                child._pin_timeout = GLib.timeout_add(
                    280, self._on_clipboard_single, child
                )
            elif n_press == 2:
                self._cancel_pending(child)
                self._clipboard.toggle_pin(entry.entry_id)
                self._refresh_clipboard()

    def _cancel_pending(self, btn):
        """Cancel a pending single-click timeout on a button."""
        timeout = getattr(btn, '_pin_timeout', None)
        if timeout:
            GLib.source_remove(timeout)
            btn._pin_timeout = None

    def _on_clipboard_single(self, btn):
        """Delayed single-click action: copy to clipboard and close."""
        btn._pin_timeout = None
        entry = btn._clipboard_entry
        if entry:
            self._copy_to_clipboard(entry)
            if self._on_select:
                self._on_select("clipboard", entry.text or "📷 图片")
            self._close_launcher()
        return False  # don't repeat

    def _on_clipboard_clear_all(self, _btn):
        """Clear all clipboard history."""
        self._clipboard.clear_all()
        self._refresh_clipboard()

    def _copy_to_clipboard(self, entry_or_text):
        """Copy entry (text or image) to system clipboard."""
        display = Gdk.Display.get_default()
        if display is None:
            print("Clipboard copy failed: Gdk.Display is unavailable")
            return
        clipboard = display.get_clipboard()

        if isinstance(entry_or_text, ClipboardEntry):
            entry = entry_or_text
            if entry.content_type == "image" and entry.image_path:
                try:
                    texture = Gdk.Texture.new_from_filename(entry.image_path)
                    value = GObject.Value()
                    value.init(Gdk.Texture)
                    value.set_object(texture)
                    clipboard.set_content(Gdk.ContentProvider.new_for_value(value))
                except (GLib.Error, OSError) as e:
                    print(f"Image clipboard copy failed: {e}")
                return
            else:
                text = entry.text
        else:
            text = entry_or_text

        if text is not None:
            value = GObject.Value()
            value.init(str)
            value.set_string(str(text))
            clipboard.set_content(Gdk.ContentProvider.new_for_value(value))

    def _save_quick_note(self, content):
        """Save a quick note to ~/.local/share/lume/notes/."""
        notes_dir = get_data_dir() / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        now = datetime.now()
        filename = now.strftime("%Y-%m-%d-%H-%M-%S") + ".md"
        filepath = notes_dir / filename
        try:
            filepath.write_text(f"# 快捷笔记\n\n{content}\n\n---\n创建: {now.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
            print(f"📝 笔记已保存: {filepath}")
        except Exception as e:
            print(f"❌ 笔记保存失败: {e}")

    def _on_clipboard_clicked(self, button):
        if entry:
            self._copy_to_clipboard(entry)
            if self._on_select:
                self._on_select("clipboard", entry.text or "📷 图片")
            self._close_launcher()

    def _on_clipboard_activated(self, _flow, child):
        widget = child.get_child()
        entry = widget._clipboard_entry
        if entry:
            self._copy_to_clipboard(entry)
            if self._on_select:
                self._on_select("clipboard", entry.text or "📷 图片")
            self._close_launcher()

    def _close_launcher(self):
        if self._on_select:
            self._on_select("close", None)

    def update_paned_position(self):
        """Recalculate the paned divider position based on window height."""
        if hasattr(self, '_paned'):
            # Only update if user hasn't manually dragged
            saved = self._config.get("paned_position", 0)
            if saved == 0:
                h = self._config.get("launcher_height", 720)
                self._paned.set_position(max(200, h - 220))

    def _on_paned_position_changed(self, paned, _pspec):
        """Save divider position to config when user drags it (debounced)."""
        pos = paned.get_position()
        self._config["paned_position"] = pos
        # Debounce: cancel pending save, schedule a new one in 300ms
        if hasattr(self, '_paned_save_timer') and self._paned_save_timer:
            GLib.source_remove(self._paned_save_timer)
        self._paned_save_timer = GLib.timeout_add(300, self._do_save_paned_pos)

    def _do_save_paned_pos(self):
        """Actually write paned position to disk."""
        self._paned_save_timer = 0
        try:
            save_config(self._config)
        except Exception as e:
            print(f"Failed to save paned position: {e}")
        return False

    def on_clipboard_updated(self, entry, history):
        GLib.idle_add(self._refresh_clipboard)

    def focus_search(self):
        self._search_entry.grab_focus()

    def clear_search(self):
        """Reset search and rebuild results (blocks signal to avoid double rebuild)."""
        self._search_entry.handler_block(self._search_changed_hid)
        self._search_entry.set_text("")
        self._search_entry.handler_unblock(self._search_changed_hid)
        self._all_results = search("", self._config)
        self._rebuild_results()
        # Force-read current clipboard so newly copied items appear immediately
        self._poll_clipboard_now()

    def _poll_clipboard_now(self):
        """Read current clipboard (text or image) and merge into history immediately."""
        display = Gdk.Display.get_default()
        if not display:
            self._refresh_clipboard()
            return
        clipboard = display.get_clipboard()
        clipboard.read_text_async(None, self._on_poll_clipboard_done, None)

    def _on_poll_clipboard_done(self, clipboard, result, _user_data):
        """Callback after force-reading clipboard text — fallback to image."""
        try:
            text = clipboard.read_text_finish(result)
            if text and text.strip():
                self._clipboard.add_entry(text.strip())
                self._refresh_clipboard()
                return
        except GLib.GError:
            pass
        # No text — try image
        clipboard.read_texture_async(None, self._on_poll_image_done, None)

    def _on_poll_image_done(self, clipboard, result, _user_data):
        """Callback after force-reading clipboard image."""
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                self._clipboard.add_image_entry(texture)
        except GLib.GError:
            pass
        finally:
            self._refresh_clipboard()
