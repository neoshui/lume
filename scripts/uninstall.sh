#!/bin/sh
set -eu

LAUNCHER="$HOME/.local/bin/lume-launcher"
INSTALL_DIR="$HOME/.local/lib/lume"
DESKTOP="$HOME/.local/share/applications/com.lume.launcher.desktop"
ICON="$HOME/.local/share/icons/hicolor/256x256/apps/com.lume.launcher.png"
UUID="lume-clipboard@lume.app"

if command -v gnome-extensions >/dev/null 2>&1; then
    gnome-extensions disable "$UUID" >/dev/null 2>&1 || true
    gnome-extensions uninstall "$UUID" >/dev/null 2>&1 || true
fi
rm -f "$LAUNCHER" "$DESKTOP" "$ICON" "$INSTALL_DIR/Lume"
rmdir "$INSTALL_DIR" 2>/dev/null || true
echo "Lume 已卸载；用户配置和剪贴板数据保留在 ~/.config/lume 与 ~/.local/share/lume。"
