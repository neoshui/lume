import unittest

from scripts.validate_version import project_version, tag_base_version


class BuildMetadataTests(unittest.TestCase):
    def test_project_versions_are_in_sync(self):
        pyproject_version, source_version = project_version()
        self.assertEqual(pyproject_version, source_version)

    def test_release_tag_accepts_prerelease_suffix(self):
        self.assertEqual(tag_base_version("v1.1.0-test.1"), "1.1.0")

    def test_release_tag_rejects_missing_v_prefix(self):
        with self.assertRaises(ValueError):
            tag_base_version("1.1.0")


if __name__ == "__main__":
    unittest.main()
