#!/bin/bash
# Lume Launcher — Linux 构建脚本
# 构建单文件可执行文件，兼容所有 Linux x86_64 发行版
# 使用方法: bash build_linux.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$PROJECT_DIR/release"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python3"
cd "$PROJECT_DIR"

echo "===== Lume Linux 构建 ====="
echo ""

# 1) 虚拟环境
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv .venv
fi
echo "[1/4] 虚拟环境: $(.venv/bin/python --version 2>&1)"

# 2) 安装依赖
echo "[2/4] 安装依赖..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q PySide6==6.11.1 PyInstaller==6.21.0 pypinyin==0.55.0

# 3) 构建
echo "[3/4] 构建 Lume..."
rm -rf build dist
.venv/bin/pyinstaller --clean \
    --name "Lume" \
    --onefile \
    --windowed \
    --add-data "lume-128.png:." \
    --add-data "lume-256.png:." \
    --add-data "lume-512.png:." \
    --add-data "lume_shell_extension:lume_shell_extension" \
    --hidden-import "PySide6.QtNetwork" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "lume.search" \
    --hidden-import "lume.config" \
    --hidden-import "lume.themes" \
    --hidden-import "lume.tools.usage" \
    --hidden-import "pypinyin" \
    --icon "lume-256.png" \
    main.py

EXE_SIZE="$(du -h dist/Lume | cut -f1)"

# 4) 发布
echo "[4/4] 发布..."
mkdir -p "$OUTPUT_DIR"
cp dist/Lume "$OUTPUT_DIR/Lume-linux-x86_64"
chmod +x "$OUTPUT_DIR/Lume-linux-x86_64"

echo ""
echo "===== 构建完成 ====="
echo "  单文件可执行文件: $OUTPUT_DIR/Lume-linux-x86_64"
echo "  文件大小: $EXE_SIZE"
echo "  运行方式: ./release/Lume-linux-x86_64"
echo ""

# 可选: 打包为 AppImage
if command -v appimagetool &>/dev/null; then
    echo "创建 AppImage..."
    mkdir -p "$OUTPUT_DIR/Lume.AppDir"
    cp dist/Lume "$OUTPUT_DIR/Lume.AppDir/AppRun"
    cp lume-256.png "$OUTPUT_DIR/Lume.AppDir/lume.png"
    cat > "$OUTPUT_DIR/Lume.AppDir/lume.desktop" <<EOF
[Desktop Entry]
Name=Lume
Comment=Floating launcher for Linux
Exec=AppRun
Icon=lume
Type=Application
Categories=Utility;
EOF
    appimagetool "$OUTPUT_DIR/Lume.AppDir" "$OUTPUT_DIR/Lume-x86_64.AppImage"
    echo "  AppImage: $OUTPUT_DIR/Lume-x86_64.AppImage"
fi
