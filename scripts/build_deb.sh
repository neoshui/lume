#!/bin/bash
# Build a Debian package from the Linux PyInstaller onedir bundle.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
APP_DIR="$PROJECT_DIR/release/Lume-linux-x86_64"
VERSION="$(python3 "$PROJECT_DIR/scripts/validate_version.py")"
ARCH="${DEB_ARCH:-amd64}"
PKG_ROOT="$PROJECT_DIR/build/deb-root"
OUTPUT="$PROJECT_DIR/release/Lume_${VERSION}_${ARCH}.deb"

if [[ ! -x "$APP_DIR/Lume" ]]; then
  echo "Linux onedir build not found: $APP_DIR/Lume" >&2
  echo "Run bash build_linux.sh first." >&2
  exit 1
fi

rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/DEBIAN" "$PKG_ROOT/opt/lume" \
  "$PKG_ROOT/usr/bin" "$PKG_ROOT/usr/share/applications" \
  "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"
cp -a "$APP_DIR/." "$PKG_ROOT/opt/lume/"

cat > "$PKG_ROOT/usr/bin/lume" <<'EOF'
#!/bin/sh
exec /opt/lume/Lume "$@"
EOF
chmod 0755 "$PKG_ROOT/usr/bin/lume" "$PKG_ROOT/opt/lume/Lume"
install -m 0644 "$PROJECT_DIR/lume-256.png" \
  "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/com.lume.launcher.png"

cat > "$PKG_ROOT/usr/share/applications/com.lume.launcher.desktop" <<'EOF'
[Desktop Entry]
Name=Lume
Comment=Desktop launcher and clipboard manager
Exec=/usr/bin/lume
Icon=com.lume.launcher
Type=Application
Categories=Utility;
StartupWMClass=Lume
Terminal=false
StartupNotify=false
EOF

cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: lume
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Lume contributors
Description: Desktop launcher and clipboard manager
 Lume searches applications, files, URLs and commands, and keeps clipboard history.
Depends: libc6, libstdc++6, libgcc-s1, libglib2.0-0 | libglib2.0-0t64, libegl1, libxkbcommon0
EOF

mkdir -p "$PROJECT_DIR/release"
dpkg-deb --root-owner-group --build "$PKG_ROOT" "$OUTPUT"
echo "Debian package: $OUTPUT"
