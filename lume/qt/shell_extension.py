"""One-click installer for Lume's own GNOME Shell clipboard component."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

UUID = "lume-clipboard@lume.app"


def target_dir() -> Path:
    return Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / UUID


def source_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "lume_shell_extension"
    return Path(__file__).resolve().parents[2] / "lume_shell_extension"


def is_enabled() -> bool:
    if not (target_dir() / "metadata.json").is_file():
        return False
    try:
        result = subprocess.run(
            ["gnome-extensions", "info", UUID],
            capture_output=True, text=True, timeout=3, check=False,
        )
        # An extension can be listed as enabled while its enable() method has
        # already thrown.  Treat ERROR as unavailable so the UI does not tell
        # the user that background clipboard capture is working when it is not.
        state = ""
        for line in result.stdout.splitlines():
            if line.strip().lower().startswith("state:"):
                state = line.split(":", 1)[1].strip().upper()
                break
        if state == "ACTIVE":
            return True
        if state in {"ERROR", "DISABLED", "INACTIVE"}:
            return False

        # GNOME 50 can return status 2 with no output from the extensions
        # CLI even though the Shell extension service and gsettings are
        # healthy.  The enabled-extensions key is the persistent source of
        # truth for whether this UUID is enabled; use it as a compatibility
        # fallback when `info` is unavailable.
        listed = subprocess.run(
            ["gnome-extensions", "list"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        # Some GNOME/dconf setups return status 2 while still printing a
        # complete, usable extension list.  The output is the useful signal
        # here; do not discard it solely because of the exit status.
        listed_names = listed.stdout.splitlines()
        if listed_names and UUID not in listed_names:
            return False
        # If the CLI produced no usable output (for example, GNOME returns
        # status 2 from a non-D-Bus-capable helper process), continue with the
        # persistent gsettings state below instead of reporting a false
        # negative.
        if not listed_names and listed.returncode == 0:
            return False
        settings = subprocess.run(
            ["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if settings.returncode != 0:
            return False
        value = settings.stdout.strip()
        if value.startswith("@as "):
            value = value[4:].lstrip()
        try:
            enabled = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return False
        return isinstance(enabled, (list, tuple)) and UUID in enabled
    except (OSError, subprocess.SubprocessError):
        return False


def install_and_enable() -> tuple[bool, str]:
    """Install the bundled extension for the current user; never needs sudo."""
    source = source_dir()
    if not (source / "metadata.json").is_file():
        return False, "找不到 Lume 剪切板组件文件。"
    try:
        # gnome-extensions install updates Shell's extension registry.  A
        # plain copy into ~/.local/share is not enough on GNOME 50, which is
        # why the previous installer reported “extension does not exist”.
        with tempfile.TemporaryDirectory(prefix="lume-shell-extension-") as temp:
            archive = Path(temp) / f"{UUID}.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                for item in source.iterdir():
                    if item.is_file():
                        bundle.write(item, item.name)
            installed = subprocess.run(
                ["gnome-extensions", "install", "--force", str(archive)],
                capture_output=True, text=True, timeout=5, check=False,
            )
        if installed.returncode != 0:
            detail = (installed.stderr or installed.stdout).strip()
            return False, f"注册组件失败：{detail or 'GNOME 未响应'}"

        # GNOME Shell updates its extension registry asynchronously.  Enabling
        # immediately after installation can otherwise race with that refresh
        # and misleadingly report that the UUID does not exist.
        registered = False
        for _ in range(10):
            known = subprocess.run(
                ["gnome-extensions", "info", UUID],
                capture_output=True, text=True, timeout=3, check=False,
            )
            if known.returncode == 0:
                registered = True
                break
            time.sleep(0.25)
        if not registered:
            return False, (
                "组件已安装，但 GNOME Shell 尚未完成注册。请注销并重新登录，"
                "然后在“设置 → 快捷键”中再次点击“安装并启用”。"
            )
        result = subprocess.run(
            ["gnome-extensions", "enable", UUID],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"安装组件失败：{exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return False, f"组件已注册，但无法启用：{detail or 'GNOME 未响应'}"
    try:
        verification = subprocess.run(
            ["gnome-extensions", "info", UUID],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"组件已启用，但无法确认运行状态：{exc}"
    if verification.returncode != 0 or "State: ACTIVE" not in verification.stdout:
        return False, (
            "组件已安装，但 GNOME Shell 没有成功加载它。请注销并重新登录后，"
            "再打开 Lume 点击“安装并启用”。"
        )
    return True, "Lume 剪切板组件已启用。"
