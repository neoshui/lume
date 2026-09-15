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

    def test_fallback_skips_broken_launcher_entries(self):
        """Broken .desktop entries must not take the whole index down.

        Real-world case: ``/usr/local/share/applications/baidunetdisk.desktop``
        was a dangling symlink into an APM/amber-ce data dir.  configparser
        silently produced an empty parser for it, so ``parser["Desktop Entry"]``
        raised KeyError('Desktop Entry') during startup indexing and Lume died
        before showing its window.
        """
        with tempfile.TemporaryDirectory() as home_dir:
            applications = Path(home_dir) / ".local/share/applications"
            applications.mkdir(parents=True)

            # 1) dangling symlink to a removed payload
            (applications / "ghost.desktop").symlink_to(
                Path(home_dir) / "removed-payload/ghost.desktop"
            )
            # 2) file without a [Desktop Entry] section
            (applications / "nosection.desktop").write_text(
                "[Other Section]\nName=Not A Launcher\n", encoding="utf-8"
            )
            # 3) empty file
            (applications / "empty.desktop").write_text("", encoding="utf-8")
            # 4) healthy launcher that must survive
            (applications / "org.example.Healthy.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Healthy App\n",
                encoding="utf-8",
            )

            with patch.object(search_module.Path, "home", return_value=Path(home_dir)):
                with patch.dict(
                    os.environ,
                    {"XDG_DATA_DIRS": "", "XDG_DATA_HOME": ""},
                    clear=False,
                ):
                    search_module._load_apps_from_desktop_files()

        ids = {app["id"] for app in search_module._app_cache}
        names = {app["name"] for app in search_module._app_cache}
        # Healthy launcher still indexed; broken entries skipped, not fatal.
        self.assertIn("org.example.Healthy.desktop", ids)
        self.assertIn("Healthy App", names)
        self.assertNotIn("ghost.desktop", ids)
        self.assertNotIn("nosection.desktop", ids)
        self.assertNotIn("empty.desktop", ids)

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
