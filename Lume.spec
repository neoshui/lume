"""Shared PyInstaller configuration for the platform-specific runners."""

from pathlib import Path
import os
import sys


project_root = Path(SPECPATH)
console_mode = os.environ.get("LUME_CONSOLE") == "1"
datas = [
    (str(project_root / "lume-128.png"), "."),
    (str(project_root / "lume-256.png"), "."),
    (str(project_root / "lume-512.png"), "."),
]
if sys.platform != "win32":
    datas.append((str(project_root / "lume_shell_extension"), "lume_shell_extension"))

hiddenimports = [
    "PySide6.QtNetwork",
    "PySide6.QtGui",
    "lume.search",
    "lume.config",
    "lume.themes",
    "lume.tools.usage",
    "pypinyin",
]
if sys.platform == "win32":
    hiddenimports.extend(["lume.win32_hotkey", "winreg"])

icon_path = project_root / "lume.ico"
if not icon_path.exists():
    icon_path = project_root / "lume-256.png"

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LumeSmoke' if console_mode else 'Lume',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console_mode,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
)
