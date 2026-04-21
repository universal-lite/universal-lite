import json
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
PALETTE_PATH = Path("/usr/share/universal-lite/palette.json")


def _build_accent_css() -> str:
    """Generate the .accent-<name> swatch rules from palette.json.

    Runs at app startup so the accent picker always reflects the
    current palette without a second file to keep in lockstep with
    palette.json. Returns an empty string if palette.json is
    unreadable; the app's @accent_color-driven rules still function
    and only the swatch fills go blank.
    """
    try:
        palette = json.loads(PALETTE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    accents = palette.get("accents", {})
    return "\n".join(
        f".accent-{name} {{ background-color: {hex_value}; }}"
        for name, hex_value in accents.items()
    )


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
        display = Gdk.Display.get_default()
        base_provider = Gtk.CssProvider()
        base_provider.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            display,
            base_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        accent_css = _build_accent_css()
        if accent_css:
            accent_provider = Gtk.CssProvider()
            accent_provider.load_from_string(accent_css)
            Gtk.StyleContext.add_provider_for_display(
                display,
                accent_provider,
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
