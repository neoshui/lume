"""Configuration management for Lume GNOME Launcher."""

import copy
import json
import shutil
from pathlib import Path

from lume.log_utils import get_logger

log = get_logger(__name__)

CONFIG_DIR = Path.home() / ".config" / "lume"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = Path.home() / ".local" / "share" / "lume"


DEFAULT_CONFIG = {
    # Global shortcut key combo
    # Format: UPPERCASE_MODIFIER+key (e.g., "CTRL+space", "ALT+space", "CTRL+ALT+t")
    # Valid modifiers: CTRL, ALT, SHIFT, LOGO (Super), NUM (mod2)
    # Key names: space, a-z, Return, Tab, Escape, F1-F12, etc.
    "shortcut": "ALT+space",
    # Launcher window settings
    "launcher_width": 680,
    "launcher_height": 720,
    "launcher_vertical_offset": 140,
    "max_results": 999,
    # Layout: "list" | "grid"
    "layout": "list",
    # Result list personalization
    # result_density: "compact" | "comfortable" | "airy"
    "result_density": "comfortable",
    "show_result_descriptions": True,
    "show_result_tooltips": True,
    # Clipboard history
    "clipboard_max_entries": 50,
    "clipboard_auto_expire_hours": 0,
    "clipboard_max_text_length": 10000,
    "clipboard_max_image_bytes": 10 * 1024 * 1024,
    "clipboard_filter_sensitive": True,
    "clipboard_private_mode": False,
    "clipboard_cleanup_orphans": True,
    # Theme: "auto" | "light" | "dark"
    "theme": "auto",
    # Color palette layered on top of the light/dark mode.
    "color_theme": "晨雾",
    # Appearance customization
    "appearance": {
        "panel_opacity": 0.97,
        "panel_bg_rgb": "247, 249, 252",
        "panel_bg_dark_rgb": "30, 32, 38",
        "text_color": "rgba(18, 24, 34, 0.96)",
        "text_dark_color": "rgba(255, 255, 255, 0.92)",
        "desc_color": "rgba(62, 73, 94, 0.72)",
        "desc_dark_color": "rgba(225, 231, 242, 0.5)",
        "search_bg": "rgba(255, 255, 255, 0.86)",
        "search_bg_dark": "rgb(43, 46, 54)",
        "accent_color": "rgb(111, 148, 201)",
        "border_radius": 18,
    },
    # Quick web shortcuts
    "web_shortcuts": [
        {"name": "Google", "url": "https://google.com"},
        {"name": "GitHub", "url": "https://github.com"},
        {"name": "Bilibili", "url": "https://bilibili.com"},
    ],
    # Quick folder shortcuts
    "folder_shortcuts": [
        {"name": "Downloads", "path": "~/Downloads"},
        {"name": "Documents", "path": "~/Documents"},
        {"name": "Workspace", "path": "~/.hermes/workspace"},
    ],
    # Direct key bindings: shortcut -> action
    "key_bindings": {},
    # UI font size base (px, default 13)
    "font_size": 15,
    # Web search engine
    "search_engine": {
        "name": "Google",
        "url": "https://www.google.com/search?q={query}"
    },
}


def _merge_config(default: dict, user: dict) -> dict:
    """Merge user config over defaults, preserving nested default keys."""
    merged = copy.deepcopy(default)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


# ── Legacy migration (fuguang → lume) —───────────────────────────────
# These run at most once per machine. They can be removed in a future
# release once all existing users have been migrated.

_LEGACY_CONFIG_DIR = Path.home() / ".config" / "fuguang"
_LEGACY_CONFIG_FILE = _LEGACY_CONFIG_DIR / "config.json"
_LEGACY_DATA_DIR = Path.home() / ".local" / "share" / "fuguang"


def _migrate_legacy():
    """One-time migration from old fuguang paths to current lume paths."""
    migrated = False

    # Config file
    if not CONFIG_FILE.exists() and _LEGACY_CONFIG_FILE.exists():
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_LEGACY_CONFIG_FILE, CONFIG_FILE)
            log.info("Migrated config: ~/.config/fuguang → ~/.config/lume")
            migrated = True
        except OSError as e:
            log.warning("Failed to migrate config: %s", e)

    # Data directory
    if not DATA_DIR.exists() and _LEGACY_DATA_DIR.exists():
        try:
            shutil.copytree(_LEGACY_DATA_DIR, DATA_DIR)
            _rewrite_legacy_data_paths()
            log.info("Migrated data: ~/.local/share/fuguang → ~/.local/share/lume")
            migrated = True
        except OSError as e:
            log.warning("Failed to migrate data directory: %s", e)

    return migrated


def _rewrite_legacy_data_paths():
    """Rewrite absolute legacy paths inside copied data files."""
    history_file = DATA_DIR / "clipboard_history.json"
    if not history_file.exists():
        return

    try:
        data = json.loads(history_file.read_text())
        legacy_prefix = str(_LEGACY_DATA_DIR)
        data_prefix = str(DATA_DIR)
        changed = False
        for item in data:
            if not isinstance(item, dict):
                continue
            image_path = item.get("image_path")
            if isinstance(image_path, str) and image_path.startswith(legacy_prefix):
                item["image_path"] = data_prefix + image_path[len(legacy_prefix):]
                changed = True
        if changed:
            history_file.write_text(json.dumps(data, ensure_ascii=False))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to rewrite migrated data paths: %s", e)


# ── Public API ──────────────────────────────────────────────────────


def load_config() -> dict:
    """Load configuration from file, merging with defaults."""
    # One-time legacy migration (no-op after first run)
    _migrate_legacy()

    config = copy.deepcopy(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            user_config = json.loads(CONFIG_FILE.read_text())
            config = _merge_config(DEFAULT_CONFIG, user_config)
        except (json.JSONDecodeError, PermissionError) as e:
            log.warning("Failed to load config (%s), using defaults", e)

    # If the config still carries the old (pre-v2) accent palette from before
    # the theme system was introduced, nudge it to the current colour.
    _upgrade_accent_if_legacy(config)

    return config


def _upgrade_accent_if_legacy(config: dict):
    """One-shot palette refresh for users upgrading from early v1 presets."""
    LEGACY_ACCENTS = {
        "#5f7fb5": "#6f94c9", "#5f8b6f": "#7eaa91", "#8b7cb4": "#9d8bca",
        "#a98454": "#c19763", "#b56f7a": "#c78391", "#5291a5": "#6ea6b9",
        "#747e8b": "#8292a8", "rgb(105, 136, 181)": "rgb(111, 148, 201)",
    }
    appearance = config.get("appearance", {})
    accent = str(appearance.get("accent_color", "")).lower().replace(" ", "")
    for old, new in LEGACY_ACCENTS.items():
        if accent == old.replace(" ", "").lower():
            appearance["accent_color"] = new
            break


def save_config(config: dict):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def get_data_dir() -> Path:
    """Get the data directory for Lume (clipboard history, etc.)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
