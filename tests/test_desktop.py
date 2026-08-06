import unittest

from lume.desktop import detect_desktop


class DesktopDetectionTests(unittest.TestCase):
    def test_gnome_wayland_needs_gnome_extension(self):
        info = detect_desktop({"XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "wayland"})
        self.assertTrue(info.is_gnome)
        self.assertTrue(info.is_wayland)
        self.assertTrue(info.needs_gnome_extension)
        self.assertEqual(info.clipboard_backend, "gnome-shell")

    def test_ubuntu_gnome_wayland_is_detected_from_desktop_tokens(self):
        info = detect_desktop({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME", "XDG_SESSION_TYPE": "wayland"})
        self.assertTrue(info.needs_gnome_extension)

    def test_kde_wayland_does_not_need_gnome_extension(self):
        info = detect_desktop({"XDG_CURRENT_DESKTOP": "KDE", "XDG_SESSION_TYPE": "wayland"})
        self.assertFalse(info.is_gnome)
        self.assertTrue(info.is_wayland)
        self.assertFalse(info.needs_gnome_extension)
        self.assertEqual(info.clipboard_backend, "qt")

    def test_gnome_x11_does_not_need_gnome_extension(self):
        info = detect_desktop({"XDG_CURRENT_DESKTOP": "GNOME", "XDG_SESSION_TYPE": "x11"})
        self.assertTrue(info.is_gnome)
        self.assertFalse(info.is_wayland)
        self.assertFalse(info.needs_gnome_extension)

    def test_wayland_display_is_fallback_when_session_type_missing(self):
        info = detect_desktop({"XDG_CURRENT_DESKTOP": "GNOME", "WAYLAND_DISPLAY": "wayland-0"})
        self.assertTrue(info.needs_gnome_extension)


if __name__ == "__main__":
    unittest.main()
