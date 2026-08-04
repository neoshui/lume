import sys
import unittest

from PySide6.QtWidgets import QApplication

from lume.qt.settings import TabbedSettingsDialog
from lume.qt.utils import _gnome_binding
from lume.win32_hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_shortcut


class ShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_gnome_binding_conversion(self):
        self.assertEqual(_gnome_binding("ALT+Space"), "<Alt>space")
        self.assertEqual(_gnome_binding("CTRL+SHIFT+K"), "<Control><Shift>k")
        self.assertEqual(_gnome_binding("LOGO+P"), "<Super>p")

    def test_pending_shortcut_only_commits_through_values(self):
        config = {"shortcut": "ALT+Space", "appearance": {}}
        dialog = TabbedSettingsDialog(config)
        dialog._pending_shortcut = "CTRL+K"
        self.assertEqual(config["shortcut"], "ALT+Space")
        self.assertEqual(dialog.values()["shortcut"], "CTRL+K")
        dialog.close()

    def test_restore_alt_space_uses_pending_value(self):
        config = {"shortcut": "CTRL+K", "appearance": {}}
        dialog = TabbedSettingsDialog(config)
        dialog._finish_shortcut_capture("ALT+SPACE")
        self.assertEqual(dialog.values()["shortcut"], "ALT+SPACE")
        self.assertEqual(config["shortcut"], "CTRL+K")
        dialog.close()

    def test_windows_hotkey_parser_does_not_fall_back_to_space(self):
        self.assertEqual(parse_shortcut("ALT+Q"), (MOD_ALT, ord("Q")))
        self.assertEqual(parse_shortcut("CTRL+SHIFT+F12"), (MOD_CONTROL | MOD_SHIFT, 0x7B))
        self.assertEqual(parse_shortcut("ALT+LEFT"), (MOD_ALT, 0x25))
        self.assertIsNone(parse_shortcut("ALT+NOT_A_KEY"))


if __name__ == "__main__":
    unittest.main()
