import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lume.autostart as autostart


class AutostartTests(unittest.TestCase):
    def test_linux_autostart_writes_user_desktop_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            config_home = Path(temp) / "config"
            with patch.object(autostart, "_linux_autostart_file", return_value=config_home / "autostart" / "com.lume.launcher.desktop"):
                with patch.object(autostart.sys, "platform", "linux"):
                    ok, message = autostart.set_autostart(True, "/home/test/.local/lib/lume/Lume")
                    self.assertTrue(ok, message)
                    entry = (config_home / "autostart" / "com.lume.launcher.desktop").read_text()
                    self.assertIn("Exec=/home/test/.local/lib/lume/Lume --background", entry)
                    self.assertTrue(autostart.is_autostart_enabled())

                    ok, message = autostart.set_autostart(False, "/home/test/.local/lib/lume/Lume")
                    self.assertTrue(ok, message)
                    self.assertFalse((config_home / "autostart" / "com.lume.launcher.desktop").exists())

    def test_windows_autostart_uses_current_user_run_key(self):
        calls = []

        class FakeKey:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        class FakeWinreg:
            HKEY_CURRENT_USER = object()
            KEY_READ = 1
            KEY_SET_VALUE = 2
            REG_SZ = 3

            @staticmethod
            def CreateKeyEx(*args):
                calls.append(("create", args))
                return FakeKey()

            @staticmethod
            def SetValueEx(*args):
                calls.append(("set", args))

            @staticmethod
            def DeleteValue(*args):
                calls.append(("delete", args))

            @staticmethod
            def OpenKey(*args):
                return FakeKey()

            @staticmethod
            def QueryValueEx(*args):
                return ('"C:\\Lume\\Lume.exe" --background', FakeWinreg.REG_SZ)

        with patch.object(autostart.sys, "platform", "win32"), patch.dict("sys.modules", {"winreg": FakeWinreg}):
            ok, message = autostart.set_autostart(True, r"C:\Lume\Lume.exe")
            self.assertTrue(ok, message)
            self.assertTrue(autostart.is_autostart_enabled())
            self.assertTrue(any(call[0] == "set" for call in calls))


if __name__ == "__main__":
    unittest.main()
