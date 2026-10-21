#!/bin/bash
# Lume Launcher — Linux 构建脚本
# 构建目录式可执行程序，依赖随程序目录分发
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
.venv/bin/python -m pip install -q PySide6==6.11.1 PyInstaller==6.21.0 pypinyin==0.55.0

# 3) 构建
echo "[3/4] 构建 Lume..."
rm -rf build dist
.venv/bin/pyinstaller --clean \
    --name "Lume" \
    --specpath build \
    --onedir \
    --windowed \
    --add-data "$PROJECT_DIR/lume-128.png:." \
    --add-data "$PROJECT_DIR/lume-256.png:." \
    --add-data "$PROJECT_DIR/lume-512.png:." \
    --add-data "$PROJECT_DIR/lume_shell_extension:lume_shell_extension" \
    --add-data "$PROJECT_DIR/lume/resources/smartisan:lume/resources/smartisan" \
    --hidden-import "PySide6.QtNetwork" \
    --hidden-import "PySide6.QtGui" \
    --hidden-import "lume.search" \
    --hidden-import "lume.config" \
    --hidden-import "lume.themes" \
    --hidden-import "lume.tools.usage" \
    --hidden-import "pypinyin" \
    --icon "$PROJECT_DIR/lume-256.png" \
    main.py

EXE_SIZE="$(du -sh dist/Lume | cut -f1)"

# 4) 发布
echo "[4/4] 发布..."
mkdir -p "$OUTPUT_DIR"
rm -rf "$OUTPUT_DIR/Lume-linux-x86_64"
cp -a dist/Lume "$OUTPUT_DIR/Lume-linux-x86_64"
chmod +x "$OUTPUT_DIR/Lume-linux-x86_64/Lume"

echo ""
echo "===== 构建完成 ====="
echo "  程序目录: $OUTPUT_DIR/Lume-linux-x86_64"
echo "  文件大小: $EXE_SIZE"
echo "  运行方式: ./release/Lume-linux-x86_64/Lume"
echo ""

# 可选: 打包为 AppImage
if command -v appimagetool &>/dev/null; then
    echo "创建 AppImage..."
    mkdir -p "$OUTPUT_DIR/Lume.AppDir"
    cp -a dist/Lume/. "$OUTPUT_DIR/Lume.AppDir/"
    mv "$OUTPUT_DIR/Lume.AppDir/Lume" "$OUTPUT_DIR/Lume.AppDir/AppRun"
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
