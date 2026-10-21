"""Missing theme cache entries must still resolve installed application icons."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap, QColor
from lume.qt import utils


class IconResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hicolor_png_is_used_when_qt_theme_lookup_misses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'hicolor/128x128/apps/example-app.png'
            target.parent.mkdir(parents=True)
            image = QPixmap(32, 32); image.fill(QColor('#b84b92')); image.save(str(target))
            with patch.object(utils, '_linux_icon_roots', return_value=(root,)), patch.object(QIcon, 'fromTheme', return_value=QIcon()):
                icon = utils._icon('example-app')
                self.assertFalse(icon.pixmap(32, 32).isNull())
                self.assertEqual(icon.pixmap(32, 32).toImage().pixelColor(16, 16).name(), '#b84b92')

    def test_flatpak_export_root_is_searched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'flatpak/exports/share/icons'
            target = root / 'hicolor/256x256/apps/org.example.App.png'
            target.parent.mkdir(parents=True)
            image = QPixmap(32, 32); image.fill(QColor('#4184c6')); image.save(str(target))
            with patch.object(utils, '_linux_icon_roots', return_value=(root,)), patch.object(QIcon, 'fromTheme', return_value=QIcon()):
                self.assertFalse(utils._icon('org.example.App').pixmap(32, 32).isNull())
