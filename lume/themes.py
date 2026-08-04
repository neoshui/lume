"""Color scheme presets for Lume."""

# Each scheme is a complete appearance dict (light + dark).

THEMES = {
    "晨雾": {
        "panel_opacity": 0.97,
        "panel_bg_rgb": "247, 249, 252",
        "panel_bg_dark_rgb": "30, 32, 38",
        "text_color": "rgba(18, 24, 34, 0.96)",
        "text_dark_color": "rgba(245, 248, 252, 0.94)",
        "desc_color": "rgba(62, 73, 94, 0.72)",
        "desc_dark_color": "rgba(218, 226, 240, 0.56)",
        "search_bg": "rgba(255, 255, 255, 0.88)",
        "search_bg_dark": "rgb(43, 46, 54)",
        "accent_color": "rgb(125, 162, 216)",
        "border_radius": 18,
    },
    "瓷白": {
        "panel_opacity": 0.98,
        "panel_bg_rgb": "250, 250, 247",
        "panel_bg_dark_rgb": "31, 31, 29",
        "text_color": "rgba(28, 28, 24, 0.94)",
        "text_dark_color": "rgba(247, 247, 241, 0.94)",
        "desc_color": "rgba(77, 78, 68, 0.68)",
        "desc_dark_color": "rgba(226, 225, 214, 0.54)",
        "search_bg": "rgba(255, 255, 252, 0.9)",
        "search_bg_dark": "rgb(47, 47, 43)",
        "accent_color": "rgb(121, 184, 155)",
        "border_radius": 16,
    },
    "鼠尾草": {
        "panel_opacity": 0.97,
        "panel_bg_rgb": "244, 249, 244",
        "panel_bg_dark_rgb": "27, 34, 29",
        "text_color": "rgba(20, 31, 24, 0.95)",
        "text_dark_color": "rgba(239, 247, 241, 0.94)",
        "desc_color": "rgba(58, 78, 63, 0.68)",
        "desc_dark_color": "rgba(208, 224, 212, 0.54)",
        "search_bg": "rgba(252, 255, 252, 0.86)",
        "search_bg_dark": "rgb(40, 50, 43)",
        "accent_color": "rgb(169, 149, 211)",
        "border_radius": 18,
    },
    "薄暮": {
        "panel_opacity": 0.96,
        "panel_bg_rgb": "248, 246, 251",
        "panel_bg_dark_rgb": "33, 31, 41",
        "text_color": "rgba(31, 27, 40, 0.95)",
        "text_dark_color": "rgba(246, 242, 252, 0.94)",
        "desc_color": "rgba(76, 66, 94, 0.66)",
        "desc_dark_color": "rgba(223, 215, 238, 0.56)",
        "search_bg": "rgba(255, 255, 255, 0.84)",
        "search_bg_dark": "rgb(50, 47, 61)",
        "accent_color": "rgb(214, 163, 106)",
        "border_radius": 20,
    },
    "雾蓝": {
        "panel_opacity": 0.97,
        "panel_bg_rgb": "242, 248, 250",
        "panel_bg_dark_rgb": "26, 34, 39",
        "text_color": "rgba(18, 34, 41, 0.95)",
        "text_dark_color": "rgba(235, 246, 250, 0.94)",
        "desc_color": "rgba(48, 77, 88, 0.68)",
        "desc_dark_color": "rgba(205, 224, 232, 0.54)",
        "search_bg": "rgba(252, 255, 255, 0.86)",
        "search_bg_dark": "rgb(38, 50, 56)",
        "accent_color": "rgb(213, 139, 154)",
        "border_radius": 18,
    },
    "石墨": {
        "panel_opacity": 0.96,
        "panel_bg_rgb": "245, 246, 247",
        "panel_bg_dark_rgb": "25, 26, 29",
        "text_color": "rgba(24, 27, 31, 0.95)",
        "text_dark_color": "rgba(242, 244, 247, 0.94)",
        "desc_color": "rgba(71, 78, 88, 0.66)",
        "desc_dark_color": "rgba(207, 213, 222, 0.54)",
        "search_bg": "rgba(255, 255, 255, 0.86)",
        "search_bg_dark": "rgb(39, 41, 47)",
        "accent_color": "rgb(120, 184, 200)",
        "border_radius": 14,
    },
    "暖纸": {
        "panel_opacity": 0.98,
        "panel_bg_rgb": "250, 247, 239",
        "panel_bg_dark_rgb": "36, 32, 27",
        "text_color": "rgba(38, 32, 24, 0.95)",
        "text_dark_color": "rgba(250, 244, 234, 0.94)",
        "desc_color": "rgba(93, 73, 48, 0.64)",
        "desc_dark_color": "rgba(231, 216, 195, 0.54)",
        "search_bg": "rgba(255, 252, 246, 0.88)",
        "search_bg_dark": "rgb(52, 45, 37)",
        "accent_color": "rgb(147, 160, 178)",
        "border_radius": 16,
    },
}


def list_themes() -> list[str]:
    """Return theme names in the curated display order."""
    return list(THEMES.keys())


def get_theme(name: str) -> dict:
    """Return the appearance dict for a named theme, or None."""
    return THEMES.get(name)


def apply_theme(config: dict, theme_name: str) -> dict:
    """Apply a named theme's appearance values to the config."""
    theme = get_theme(theme_name)
    if theme is None:
        return config
    config["appearance"] = dict(theme)
    return config
