"""Clipboard history storage for Lume Qt UI."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QObject, QTimer, QMimeData
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from lume.config import get_data_dir
from lume.desktop import detect_desktop
from lume.log_utils import get_logger
from lume.qt.shell_extension import is_enabled

CLIPBOARD_FILE = get_data_dir() / 'clipboard_history.json'
SHELL_HISTORY_FILE = get_data_dir() / "shell_clipboard" / "history.json"
_POLL_INTERVAL_MS = 250
_SENSITIVE_TEXT = re.compile(
    r"(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9_]{16,}|AKIA[0-9A-Z]{16}|"
    r"Bearer\s+[A-Za-z0-9._-]{20,}|password\s*[:=]\s*\S+)", re.IGNORECASE
)
log = get_logger(__name__)


class ClipboardStore(QObject):
    """Qt clipboard history using a background polling timer.

    On Wayland the ``dataChanged`` signal does not fire when the window
    is hidden or unfocused, so we rely on a periodic poll instead.  The
    signal handler is kept as a secondary trigger for the visible case.
    """

    def __init__(self, app: QApplication, max_entries: int, changed, config: dict | None = None):
        super().__init__()
        self.app = app
        self.max_entries = max_entries
        self.config = config or {}
        self.changed = changed
        self.entries: list[dict] = []
        self._ignore_depth = 0
        self._last_clipboard_signature = ""
        self._last_capture_time = 0.0
        self._shell_provider_active = False
        self.load()
        if self.config.get("clipboard_cleanup_orphans", True):
            self.cleanup_orphan_images()

        # Background poll — catches copies on Wayland while hidden.
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(_POLL_INTERVAL_MS)

        # dataChanged signal — capture an eager snapshot immediately so
        # "image -> text" or "text -> image" sequences do not collapse
        # into only the final clipboard state before the next poll runs.
        app.clipboard().dataChanged.connect(self._capture_from_signal)
    def _poll(self):
        """Read current clipboard content and capture if changed."""
        try:
            self.capture()
        except Exception:
            pass  # clipboard not accessible yet (e.g. during startup)

    def _capture_from_signal(self):
        """Capture a clipboard snapshot immediately on dataChanged."""
        if self.config.get("clipboard_private_mode", False):
            return
        try:
            mime = self._snapshot_mime_data(self.app.clipboard().mimeData())
            self._capture_mime_data(mime)
        except Exception:
            pass

    def load(self):
        try:
            data = json.loads(CLIPBOARD_FILE.read_text(encoding="utf-8"))
            self.entries = [item for item in data if isinstance(item, dict) and not self._expired(item)]
        except (OSError, json.JSONDecodeError):
            self.entries = []

    def save(self):
        CLIPBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(CLIPBOARD_FILE, self.entries)

    def set_max_entries(self, max_entries: int):
        """Apply the history limit immediately after settings are saved."""
        self.max_entries = max(1, int(max_entries))
        if SHELL_HISTORY_FILE.is_file():
            # The Shell history is authoritative when available; syncing
            # also trims its JSON source so the limit survives restarts.
            self._sync_shell_history()
            return
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
            self.save()
            self.changed()

    def _expired(self, item: dict) -> bool:
        hours = float(self.config.get("clipboard_auto_expire_hours", 0) or 0)
        if hours <= 0:
            return False
        captured = str(item.get("captured_at", ""))
        if not captured:
            return False
        try:
            stamp = datetime.fromisoformat(captured.replace("Z", "+00:00"))
            return (datetime.now(stamp.tzinfo) - stamp).total_seconds() > hours * 3600
        except ValueError:
            return False

    def capture(self):
        if self._ignore_depth > 0 or self.config.get("clipboard_private_mode", False):
            return
        # The optional Lume GNOME Shell component receives every Wayland
        # selection change and persists it before the next copy can replace it.
        if self._sync_shell_history():
            return
        mime = self._snapshot_mime_data(self.app.clipboard().mimeData())
        self._capture_mime_data(mime)

    def _sync_shell_history(self) -> bool:
        """Load history captured by Lume's own GNOME Shell component."""
        if not detect_desktop().needs_gnome_extension:
            return False
        if not SHELL_HISTORY_FILE.is_file():
            return False
        if not is_enabled():
            self._shell_provider_active = False
            return False
        try:
            source_entries = json.loads(SHELL_HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.debug("Lume Shell clipboard history is temporarily unavailable: %s", exc)
            return False
        if not isinstance(source_entries, list):
            return False
        pinned_by_id = {str(e.get("id", "")): bool(e.get("pinned")) for e in self.entries if e.get("id")}
        imported: list[dict] = []
        accepted_source: list[dict] = []
        private_mode = bool(self.config.get("clipboard_private_mode", False))
        for item in source_entries[-self.max_entries:]:
            if not isinstance(item, dict):
                continue
            content_type = item.get("content_type")
            if self._expired(item):
                continue
            if content_type == "text":
                text = str(item.get("text", "")).strip()
                # Private mode blocks future captures; it must not delete or
                # hide history that already existed before the switch.
                if not private_mode and not self._allowed_text(text):
                    continue
                accepted_source.append(item)
                imported.append({
                    "id": str(item.get("id", "")), "text": text, "content_type": "text",
                    "pinned": pinned_by_id.get(str(item.get("id", "")), bool(item.get("pinned"))), "source": "lume-shell",
                    "captured_at": item.get("captured_at", ""),
                })
            elif content_type == "image":
                image_path = Path(str(item.get("image_path", "")))
                if not image_path.is_file():
                    continue
                if not private_mode and not self._allowed_image(image_path):
                    continue
                accepted_source.append(item)
                imported.append({
                    "id": str(item.get("id", "")), "text": "", "content_type": "image",
                    "image_path": str(image_path), "image_hash": str(item.get("image_hash", "")),
                    "pinned": pinned_by_id.get(str(item.get("id", "")), bool(item.get("pinned"))), "source": "lume-shell",
                    "captured_at": item.get("captured_at", ""),
                })
        if accepted_source != source_entries:
            try:
                self._atomic_write(SHELL_HISTORY_FILE, accepted_source)
            except OSError:
                log.warning("Could not persist filtered Shell clipboard history")
        # The Shell component is the authoritative source while available. Replacing rather
        # than merging prevents every copy from appearing twice (Qt + Pano).
        if self.entries != imported:
            self.entries = imported
            self.save()
            self.changed()
        if not self._shell_provider_active:
            log.info("Using Lume GNOME Shell clipboard provider (%d entries)", len(imported))
        self._shell_provider_active = True
        return True

    def _allowed_text(self, text: str) -> bool:
        if not text or self.config.get("clipboard_private_mode", False):
            return False
        limit = max(1, int(self.config.get("clipboard_max_text_length", 10000)))
        if len(text) > limit:
            return False
        if self.config.get("clipboard_filter_sensitive", True) and _SENSITIVE_TEXT.search(text):
            log.info("Skipped sensitive clipboard text")
            return False
        return True

    def _allowed_image(self, path: Path) -> bool:
        if self.config.get("clipboard_private_mode", False):
            return False
        try:
            return path.stat().st_size <= max(1, int(self.config.get("clipboard_max_image_bytes", 10 * 1024 * 1024)))
        except OSError:
            return False

    @staticmethod
    def _snapshot_mime_data(source: QMimeData) -> QMimeData:
        """Materialize clipboard data before the provider can release it.

        ``QMimeData(source)`` is *not* a copy constructor in PySide6; it
        creates an empty object.  This was especially visible on Windows,
        where delayed-rendered screenshots disappeared as soon as the next
        text copy arrived.  Explicitly materialize the payload while the
        clipboard owner is still available.
        """
        snapshot = QMimeData()
        if source is None:
            return snapshot
        try:
            if source.hasImage():
                image = source.imageData()
                if image is not None:
                    snapshot.setImageData(image)
                    return snapshot
        except Exception:
            pass
        try:
            if source.hasText():
                snapshot.setText(str(source.text()))
        except Exception:
            pass
        return snapshot

    def _capture_mime_data(self, mime: QMimeData):
        if self._ignore_depth > 0 or self.config.get("clipboard_private_mode", False):
            return
        if mime.hasImage():
            image = mime.imageData()
            pixmap = image if isinstance(image, QPixmap) else None
            if pixmap is None:
                try:
                    pixmap = QPixmap.fromImage(image)
                except Exception:
                    pixmap = QPixmap()
            if not pixmap.isNull():
                buffer = QBuffer()
                buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                pixmap.save(buffer, "PNG")
                self._add_image_bytes(bytes(buffer.data()))
                return
        elif mime.hasText() and str(mime.text()).strip():
            self._add_text(str(mime.text()))
            return
        return

    def _add_text(self, text: str):
        text = text.strip()
        if not self._allowed_text(text):
            return
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        now = time.monotonic()
        if text_hash == self._last_clipboard_signature and now - self._last_capture_time < 0.6:
            return
        if self.entries and self.entries[-1].get("content_type") == "text" and self.entries[-1].get("text") == text:
            return
        self.entries.append({"id": f"qt_{time.time_ns()}", "text": text, "content_type": "text",
                             "captured_at": datetime.now().astimezone().isoformat()})
        self.entries = self.entries[-self.max_entries:]
        self._last_clipboard_signature = text_hash
        self._last_capture_time = now
        self.save()
        self.changed()

    def _add_image_bytes(self, image_bytes: bytes):
        """Store an already-materialized PNG from the Qt clipboard path."""
        image_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
        now = time.monotonic()
        if image_hash == self._last_clipboard_signature and now - self._last_capture_time < 1.2:
            return
        if self.entries and self.entries[-1].get("content_type") == "image" and self.entries[-1].get("image_hash") == image_hash:
            return
        images = get_data_dir() / "clipboard_images"
        images.mkdir(parents=True, exist_ok=True)
        path = images / f"qt_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
        try:
            path.write_bytes(image_bytes)
        except OSError:
            return
        if not self._allowed_image(path):
            path.unlink(missing_ok=True)
            log.info("Skipped oversized clipboard image (%d bytes)", len(image_bytes))
            return
        self.entries.append({
            "id": path.stem,
            "text": "",
            "content_type": "image",
            "image_path": str(path),
            "image_hash": image_hash,
            "captured_at": datetime.now().astimezone().isoformat(),
        })
        self.entries = self.entries[-self.max_entries:]
        self._last_clipboard_signature = image_hash
        self._last_capture_time = now
        self.save()
        self.changed()
        log.info("Saved clipboard image via Qt (%d bytes)", len(image_bytes))

    def _add_image_file(self, path: Path, image_hash: str = ""):
        """Register the PNG written by the GDK helper without re-encoding it."""
        if (self._ignore_depth > 0 or self.config.get("clipboard_private_mode", False)
                or not path.is_file() or not self._allowed_image(path)):
            return
        if not image_hash:
            try:
                image_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            except OSError:
                return
        now = time.monotonic()
        if image_hash == self._last_clipboard_signature and now - self._last_capture_time < 1.2:
            return
        if self.entries and self.entries[-1].get("content_type") == "image" and self.entries[-1].get("image_hash") == image_hash:
            return
        self.entries.append({
            "id": path.stem,
            "text": "",
            "content_type": "image",
            "image_path": str(path),
            "image_hash": image_hash,
            "captured_at": datetime.now().astimezone().isoformat(),
        })
        self.entries = self.entries[-self.max_entries:]
        self._last_clipboard_signature = image_hash
        self._last_capture_time = now
        self.save()
        self.changed()
        log.info("Saved clipboard image via GNOME GDK (%s)", path.name)

    def copy(self, entry: dict):
        self._ignore_depth += 1
        try:
            if entry.get("content_type") == "image":
                pixmap = QPixmap(entry.get("image_path", ""))
                if not pixmap.isNull():
                    self.app.clipboard().setPixmap(pixmap)
            else:
                self.app.clipboard().setText(entry.get("text", ""))
        finally:
            # Defer release so the dataChanged signal (which fires
            # synchronously on setText/setPixmap) sees _ignore_depth > 0
            # and skips the re-capture of our own clipboard write.
            QTimer.singleShot(50, self._release_ignore)

    def _release_ignore(self):
        if self._ignore_depth > 0:
            self._ignore_depth -= 1

    def add_entry(self, entry: dict):
        # Directly add a pre-built entry dict (bypasses clipboard read).
        # Used for forced sync on Wayland where dataChanged is unreliable.
        if not entry or self.config.get("clipboard_private_mode", False):
            return
        # Dedup against last entry
        if self.entries and self.entries[-1].get("content_type") == entry["content_type"]:
            last = self.entries[-1]
            if entry["content_type"] == "text" and last.get("text") == entry["text"]:
                return
            if entry["content_type"] == "image" and last.get("image_hash") == entry.get("image_hash"):
                return
        self.entries.append(entry)
        self.entries = self.entries[-self.max_entries:]
        self.save()
        self.changed()

    def get_history(self) -> list[dict]:
        # Return entries newest-first, pinned items at the top.
        result = list(reversed(self.entries))
        result.sort(key=lambda e: (0 if e.get("pinned") else 1))
        return result

    def remove(self, entry: dict):
        self._rewrite_shell_history(
            lambda item: item.get("id") != entry.get("id")
        )
        self.entries = [item for item in self.entries if item.get("id") != entry.get("id")]
        if entry.get("image_path") and entry.get("source") != "lume-shell":
            try:
                Path(entry["image_path"]).unlink(missing_ok=True)
            except OSError:
                pass
        self.save()
        self.changed()

    def clear(self):
        # "清空" means clear the complete history, including pinned entries.
        # Keeping pinned items here made the button appear ineffective and
        # allowed them to return after the next Shell-history sync.
        self._rewrite_shell_history(lambda _item: False)
        self.entries = []
        self.save()
        self.changed()

    def _rewrite_shell_history(self, keep) -> bool:
        """Apply a history mutation to the Shell provider's source file.

        When the GNOME Shell bridge is active, its JSON file is authoritative.
        Mutating only ``CLIPBOARD_FILE`` would make deleted entries reappear
        on the next polling sync.
        """
        if not SHELL_HISTORY_FILE.is_file():
            return False
        try:
            source_entries = json.loads(SHELL_HISTORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(source_entries, list):
                return False
            kept = [item for item in source_entries if isinstance(item, dict) and keep(item)]
            if kept == source_entries:
                return False
            self._atomic_write(SHELL_HISTORY_FILE, kept)
            return True
        except (OSError, json.JSONDecodeError):
            return False

    @staticmethod
    def _atomic_write(path: Path, value) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp-{time.time_ns()}")
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    def cleanup_orphan_images(self) -> int:
        """Remove PNG files no longer referenced by clipboard history."""
        roots = [get_data_dir() / "clipboard_images", get_data_dir() / "shell_clipboard" / "images"]
        referenced = {str(Path(item.get("image_path", "")).resolve()) for item in self.entries if item.get("image_path")}
        try:
            source = json.loads(SHELL_HISTORY_FILE.read_text(encoding="utf-8")) if SHELL_HISTORY_FILE.is_file() else []
            referenced.update(str(Path(item.get("image_path", "")).resolve()) for item in source if isinstance(item, dict) and item.get("image_path"))
        except (OSError, json.JSONDecodeError):
            pass
        removed = 0
        for root in roots:
            if not root.is_dir():
                continue
            for image in root.glob("*.png"):
                if str(image.resolve()) not in referenced:
                    try:
                        image.unlink()
                        removed += 1
                    except OSError:
                        pass
        return removed
