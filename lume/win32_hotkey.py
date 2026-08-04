"""Windows global hotkey using RegisterHotKey + QAbstractNativeEventFilter.
Reliably registers system-level hotkeys by integrating with Qt's event loop.
"""

from lume.log_utils import get_logger

log = get_logger(__name__)

import sys
import ctypes

# wintypes needed for MSG structure on Windows; import now so it's available
# in the frozen exe's module cache before the native event filter runs.
try:
    import ctypes.wintypes
except ImportError:
    pass

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_SPACE = 0x20


def parse_shortcut(shortcut: str):
    """Return (modifiers, virtual-key) or None for an unsupported shortcut."""
    parts = [part for part in shortcut.upper().replace(" ", "").split("+") if part]
    if len(parts) < 2:
        return None
    mod = 0
    for part in parts[:-1]:
        if part == "ALT":
            mod |= MOD_ALT
        elif part in ("CTRL", "CONTROL"):
            mod |= MOD_CONTROL
        elif part == "SHIFT":
            mod |= MOD_SHIFT
        elif part in ("LOGO", "SUPER", "WIN", "META"):
            mod |= MOD_WIN
        else:
            return None

    key_name = parts[-1]
    key_map = {
        "BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "RETURN": 0x0D,
        "ESC": 0x1B, "ESCAPE": 0x1B, "SPACE": VK_SPACE,
        "PGUP": 0x21, "PAGEUP": 0x21, "PGDOWN": 0x22, "PAGEDOWN": 0x22,
        "END": 0x23, "HOME": 0x24, "LEFT": 0x25, "UP": 0x26,
        "RIGHT": 0x27, "DOWN": 0x28, "INS": 0x2D, "INSERT": 0x2D,
        "DEL": 0x2E, "DELETE": 0x2E,
    }
    vk = key_map.get(key_name)
    if vk is None and len(key_name) == 1 and key_name.isalnum():
        vk = ord(key_name)
    if vk is None and key_name.startswith("F") and key_name[1:].isdigit():
        number = int(key_name[1:])
        if 1 <= number <= 24:
            vk = 0x70 + number - 1
    return (mod, vk) if vk is not None else None

if sys.platform == "win32":
    from PySide6.QtCore import QAbstractNativeEventFilter

    user32 = ctypes.windll.user32

    class WinHotkeyFilter(QAbstractNativeEventFilter):
        """Qt native event filter that catches WM_HOTKEY messages."""

        def __init__(self, callback):
            super().__init__()
            self.callback = callback
            self.hotkey_id = 100
            self._shortcut_info = None

        def register(self, shortcut: str) -> bool:
            """Register a global hotkey using Win32 RegisterHotKey."""
            parsed = parse_shortcut(shortcut)
            if parsed is None:
                log.warning("WinHotkeyFilter: unsupported shortcut=%s", shortcut)
                return False
            mod, vk = parsed

            result = user32.RegisterHotKey(None, self.hotkey_id, mod | MOD_NOREPEAT, vk)
            if result:
                self._shortcut_info = (shortcut, vk, mod)
                log.info("WinHotkeyFilter: registered shortcut=%s, vk=0x%x, mod=0x%x", shortcut, vk, mod)
            else:
                log.warning("WinHotkeyFilter: RegisterHotKey FAILED for %s", shortcut)
            return result != 0

        def nativeEventFilter(self, eventType, message):
            """Called by Qt for every native Windows message."""
            if eventType != b"windows_generic_MSG":
                return False, 0
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    self.callback()
                    return True, 0
            except Exception:
                pass
            return False, 0

        def unregister(self):
            if self.hotkey_id:
                try:
                    user32.UnregisterHotKey(None, self.hotkey_id)
                    log.info("WinHotkeyFilter: unregistered hotkey ID %s", self.hotkey_id)
                except Exception:
                    pass
            self._shortcut_info = None

    _filter_instance = None

    def register(shortcut: str, callback) -> bool:
        """Register a global hotkey. Creates a new WinHotkeyFilter and installs it."""
        global _filter_instance
        from PySide6.QtCore import QCoreApplication

        unregister_all()
        hotkey_filter = WinHotkeyFilter(callback)
        ok = hotkey_filter.register(shortcut)
        if ok:
            QCoreApplication.instance().installNativeEventFilter(hotkey_filter)
            _filter_instance = hotkey_filter
            return True
        return False

    def unregister(hotkey_id=None):
        global _filter_instance
        if _filter_instance is not None:
            try:
                from PySide6.QtCore import QCoreApplication
                app = QCoreApplication.instance()
                if app:
                    app.removeNativeEventFilter(_filter_instance)
            except Exception:
                pass
            try:
                _filter_instance.unregister()
            except Exception:
                pass
            _filter_instance = None

    def unregister_all():
        unregister()

    def get_active_hotkey_info():
        """Return (shortcut, vk, mods) of the currently registered hotkey, or None."""
        global _filter_instance
        if _filter_instance is not None:
            return getattr(_filter_instance, '_shortcut_info', None)
        return None

else:
    # Linux/macOS stub
    def register(shortcut, callback):
        return False

    def unregister(hotkey_id=None):
        pass

    def unregister_all():
        pass
