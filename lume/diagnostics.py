"""Read-only runtime diagnostics for support and upgrade checks."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

from lume.config import CONFIG_FILE, DATA_DIR
from lume.qt.shell_extension import UUID, is_enabled, target_dir
from lume.version import runtime_identity


def _extension_state() -> dict[str, object]:
    metadata_path = target_dir() / "metadata.json"
    metadata: dict[str, object] = {}
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "uuid": UUID,
        "installed": metadata_path.is_file(),
        "version": metadata.get("version", "unknown"),
        "enabled": is_enabled(),
        "path": str(target_dir()),
    }


def _lume_processes() -> list[dict[str, str]]:
    processes = []
    proc_root = Path("/proc")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
            cwd = str((entry / "cwd").resolve())
        except (OSError, PermissionError):
            continue
        parts = command.split()
        executable = Path(parts[0]).name if parts else ""
        if executable in {"python", "python3", "Lume"} and "main.py" in command and "fuguang-gnome" in cwd:
            processes.append({"pid": entry.name, "command": command, "cwd": cwd})
    return processes


def collect() -> dict[str, object]:
    identity = runtime_identity()
    return {
        "identity": identity,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
            "session": os.environ.get("XDG_SESSION_TYPE", ""),
        },
        "paths": {"config": str(CONFIG_FILE), "data": str(DATA_DIR)},
        "extension": _extension_state(),
        "processes": _lume_processes(),
        "process_count": len(_lume_processes()),
    }


def format_diagnostics() -> str:
    return json.dumps(collect(), ensure_ascii=False, indent=2)
