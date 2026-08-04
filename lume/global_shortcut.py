"""Global shortcut integration via xdg-desktop-portal GlobalShortcuts.

Spec: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
"""

import dbus
import dbus.mainloop.glib
import uuid
from gi.repository import GLib

from lume.log_utils import get_logger

log = get_logger(__name__)


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
LOGIND_BUS_NAME = "org.freedesktop.login1"
LOGIND_OBJECT_PATH = "/org/freedesktop/login1"
LOGIND_INTERFACE = "org.freedesktop.login1.Manager"


class GlobalShortcutManager:
    """Register and handle global shortcuts via the portals API."""

    def __init__(self, shortcut: str = "<Control>space"):
        self._shortcut = shortcut
        self._session_handle = None
        self._create_session_req_path = None
        self._bind_req_path = None
        self._on_activated = None
        self._dbus_connection = None
        self._setup_done = False
        self._short_id = "lume-open-v5"
        self._suspended = False

    def set_on_activated(self, callback):
        """Set callback when shortcut is pressed. Callback receives no args."""
        self._on_activated = callback

    def setup(self):
        """Initialize D-Bus connection and register the shortcut."""
        if self._setup_done:
            return

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        try:
            self._dbus_connection = dbus.SessionBus()
        except dbus.DBusException as e:
            log.warning("Could not connect to session bus: %s", e)
            return

        log.info("Setting up global shortcut: %s", self._shortcut)
        self._register()

        # Monitor system resume to re-register shortcut after hibernation
        self._watch_system_resume()

    def _register(self):
        """Start the session creation process."""
        self._setup_done = False
        self._create_session()

    def _watch_system_resume(self):
        """Listen for logind PrepareForSleep to re-register after hibernation."""
        try:
            system_bus = dbus.SystemBus()
            system_bus.add_signal_receiver(
                self._on_prepare_for_sleep,
                signal_name="PrepareForSleep",
                dbus_interface=LOGIND_INTERFACE,
                path=LOGIND_OBJECT_PATH,
            )
            log.info("Monitoring system resume (logind)")
        except dbus.DBusException as e:
            log.warning("Could not monitor system resume: %s", e)

    def _on_prepare_for_sleep(self, about_to_sleep: bool):
        """Handle logind PrepareForSleep signal."""
        if about_to_sleep:
            log.info("System going to sleep — shortcut re-registered on wake")
        else:
            log.info("System woke up — re-registering global shortcut")
            self._setup_done = False
            self._register()

    def _create_session(self):
        """Create a GlobalShortcuts portal session."""
        try:
            portal = self._dbus_connection.get_object(
                PORTAL_BUS_NAME, PORTAL_OBJECT_PATH
            )
            portal_iface = dbus.Interface(portal, PORTAL_INTERFACE)

            request_handle = portal_iface.CreateSession(
                dbus.Dictionary(
                    {"session_handle_token": uuid.uuid4().hex[:12]},
                    signature="sv",
                ),
                reply_handler=self._on_create_session_done,
                error_handler=self._on_dbus_error,
            )
            # request_handle is a D-Bus object path like /org/freedesktop/portal/desktop/request/...
            self._create_session_req_path = request_handle
        except dbus.DBusException as e:
            log.warning("Could not call CreateSession: %s", e)

    def _on_create_session_done(self, request_handle):
        """CreateSession reply received. Now listen for the Response signal."""
        self._create_session_req_path = request_handle
        log.debug("CreateSession request path: %s", request_handle)

        # Listen for Response signal on this specific request path
        self._dbus_connection.add_signal_receiver(
            self._on_create_session_response,
            signal_name="Response",
            dbus_interface=REQUEST_INTERFACE,
            path=request_handle,
        )

    def _on_create_session_response(self, response_code, results):
        """Handle the CreateSession response."""
        log.debug("CreateSession response: code=%s, results=%s", response_code, results)

        if response_code != 0:
            log.error("CreateSession failed with code %s", response_code)
            return

        session_handle = results.get("session_handle", "")
        if session_handle:
            self._session_handle = session_handle
            self._setup_done = True
            log.info("Global shortcut session created: %s", session_handle)
            self._bind_shortcuts()
        else:
            # This can be a BindShortcuts response on the same request path
            log.debug("CreateSession handler skipped: no session_handle in this response")

    def _bind_shortcuts(self):
        """Bind the shortcut key combo."""
        if not self._session_handle:
            return

        try:
            portal = self._dbus_connection.get_object(
                PORTAL_BUS_NAME, PORTAL_OBJECT_PATH
            )
            portal_iface = dbus.Interface(portal, PORTAL_INTERFACE)

            # Use persistent shortcut_id so the portal remembers the user's binding
            self._short_id = "lume-open-v5"
            short_id = self._short_id

            # Shortcut format: (shortcut_id, {preferred_trigger, description})
            # preferred_trigger uses MODIFIER+key format: ALT+space, CTRL+a, etc.
            # Valid modifiers: CTRL, ALT, SHIFT, LOGO (Super), NUM (mod2)
            shortcuts = dbus.Array([
                dbus.Struct(
                    (
                        short_id,
                        dbus.Dictionary({
                            "preferred_trigger": self._shortcut,
                            "description": "Toggle Lume Launcher",
                        }, signature="sv"),
                    ),
                    signature="(sa{sv})",
                )
            ], signature="(sa{sv})")

            log.info("Binding shortcut: id=%s, trigger=%s", short_id, self._shortcut)
            request_handle = portal_iface.BindShortcuts(
                self._session_handle,
                shortcuts,
                "",  # parent_window
                dbus.Dictionary(signature="sv"),
                reply_handler=self._on_bind_done,
                error_handler=self._on_dbus_error,
            )
            self._bind_req_path = request_handle
        except dbus.DBusException as e:
            log.warning("Could not call BindShortcuts: %s", e)

    def _on_bind_done(self, request_handle):
        """BindShortcuts dispatched. Listen for proper Response signal."""
        self._bind_req_path = request_handle
        log.debug("BindShortcuts request path: %s", request_handle)

        # Listen for Response signal on this specific request path
        self._dbus_connection.add_signal_receiver(
            self._on_bind_response,
            signal_name="Response",
            dbus_interface=REQUEST_INTERFACE,
            path=request_handle,
        )

    def _on_bind_response(self, response_code, results):
        """Handle the BindShortcuts response."""
        log.debug("BindShortcuts response: code=%s, results=%s", response_code, results)

        if response_code != 0:
            log.error("BindShortcuts failed with code %s", response_code)
            return

        self._setup_done = True
        log.info("Shortcut bound: %s", self._shortcut)

        # Listen for the Activated signal on the session object path.
        # The xdg-desktop-portal spec says this signal is emitted on the
        # session object path, so we listen specifically on that path.
        # Listen for the Activated signal from the portal.
        # We listen globally (no path restriction) to ensure we catch
        # the signal regardless of how the portal emits it.
        self._dbus_connection.add_signal_receiver(
            self._on_shortcut_activated,
            signal_name="Activated",
            dbus_interface=PORTAL_INTERFACE,
        )
        log.debug("Listening for Activated signal on all paths")

    def _on_shortcut_activated(self, session_handle, shortcut_id, timestamp, options):
        """Shortcut was pressed!"""
        log.info("Shortcut activated: %s at %s", shortcut_id, timestamp)

        if self._suspended:
            log.debug("Shortcut suspended, ignoring activation")
            return

        # Match by prefix since shortcut_id may have timestamp suffix
        if shortcut_id and shortcut_id.startswith("lume-open-v") and self._on_activated:
            log.debug("Matching shortcut, calling on_activated")
            self._on_activated()
        else:
            log.debug("shortcut_id %s does not match lume-open-v*", shortcut_id)

    def suspend(self):
        """Temporarily ignore shortcut activations (for conflict-free capture)."""
        self._suspended = True

    def resume(self):
        """Re-enable shortcut activations."""
        self._suspended = False

    def _on_dbus_error(self, error):
        """Handle D-Bus transport errors."""
        log.error("D-Bus error: %s", error)
        self._setup_done = False

    def cleanup(self):
        """Clean up the global shortcut session.

        In xdg-desktop-portal, sessions auto-terminate when the D-Bus
        connection drops. This method resets internal state.
        """
        self._setup_done = False
        self._session_handle = None
        self._create_session_req_path = None
        self._bind_req_path = None
        self._suspended = False
        log.info("Global shortcut session cleaned up")
