import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lume.search as search_module


class LinuxSearchIndexTests(unittest.TestCase):
    def setUp(self):
        self.previous_cache = search_module._app_cache
        search_module._app_cache = []

    def tearDown(self):
        search_module._app_cache = self.previous_cache

    def test_fallback_discovers_user_flatpak_export(self):
        with tempfile.TemporaryDirectory() as home_dir:
            applications = (
                Path(home_dir) / ".local/share/flatpak/exports/share/applications"
            )
            applications.mkdir(parents=True)
            (applications / "org.example.FlatpakApp.desktop").write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Flatpak Example\n"
                "Comment=Installed from Flatpak\n"
                "Icon=org.example.FlatpakApp\n",
                encoding="utf-8",
            )

            with patch.object(search_module.Path, "home", return_value=Path(home_dir)):
                with patch.dict(os.environ, {"XDG_DATA_DIRS": ""}, clear=False):
                    search_module._load_apps_from_desktop_files()

        matches = [
            app for app in search_module._app_cache
            if app["id"] == "org.example.FlatpakApp.desktop"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Flatpak Example")

    def test_launch_environment_contains_flatpak_exports(self):
        with patch.object(search_module.Path, "home", return_value=Path("/home/tester")):
            with patch.dict(
                os.environ,
                {"XDG_DATA_DIRS": "/opt/share:/usr/share"},
                clear=False,
            ):
                data_dirs = search_module._desktop_launch_env()["XDG_DATA_DIRS"].split(os.pathsep)

        self.assertIn("/home/tester/.local/share/flatpak/exports/share", data_dirs)
        self.assertIn("/var/lib/flatpak/exports/share", data_dirs)
        self.assertIn("/opt/share", data_dirs)


if __name__ == "__main__":
    unittest.main()
