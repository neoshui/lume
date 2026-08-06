"""User-level login startup integration for Lume."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path


APP_NAME = "Lume"
LINUX_AUTOSTART_NAME = "com.lume.launcher.desktop"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _linux_autostart_file() -> Path:
    return Path.home() / ".config" / "autostart" / LINUX_AUTOSTART_NAME


def _default_executable() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    launcher = Path.home() / ".local" / "bin" / "lume-launcher"
    if launcher.exists():
        return str(launcher)
    return str(Path(sys.argv[0]).resolve())


def _windows_command(executable: str) -> str:
    return f'"{executable}" --background'


def _linux_desktop_entry(executable: str) -> str:
    command = shlex.quote(executable) + " --background"
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Lume",
        "Comment=Lume launcher background service",
        f"Exec={command}",
        "X-GNOME-Autostart-enabled=true",
        "NoDisplay=true",
        "Hidden=false",
        "Terminal=false",
        "",
    ])


def is_autostart_enabled() -> bool:
    """Return whether Lume is configured to start for the current user."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_READ) as key:
                command, _kind = winreg.QueryValueEx(key, APP_NAME)
            return "--background" in str(command)
        except (ImportError, OSError):
            return False
    if sys.platform == "linux":
        path = _linux_autostart_file()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False
        return (
            "X-GNOME-Autostart-enabled=true" in text
            and "Hidden=false" in text
            and "--background" in text
        )
    return False


def set_autostart(enabled: bool, executable: str | None = None) -> tuple[bool, str]:
    """Enable or disable user-level login startup without administrator rights."""
    executable = executable or _default_executable()
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _windows_command(executable))
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                    except FileNotFoundError:
                        pass
            return True, "Windows 登录启动已更新。"

        if sys.platform == "linux":
            path = _linux_autostart_file()
            if enabled:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_linux_desktop_entry(executable), encoding="utf-8")
            else:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            return True, "Linux 登录启动已更新。"
    except (ImportError, OSError) as exc:
        return False, f"无法更新登录启动设置：{exc}"
    return False, "当前平台不支持登录启动设置。"
