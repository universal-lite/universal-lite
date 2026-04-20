from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from .events import EventBus
from .settings_store import SettingsStore
from .window import SettingsWindow

APP_ID = "org.universallite.Settings"
CSS_PATH = Path(__file__).parent / "css" / "style.css"


class SettingsApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self._store = SettingsStore()
        self._event_bus = EventBus()

    def do_activate(self) -> None:
        win = self.get_active_window()
        if win is not None:
            win.present()
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        win = SettingsWindow(self, self._store, self._event_bus)
        win.present()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        self.set_accels_for_action("win.search", ["<Control>f"])


def main() -> None:
    app = SettingsApp()
    app.run([])
