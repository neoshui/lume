import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lume.qt.shell_extension as shell_extension


class ShellExtensionStatusTests(unittest.TestCase):
    def test_is_enabled_uses_registered_list_and_gsettings_when_info_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "", "")
                listed = shell_extension.subprocess.CompletedProcess([], 0, f"{shell_extension.UUID}\n", "")
                settings = shell_extension.subprocess.CompletedProcess(
                    [], 0, json.dumps([shell_extension.UUID]), ""
                )
                with patch.object(shell_extension.subprocess, "run", side_effect=[info, listed, settings]):
                    self.assertTrue(shell_extension.is_enabled())

    def test_is_enabled_accepts_nonzero_cli_status_when_output_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "", "dconf warning")
                listed = shell_extension.subprocess.CompletedProcess([], 2, f"{shell_extension.UUID}\n", "dconf warning")
                settings = shell_extension.subprocess.CompletedProcess([], 0, json.dumps([shell_extension.UUID]), "")
                with patch.object(shell_extension.subprocess, "run", side_effect=[info, listed, settings]):
                    self.assertTrue(shell_extension.is_enabled())

    def test_is_enabled_uses_settings_when_cli_has_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "", "")
                listed = shell_extension.subprocess.CompletedProcess([], 2, "", "")
                settings = shell_extension.subprocess.CompletedProcess([], 0, json.dumps([shell_extension.UUID]), "")
                with patch.object(shell_extension.subprocess, "run", side_effect=[info, listed, settings]):
                    self.assertTrue(shell_extension.is_enabled())

    def test_is_enabled_rejects_disabled_gsettings_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "", "")
                listed = shell_extension.subprocess.CompletedProcess([], 0, f"{shell_extension.UUID}\n", "")
                settings = shell_extension.subprocess.CompletedProcess([], 0, "[]", "")
                with patch.object(shell_extension.subprocess, "run", side_effect=[info, listed, settings]):
                    self.assertFalse(shell_extension.is_enabled())

    def test_is_enabled_rejects_unregistered_extension_even_if_gsettings_lists_it(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "", "")
                listed = shell_extension.subprocess.CompletedProcess([], 0, "other-extension@example.com\n", "")
                with patch.object(shell_extension.subprocess, "run", side_effect=[info, listed]):
                    self.assertFalse(shell_extension.is_enabled())

    def test_is_enabled_trusts_active_info_state(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 0, "State: ACTIVE\n", "")
                with patch.object(shell_extension.subprocess, "run", return_value=info):
                    self.assertTrue(shell_extension.is_enabled())

    def test_is_enabled_trusts_active_state_even_with_nonzero_info_status(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(shell_extension, "target_dir", return_value=Path(temp)):
                (Path(temp) / "metadata.json").write_text("{}", encoding="utf-8")
                info = shell_extension.subprocess.CompletedProcess([], 2, "State: ACTIVE\n", "dconf warning")
                with patch.object(shell_extension.subprocess, "run", return_value=info):
                    self.assertTrue(shell_extension.is_enabled())


if __name__ == "__main__":
    unittest.main()
