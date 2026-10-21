"""Desktop identity and dock restoration must agree with the launcher entry."""
import unittest
import sys
from unittest.mock import patch
from PySide6.QtCore import Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from lume.qt.main_window import LumeWindow, configure_application


class DockIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_application(cls.app)

    def test_desktop_identity_matches_installed_launcher(self):
        self.assertEqual(self.app.desktopFileName(), 'com.lume.launcher')
        self.assertFalse(self.app.windowIcon().isNull())

    @unittest.skipUnless(sys.platform == "linux", "Linux dock integration")
    def test_linux_launcher_window_is_transient_and_can_be_restored(self):
        with patch.object(LumeWindow, '_setup_tray_and_hotkey'), patch.object(LumeWindow, '_offer_shell_clipboard_component'):
            w = LumeWindow(self.app)
            w.store._poll_timer.stop()
            capture = patch.object(w.store, "capture")
            capture.start()
            self.assertEqual(w.windowFlags() & Qt.WindowType.WindowType_Mask, Qt.WindowType.Tool)
            w.show_launcher(); self.app.processEvents()
            w._dismiss(); self.app.processEvents()
            self.assertTrue(w._dismissed)
            self.assertFalse(w.isVisible())
            self.assertEqual(w.windowOpacity(), 1.0)
            w.toggle(); self.app.processEvents()
            self.assertTrue(w.isVisible())
            w.close(); w.store.deleteLater(); w.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            capture.stop()
