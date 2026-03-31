import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .events import EventBus
from .settings_store import SettingsStore


class BasePage:
    """Base class for all settings pages. Provides shared widget factories and infrastructure."""

    def __init__(self, store: SettingsStore, event_bus: EventBus) -> None:
        self.store = store
        self.event_bus = event_bus

    @property
    def search_keywords(self) -> list[tuple[str, str]]:
        return []

    def build(self) -> Gtk.Widget:
        raise NotImplementedError

    def refresh(self) -> None:
        pass

    @staticmethod
    def make_page_box() -> Gtk.Box:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        page.set_margin_top(32)
        page.set_margin_bottom(32)
        page.set_margin_start(40)
        page.set_margin_end(40)
        return page

    @staticmethod
    def make_group_label(text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("group-title")
        return lbl

    @staticmethod
    def make_setting_row(label: str, subtitle: str, control: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("setting-row")
        row.set_valign(Gtk.Align.CENTER)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        left.set_hexpand(True)
        left.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label, xalign=0)
        left.append(lbl)
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            sub.add_css_class("setting-subtitle")
            left.append(sub)
        row.append(left)
        control.set_valign(Gtk.Align.CENTER)
        row.append(control)
        return row

    @staticmethod
    def make_info_row(label: str, value: str) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("setting-row")
        row.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label, xalign=0)
        lbl.set_hexpand(True)
        row.append(lbl)
        val = Gtk.Label(label=value, xalign=1)
        val.add_css_class("setting-subtitle")
        row.append(val)
        return row

    @staticmethod
    def make_toggle_cards(options: list[tuple[str, str]], active: str, callback) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons: list[Gtk.ToggleButton] = []
        _updating = [False]

        def _on_toggled(btn: Gtk.ToggleButton, value: str) -> None:
            if _updating[0]:
                return
            if not btn.get_active():
                _updating[0] = True
                btn.set_active(True)
                _updating[0] = False
                return
            _updating[0] = True
            for other in buttons:
                if other is not btn:
                    other.set_active(False)
            _updating[0] = False
            callback(value)

        for value, label in options:
            btn = Gtk.ToggleButton(label=label)
            btn.add_css_class("toggle-card")
            btn.set_active(value == active)
            btn.connect("toggled", _on_toggled, value)
            buttons.append(btn)
            box.append(btn)
        return box
