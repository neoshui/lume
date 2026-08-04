#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../lume_shell_extension" && pwd)"
uuid="lume-clipboard@lume.app"

command -v zip >/dev/null || {
  echo "缺少 zip 命令；请直接在 Lume 的 设置 → 快捷键 中点击“安装并启用”。" >&2
  exit 1
}

archive="$(mktemp -p "${TMPDIR:-/tmp}" --suffix=.zip lume-shell-extension.XXXXXX)"
trap 'rm -f "$archive"' EXIT
# zip treats the empty file created by mktemp as a corrupt existing archive.
rm -f "$archive"
(
  cd "$source_dir"
  zip -q -j "$archive" metadata.json extension.js
)
gnome-extensions install --force "$archive"
for _ in {1..10}; do
  gnome-extensions info "$uuid" >/dev/null 2>&1 && break
  sleep 0.25
done
 # Force a lifecycle reload when upgrading an already-enabled extension.
 # Merely calling enable leaves GNOME Shell's old JavaScript module alive.
gnome-extensions disable "$uuid" >/dev/null 2>&1 || true
disabled_state=""
for _ in {1..20}; do
  disabled_state="$(gnome-extensions info "$uuid" 2>/dev/null | sed -n 's/^[[:space:]]*State:[[:space:]]*//p' | head -n 1)"
  [[ "$disabled_state" == "INACTIVE" || "$disabled_state" == "DISABLED" ]] && break
  sleep 0.25
done
gnome-extensions enable "$uuid"
state=""
for _ in {1..20}; do
  state="$(gnome-extensions info "$uuid" 2>/dev/null | sed -n 's/^[[:space:]]*State:[[:space:]]*//p' | head -n 1)"
  [[ "$state" == "ACTIVE" ]] && break
  sleep 0.25
done
if [[ "$state" != "ACTIVE" ]]; then
  echo "GNOME Shell 扩展未处于 ACTIVE 状态（当前：${state:-unknown}）。" >&2
  exit 1
fi
echo "Lume GNOME Shell clipboard bridge enabled."
