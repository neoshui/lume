#!/bin/bash
# Lume Launcher — 系统安装脚本
# 用法: sudo bash scripts/install.sh

set -e

AUTOSTART_MODE="preserve"
for arg in "$@"; do
    case "$arg" in
        --autostart) AUTOSTART_MODE="enable" ;;
        --no-autostart) AUTOSTART_MODE="disable" ;;
        --help|-h)
            echo "用法: $0 [--autostart|--no-autostart]"
            exit 0
            ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

PROJECT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
BINARY="$PROJECT_DIR/release/Lume-linux-x86_64"
ICON="lume-256.png"
LAUNCHER="$HOME/.local/bin/lume-launcher"
INSTALL_DIR="$HOME/.local/lib/lume"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_TARGET="$ICON_DIR/com.lume.launcher.png"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_TARGET="$DESKTOP_DIR/com.lume.launcher.desktop"
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_TARGET="$AUTOSTART_DIR/com.lume.launcher.desktop"

echo "===== Lume 安装 ====="

# 1) 复制可执行文件
mkdir -p "$HOME/.local/bin" "$INSTALL_DIR"
if [ -f "$BINARY" ]; then
    cp "$BINARY" "$INSTALL_DIR/Lume"
    chmod +x "$INSTALL_DIR/Lume"
    cat > "$LAUNCHER" <<EOF
#!/bin/sh
exec "$INSTALL_DIR/Lume" "\$@"
EOF
    chmod +x "$LAUNCHER"
    echo "[1/4] 可执行文件 -> $INSTALL_DIR/Lume"
else
    echo "错误: 未找到 $BINARY，请先运行 bash $PROJECT_DIR/build_linux.sh"
    exit 1
fi

# 2) 安装图标
mkdir -p "$ICON_DIR"
cp "$PROJECT_DIR/$ICON" "$ICON_TARGET"
echo "[2/4] 图标 -> $ICON_TARGET"

# 3) 创建 .desktop 文件（快捷键入口）
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_TARGET" <<EOF
[Desktop Entry]
Name=Lume Launcher
Comment=Floating launcher — search apps, clipboard, commands
Exec=$LAUNCHER
Icon=$ICON_DIR/com.lume.launcher.png
Type=Application
Categories=Utility;
Terminal=false
EOF
echo "[3/4] .desktop -> $DESKTOP_TARGET"

if [ "$AUTOSTART_MODE" = "enable" ]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_TARGET" <<EOF
[Desktop Entry]
Type=Application
Name=Lume
Comment=Lume launcher background service
Exec=$INSTALL_DIR/Lume --background
X-GNOME-Autostart-enabled=true
NoDisplay=true
Hidden=false
Terminal=false
EOF
    echo "      登录启动 -> $AUTOSTART_TARGET"
elif [ "$AUTOSTART_MODE" = "disable" ]; then
    rm -f "$AUTOSTART_TARGET"
    echo "      已关闭登录启动"
fi

if command -v gnome-extensions >/dev/null 2>&1 && [ -x "$PROJECT_DIR/scripts/install_lume_shell_extension.sh" ]; then
    "$PROJECT_DIR/scripts/install_lume_shell_extension.sh" || echo "警告: GNOME 剪贴板扩展安装失败，请在 Lume 设置中重试。"
fi
echo "[4/4] GNOME 剪贴板扩展（如适用）"

# 刷新图标缓存
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "✅ Lume 安装完成!"
echo "   可执行文件: $LAUNCHER"
echo "   按 Alt+Space 唤醒（需在 Lume 设置中绑定快捷键）"
