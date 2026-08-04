import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

import lume.qt.clipboard as clip_module


class ClipboardStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)
        cls.shell_provider_patch = patch.object(clip_module, "is_enabled", return_value=True)
        cls.shell_provider_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.shell_provider_patch.stop()

    def test_capture_keeps_text_and_image_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            history_file = root / "clipboard_history.json"
            images_dir = root / "clipboard_images"
            with patch.object(clip_module, "CLIPBOARD_FILE", history_file):
                with patch.object(clip_module, "get_data_dir", return_value=root):
                    store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                    store._poll_timer.stop()

                    text_mime = QMimeData()
                    text_mime.setText("hello")
                    store._capture_mime_data(text_mime)

                    image_mime = QMimeData()
                    image = QImage(8, 8, QImage.Format.Format_ARGB32)
                    image.fill(0xFF00FF00)
                    image_mime.setImageData(image)
                    store._capture_mime_data(image_mime)

                    self.assertEqual(len(store.entries), 2)
                    self.assertEqual(store.entries[0]["content_type"], "text")
                    self.assertEqual(store.entries[1]["content_type"], "image")
                    self.assertTrue(Path(store.entries[1]["image_path"]).is_file())
                    self.assertTrue(images_dir.is_dir())

    def test_capture_dedups_identical_image_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            history_file = root / "clipboard_history.json"
            with patch.object(clip_module, "CLIPBOARD_FILE", history_file):
                with patch.object(clip_module, "get_data_dir", return_value=root):
                    store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                    store._poll_timer.stop()

                    image_mime = QMimeData()
                    image = QImage(8, 8, QImage.Format.Format_ARGB32)
                    image.fill(0xFFFF0000)
                    image_mime.setImageData(image)
                    store._capture_mime_data(image_mime)
                    store._capture_mime_data(image_mime)

                    self.assertEqual(len(store.entries), 1)

    def test_capture_from_qt_clipboard_materializes_payload(self):
        """The real clipboard path must retain successive text and image copies."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"):
                with patch.object(clip_module, "get_data_dir", return_value=root):
                    store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                    store._poll_timer.stop()
                    clipboard = self.app.clipboard()
                    image = QImage(8, 8, QImage.Format.Format_ARGB32)
                    image.fill(0xFF00FF00)
                    clipboard.setPixmap(QPixmap.fromImage(image))
                    store.capture()
                    clipboard.setText("after-image")
                    store.capture()
                    self.assertEqual([e["content_type"] for e in store.entries], ["image", "text"])
                    self.assertTrue(Path(store.entries[0]["image_path"]).is_file())

    def test_gdk_image_file_is_registered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"):
                with patch.object(clip_module, "get_data_dir", return_value=root):
                    store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                    store._poll_timer.stop()
                    image = QImage(8, 8, QImage.Format.Format_ARGB32)
                    image.fill(0xFF00FF00)
                    pixmap = QPixmap.fromImage(image)
                    from PySide6.QtCore import QBuffer
                    buffer = QBuffer(); buffer.open(QBuffer.OpenModeFlag.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    png = bytes(buffer.data())
                    image_path = root / "from-gdk.png"
                    image_path.write_bytes(png)
                    store._add_image_file(image_path)
                    self.assertEqual(store.entries[-1]["content_type"], "image")
                    self.assertEqual(store.entries[-1]["image_path"], str(image_path))

    def test_shell_history_imports_text_and_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_dir = root / "shell_clipboard"
            images = shell_dir / "images"
            images.mkdir(parents=True)
            image = QImage(8, 8, QImage.Format.Format_ARGB32); image.fill(0xFF00FF00)
            image_path = images / "imagehash.png"
            QPixmap.fromImage(image).save(str(image_path), "PNG")
            (shell_dir / "history.json").write_text(__import__("json").dumps([
                {"id": "shell_text", "content_type": "text", "text": "from-shell"},
                {"id": "shell_image", "content_type": "image", "image_path": str(image_path), "image_hash": "imagehash", "pinned": True},
            ]), encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"):
                with patch.object(clip_module, "SHELL_HISTORY_FILE", shell_dir / "history.json"):
                        store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                        store._poll_timer.stop()
                        self.assertTrue(store._sync_shell_history())
                        self.assertEqual([e["content_type"] for e in store.entries], ["text", "image"])
                        self.assertTrue(store.entries[1]["pinned"])

    def test_remove_updates_shell_history_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_history = root / "shell_clipboard" / "history.json"
            shell_history.parent.mkdir()
            shell_history.write_text(__import__("json").dumps([
                {"id": "keep", "content_type": "text", "text": "keep"},
                {"id": "remove", "content_type": "text", "text": "remove"},
            ]), encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", shell_history):
                store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                store._poll_timer.stop()
                self.assertTrue(store._sync_shell_history())
                store.remove({"id": "remove", "source": "lume-shell"})
                self.assertEqual([item["id"] for item in __import__("json").loads(shell_history.read_text())], ["keep"])
                self.assertEqual([item["id"] for item in store.entries], ["keep"])

    def test_clear_removes_pinned_and_unpinned_shell_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_history = root / "shell_clipboard" / "history.json"
            shell_history.parent.mkdir()
            shell_history.write_text(__import__("json").dumps([
                {"id": "pinned", "content_type": "text", "text": "pinned", "pinned": True},
                {"id": "normal", "content_type": "text", "text": "normal"},
            ]), encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", shell_history):
                store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                store._poll_timer.stop()
                self.assertTrue(store._sync_shell_history())
                store.clear()
                self.assertEqual(__import__("json").loads(shell_history.read_text()), [])
                self.assertEqual(store.entries, [])

    def test_empty_shell_history_remains_authoritative_after_clear(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_history = root / "shell_clipboard" / "history.json"
            shell_history.parent.mkdir()
            shell_history.write_text("[]", encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", shell_history):
                store = clip_module.ClipboardStore(self.app, 50, lambda: None)
                store._poll_timer.stop()
                store.entries = [{"id": "stale", "content_type": "text", "text": "stale"}]
                self.assertTrue(store._sync_shell_history())
                self.assertEqual(store.entries, [])

    def test_privacy_policy_skips_sensitive_and_oversized_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(
                    self.app, 50, lambda: None,
                    {"clipboard_filter_sensitive": True, "clipboard_max_text_length": 5},
                )
                store._poll_timer.stop()
                store._add_text("sk-abcdefghijklmnopqrstuvwxyz")
                store._add_text("123456")
                store._add_text("hello")
                self.assertEqual([item["text"] for item in store.entries], ["hello"])

    def test_private_mode_skips_text_and_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(
                    self.app, 50, lambda: None, {"clipboard_private_mode": True}
                )
                store._poll_timer.stop()
                store._add_text("not saved")
                self.assertEqual(store.entries, [])

    def test_private_mode_blocks_all_qt_capture_entry_points(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", root / "missing.json"), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(
                    self.app, 50, lambda: None,
                    {"clipboard_private_mode": True, "clipboard_cleanup_orphans": False},
                )
                store._poll_timer.stop()
                mime = QMimeData()
                mime.setText("should not be saved")
                self.app.clipboard().setText("signal should not be saved")
                store._capture_from_signal()
                store.capture()
                store._capture_mime_data(mime)
                store.add_entry({"id": "direct", "content_type": "text", "text": "direct"})
                self.assertEqual(store.entries, [])
                self.assertFalse((root / "clipboard_history.json").exists())

    def test_private_mode_preserves_existing_shell_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_dir = root / "shell_clipboard"
            shell_dir.mkdir()
            shell_history = shell_dir / "history.json"
            existing = [
                {"id": "old", "content_type": "text", "text": "copied before private mode"},
            ]
            shell_history.write_text(__import__("json").dumps(existing), encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", shell_history), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(
                    self.app, 50, lambda: None,
                    {"clipboard_private_mode": True, "clipboard_cleanup_orphans": False},
                )
                store._poll_timer.stop()
                self.assertTrue(store._sync_shell_history())
                self.assertEqual(store.entries[0]["text"], "copied before private mode")
                self.assertEqual(__import__("json").loads(shell_history.read_text()), existing)
                store._add_text("copied after private mode")
                self.assertEqual(len(store.entries), 1)

    def test_max_entries_updates_and_trims_shell_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_dir = root / "shell_clipboard"
            shell_dir.mkdir()
            shell_history = shell_dir / "history.json"
            source = [
                {"id": "one", "content_type": "text", "text": "one"},
                {"id": "two", "content_type": "text", "text": "two"},
                {"id": "three", "content_type": "text", "text": "three"},
            ]
            shell_history.write_text(__import__("json").dumps(source), encoding="utf-8")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", shell_history), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(self.app, 50, lambda: None, {"clipboard_cleanup_orphans": False})
                store._poll_timer.stop()
                store.set_max_entries(2)
                self.assertEqual(store.max_entries, 2)
                self.assertEqual([item["id"] for item in store.entries], ["two", "three"])
                self.assertEqual([item["id"] for item in __import__("json").loads(shell_history.read_text())], ["two", "three"])

    def test_cleanup_orphan_images_removes_only_unreferenced_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "clipboard_images"
            images.mkdir()
            kept = images / "kept.png"; kept.write_bytes(b"png")
            orphan = images / "orphan.png"; orphan.write_bytes(b"png")
            with patch.object(clip_module, "CLIPBOARD_FILE", root / "clipboard_history.json"), \
                    patch.object(clip_module, "SHELL_HISTORY_FILE", root / "missing.json"), \
                    patch.object(clip_module, "get_data_dir", return_value=root):
                store = clip_module.ClipboardStore(self.app, 50, lambda: None, {"clipboard_cleanup_orphans": False})
                store._poll_timer.stop()
                store.entries = [{"content_type": "image", "image_path": str(kept)}]
                self.assertEqual(store.cleanup_orphan_images(), 1)
                self.assertTrue(kept.exists())
                self.assertFalse(orphan.exists())


if __name__ == "__main__":
    unittest.main()
