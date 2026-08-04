"""Clipboard history tracking for Lume - uses Gdk.Clipboard API (no subprocess polling).

Supports text and image content types.
"""

import json
import hashlib
import uuid
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gtk, Gdk, GLib

from lume.log_utils import get_logger

log = get_logger(__name__)
from collections import deque
from pathlib import Path

from lume.config import get_data_dir


CLIPBOARD_FILE = get_data_dir() / "clipboard_history.json"
IMAGES_DIR = get_data_dir() / "clipboard_images"


def _generate_id() -> str:
    """Generate a short unique ID for clipboard entries."""
    return uuid.uuid4().hex[:12]


class ClipboardEntry:
    """A clipboard history entry — text or image."""

    def __init__(self, text: str = "", content_type: str = "text",
                 pinned: bool = False, image_path: str = "",
                 entry_id: str | None = None, image_hash: str = ""):
        self.entry_id = entry_id or _generate_id()
        self.text = text
        self.content_type = content_type  # "text" | "image"
        self.pinned = pinned
        self.image_path = image_path  # path to saved PNG, only for image type
        self.image_hash = image_hash  # sha256 of image file for dedup

    def to_dict(self) -> dict:
        data = {
            "id": self.entry_id,
            "text": self.text,
            "content_type": self.content_type,
        }
        if self.pinned:
            data["pinned"] = True
        if self.image_path:
            data["image_path"] = self.image_path
        if self.image_hash:
            data["image_hash"] = self.image_hash
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ClipboardEntry":
        return cls(
            text=data.get("text", ""),
            content_type=data.get("content_type", "text"),
            pinned=data.get("pinned", False),
            image_path=data.get("image_path", ""),
            entry_id=data.get("id"),
            image_hash=data.get("image_hash", ""),
        )

    def preview(self, max_len: int = 60) -> str:
        if self.content_type == "image":
            return "📷 [图片]"
        text = self.text.strip().replace("\n", " ")
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text


class ClipboardWatcher:
    """Monitor clipboard changes via Gdk.Clipboard (no subprocess polling).

    Uses GDK's clipboard 'changed' signal, which the compositor emits
    when clipboard ownership changes. This is compositor-friendly and
    does not spawn subprocesses or poll.

    Supports both text and image clipboard content.
    """

    def __init__(self, max_entries: int = 50):
        self.max_entries = max_entries
        self.history: deque[ClipboardEntry] = deque(maxlen=max_entries)
        self._on_update = None
        self._running = False
        self._signal_id = None
        self._clipboard = None

        # Ensure images directory exists
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # Load saved history
        self._load()

    def _load(self):
        """Load clipboard history from disk."""
        changed = False
        if CLIPBOARD_FILE.exists():
            try:
                data = json.loads(CLIPBOARD_FILE.read_text())
                for item in data:
                    entry = ClipboardEntry.from_dict(item)
                    # Validate image files still exist for image entries
                    if entry.content_type == "image" and entry.image_path:
                        if not Path(entry.image_path).exists():
                            changed = True
                            continue  # skip orphaned entries
                    self.history.append(entry)
            except (json.JSONDecodeError, OSError):
                pass
        if changed:
            self._save()

    def _save(self):
        """Save clipboard history to disk."""
        try:
            data = [entry.to_dict() for entry in self.history]
            CLIPBOARD_FILE.write_text(json.dumps(data, ensure_ascii=False))
        except OSError as e:
            log.warning("Clipboard: failed to save history: %s", e)

    def _cleanup_orphan_images(self):
        """Remove image files not referenced by any entry."""
        if not IMAGES_DIR.exists():
            return
        valid_paths = {entry.image_path for entry in self.history if entry.image_path}
        for f in IMAGES_DIR.iterdir():
            if f.is_file() and str(f) not in valid_paths:
                try:
                    f.unlink()
                except OSError:
                    pass

    def prune_missing_images(self) -> bool:
        """Drop image entries whose cached PNG file is no longer available."""
        kept = []
        changed = False
        for entry in self.history:
            if entry.content_type == "image" and entry.image_path:
                if not Path(entry.image_path).exists():
                    changed = True
                    continue
            kept.append(entry)

        if changed:
            self.history = deque(kept, maxlen=self.max_entries)
            self._save()
            self._cleanup_orphan_images()
        return changed

    def set_on_update(self, callback):
        """Set callback for clipboard changes. Callback receives (entry, history_list)."""
        self._on_update = callback

    def add_entry(self, text: str) -> ClipboardEntry | None:
        """Add a new text clipboard entry.

        Returns the entry if added, None if it was a duplicate or empty.
        """
        if not text or not text.strip():
            return None
        text = text.strip()
        # Dedup: skip if last entry is the same text
        if self.history and self.history[-1].content_type == "text" and self.history[-1].text == text:
            return None
        entry = ClipboardEntry(text=text, content_type="text")
        self.history.append(entry)
        self._save()
        if self._on_update:
            history_list = list(self.history)
            self._on_update(entry, history_list)
        return entry

    def add_image_entry(self, texture: Gdk.Texture) -> ClipboardEntry | None:
        """Save a Gdk.Texture to disk and create an image clipboard entry.

        Returns the entry if added, None if duplicate (same content).
        """
        # Save texture as PNG to a temp path first
        img_filename = f"img_{_generate_id()}.png"
        img_path = str(IMAGES_DIR / img_filename)
        try:
            texture.save_to_png(img_path)
        except GLib.GError as e:
            log.warning("Failed to save clipboard image: %s", e)
            return None

        # Compute content hash from the saved file for dedup
        try:
            with open(img_path, 'rb') as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        except OSError:
            content_hash = ""

        # Dedup: skip if the last image entry has the same content hash
        if self.history and self.history[-1].content_type == "image":
            last = self.history[-1]
            if last.image_hash and last.image_hash == content_hash:
                # Same content — remove the duplicate file and skip
                try:
                    Path(img_path).unlink()
                except OSError:
                    pass
                return None

        entry = ClipboardEntry(
            text="",
            content_type="image",
            image_path=img_path,
            image_hash=content_hash,
        )
        self.history.append(entry)
        self._save()
        log.info("Clipboard: image saved %s", img_path)
        if self._on_update:
            history_list = list(self.history)
            self._on_update(entry, history_list)
        return entry

    def get_history(self) -> list[ClipboardEntry]:
        """Get clipboard history (newest first), pinned items first."""
        items = list(reversed(self.history))
        order = {id(e): i for i, e in enumerate(items)}
        items.sort(key=lambda e: (0 if e.pinned else 1, order.get(id(e), 0)))
        return items

    def start(self):
        """Start monitoring clipboard via Gdk.Clipboard 'changed' signal.

        Must be called from the GTK/GLib main loop thread.
        """
        if self._running:
            return
        self._running = True

        GLib.idle_add(self._setup_gdk_clipboard)
        log.info("Clipboard: monitoring via Gdk.Clipboard API (no subprocess polling)")

    def _setup_gdk_clipboard(self):
        """Connect to Gdk.Clipboard 'changed' signal (runs on main loop)."""
        display = Gdk.Display.get_default()
        if display is None:
            log.warning("Clipboard: Gdk.Display not available, monitoring disabled")
            self._running = False
            return False

        self._clipboard = display.get_clipboard()
        self._signal_id = self._clipboard.connect("changed", self._on_clipboard_changed)

        # Also read initial clipboard content (text + image)
        self._clipboard.read_text_async(None, self._on_read_initial, None)
        return False  # run once

    def _on_clipboard_changed(self, clipboard, *args):
        """Signal handler: clipboard content changed — try text first, then image."""
        clipboard.read_text_async(None, self._on_read_complete, None)

    def _try_read_image(self, clipboard):
        """Try to read clipboard as image (texture)."""
        clipboard.read_texture_async(None, self._on_image_read_complete, None)

    def _on_read_initial(self, clipboard, result, user_data):
        """Read initial clipboard content — try text, then image."""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self.add_entry(text)
                return
        except GLib.GError:
            pass
        # No text content — try image
        self._try_read_image(clipboard)

    def _on_read_complete(self, clipboard, result, user_data):
        """Read clipboard text after 'changed' signal."""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                self.add_entry(text)
                return
        except GLib.GError:
            pass
        # No text content — try image
        self._try_read_image(clipboard)

    def _on_image_read_complete(self, clipboard, result, user_data):
        """Read clipboard image (texture) after text read failed."""
        try:
            texture = clipboard.read_texture_finish(result)
            if texture:
                self.add_image_entry(texture)
        except GLib.GError:
            pass  # Neither text nor image — ignore

    def stop(self):
        """Stop monitoring clipboard."""
        self._running = False
        if self._clipboard and self._signal_id:
            try:
                self._clipboard.disconnect(self._signal_id)
            except Exception:
                pass
            self._signal_id = None
            self._clipboard = None

    def remove_entry(self, entry_id: str) -> bool:
        """Remove a specific entry by entry_id. Returns True if found and removed."""
        for i, entry in enumerate(self.history):
            if entry.entry_id == entry_id:
                # Delete image file if image entry
                if entry.image_path:
                    try:
                        Path(entry.image_path).unlink(missing_ok=True)
                    except OSError:
                        pass
                del self.history[i]
                self._save()
                if self._on_update:
                    self._on_update(None, list(self.history))
                return True
        return False

    def clear_all(self):
        """Clear all clipboard history, keeping pinned items and their image files."""
        # Collect image files to delete (non-pinned entries)
        to_delete = []
        for entry in self.history:
            if not entry.pinned and entry.image_path:
                to_delete.append(entry.image_path)

        self.history = deque(
            (entry for entry in self.history if entry.pinned),
            maxlen=self.max_entries,
        )

        # Delete orphaned image files
        for p in to_delete:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass

        self._save()
        self._cleanup_orphan_images()
        if self._on_update:
            self._on_update(None, list(self.history))

    def toggle_pin(self, entry_id: str) -> bool:
        """Toggle pin status of an entry by entry_id.
        Returns True if pinned, False if unpinned, None if not found.
        """
        for entry in reversed(self.history):
            if entry.entry_id == entry_id:
                entry.pinned = not entry.pinned
                self._save()
                if self._on_update:
                    self._on_update(entry, list(self.history))
                return entry.pinned
        return False
