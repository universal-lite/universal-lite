from gettext import gettext as _  # noqa: F401 - re-exported for page modules

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: F401 - re-exported for page modules

from .events import EventBus
from .settings_store import SettingsStore


class BasePage:
    """Minimal shared protocol every settings page implements.

    This used to be the home for a pile of Gtk widget factory
    staticmethods (make_page_box, make_group, make_setting_row,
    make_info_row, make_toggle_cards) that each page pulled from
    to build its hand-rolled Gtk.Box layouts. After the libadwaita
    migration (Phases 0-3), every page inherits from
    Adw.PreferencesPage and builds its UI from native Adw.*Row
    widgets, so the factories have no callers. Phase 4 dropped them
    along with the enable_escape_close dialog helper (no Gtk.Window
    dialogs remain in any page - everything is AdwAlertDialog or
    AdwNavigationView push).
    """

    def __init__(self, store: SettingsStore, event_bus: EventBus) -> None:
        self.store = store
        self.event_bus = event_bus
        self._subscriptions: list[tuple[str, object]] = []

    @property
    def search_keywords(self) -> list[tuple[str, str]]:
        return []

    def build(self) -> Gtk.Widget:
        raise NotImplementedError

    def refresh(self) -> None:
        pass

    def subscribe(self, event: str, callback) -> None:
        """Subscribe to an event and track it for cleanup on unmap."""
        self.event_bus.subscribe(event, callback)
        self._subscriptions.append((event, callback))

    def unsubscribe_all(self) -> None:
        """Unsubscribe every tracked callback."""
        for event, callback in self._subscriptions:
            self.event_bus.unsubscribe(event, callback)
        self._subscriptions.clear()

    def setup_cleanup(self, widget: Gtk.Widget) -> None:
        """Connect the widget's unmap signal to unsubscribe_all.

        Call this from build() on whichever widget actually leaves
        the visible tree when the user navigates away from the page -
        for most pages that's self (the PreferencesPage); for pages
        wrapped in an AdwNavigationView, it's self._nav, because the
        PreferencesPage itself unmaps when sub-pages are pushed.
        """
        widget.connect("unmap", lambda _: self.unsubscribe_all())
