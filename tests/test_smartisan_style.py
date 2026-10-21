"""Theme switching must preserve launcher preferences and privacy behavior."""
import copy
import unittest

from PySide6.QtWidgets import QApplication, QLabel
from lume.config import DEFAULT_CONFIG
from lume.qt.smartisan import is_smartisan, palette
from lume.qt.settings import TabbedSettingsDialog
from lume.qt.widgets import PrivacyButton


class SmartisanStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_older_config_uses_smartisan_without_mutation(self):
        config = {"shortcut": "ALT+SPACE", "appearance": {"accent_color": "#abc123"}}
        before = copy.deepcopy(config)
        self.assertTrue(is_smartisan(config))
        self.assertEqual(config, before)
        self.assertFalse(is_smartisan({"ui_style": "classic"}))

    def test_light_tokens_and_derived_dark_surface(self):
        self.assertEqual(palette(False)["page"], "#f5f5f5")
        self.assertEqual(palette(False)["accent"], "#5b87eb")
        self.assertNotEqual(palette(False)["page"], palette(True)["page"])

    def test_settings_roundtrip_and_classic_switch_preserve_preferences(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        config.update(ui_style="smartisan", shortcut="CTRL+F9", show_apps_on_open=False,
                      clipboard_private_mode=True, clipboard_max_entries=80)
        dialog = TabbedSettingsDialog(config)
        self.assertEqual(dialog.ui_style.currentData(), "smartisan")
        for style in ("classic", "smartisan"):
            dialog.ui_style.setCurrentIndex(dialog.ui_style.findData(style))
            result = dialog.values()
            self.assertEqual(result["ui_style"], style)
            for key in ("shortcut", "show_apps_on_open", "clipboard_private_mode", "clipboard_max_entries", "theme", "layout", "result_density"):
                self.assertEqual(result[key], config[key])
        self.assertEqual(config["ui_style"], "smartisan")
        dialog.deleteLater()

    def test_settings_uses_one_window_title(self):
        dialog = TabbedSettingsDialog(copy.deepcopy(DEFAULT_CONFIG))
        self.assertEqual(dialog.windowTitle(), "设置")
        self.assertIsNone(dialog.findChild(QLabel, "settingsTitle"))
        dialog.deleteLater()

    def test_privacy_button_has_stable_geometry_and_caption_in_both_styles(self):
        button = PrivacyButton()
        for smartisan in (True, False):
            button.set_visual_style(smartisan, False)
            size = button.size()
            for checked in (True, False):
                button.setChecked(checked)
                self.assertEqual(button.size(), size)
                self.assertEqual(button._text_label.text(), "私密模式")
                self.assertFalse(button._icon_label.pixmap().isNull())
        button.deleteLater()
