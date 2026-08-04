import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lume.search as search_module


class WindowsSearchIndexTests(unittest.TestCase):
    def test_start_menu_shortcuts_are_indexed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            programs = root / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            programs.mkdir(parents=True)
            (programs / "Example Editor.lnk").write_bytes(b"shortcut-placeholder")

            previous = search_module._app_cache
            search_module._app_cache = []
            try:
                with patch.dict(os.environ, {"APPDATA": temp, "PROGRAMDATA": ""}, clear=False):
                    with patch.object(
                        search_module,
                        "_resolve_windows_shortcuts",
                        return_value={
                            str(programs / "Example Editor.lnk"): {
                                "display_name": "示例编辑器",
                                "target": r"C:\Apps\ExampleEditor.exe",
                                "icon": r"C:\Apps\ExampleEditor.exe",
                            }
                        },
                    ):
                        search_module._load_windows_apps()
                self.assertEqual(len(search_module._app_cache), 1)
                app = search_module._app_cache[0]
                self.assertEqual(app["name"], "示例编辑器")
                self.assertTrue(app["id"].endswith("Example Editor.lnk"))
                self.assertTrue(app["icon"].endswith("Example Editor.lnk"))
                self.assertEqual(app["description"], r"C:\Apps\ExampleEditor.exe")
            finally:
                search_module._app_cache = previous

    def test_start_apps_localized_name_overrides_shortcut_stem(self):
        localized = search_module._best_windows_app_name(
            "Calculator",
            "Calculator",
            r"C:\Windows\System32\calc.exe",
            {"calculator": "计算器", "calc": "计算器"},
        )
        self.assertEqual(localized, "计算器")

    def test_load_apps_forces_windows_discovery_even_without_gio(self):
        previous_cache = search_module._app_cache
        previous_loaded = search_module._app_cache_loaded
        previous_locale = search_module._app_cache_locale
        try:
            search_module._app_cache = []
            search_module._app_cache_loaded = False
            search_module._app_cache_locale = ""
            with patch.object(search_module.sys, "platform", "win32"):
                with patch.object(search_module, "_load_windows_apps") as loader:
                    search_module._load_apps()
            loader.assert_called_once()
            self.assertTrue(search_module._app_cache_loaded)
        finally:
            search_module._app_cache = previous_cache
            search_module._app_cache_loaded = previous_loaded
            search_module._app_cache_locale = previous_locale


if __name__ == "__main__":
    unittest.main()
