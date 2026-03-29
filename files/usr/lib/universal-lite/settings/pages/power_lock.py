import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage

TIMEOUT_OPTIONS = [
    ("1 minute", 60), ("2 minutes", 120), ("5 minutes", 300),
    ("10 minutes", 600), ("15 minutes", 900), ("30 minutes", 1800), ("Never", 0),
]


class PowerLockPage(BasePage):
    @property
    def search_keywords(self):
        return [("Lock & Display", "Lock screen"), ("Lock & Display", "Display off")]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Lock & Display"))
        labels = [l for l, _ in TIMEOUT_OPTIONS]
        seconds = [s for _, s in TIMEOUT_OPTIONS]

        lock_dd = Gtk.DropDown.new_from_strings(labels)
        current_lock = self.store.get("lock_timeout", 300)
        try:
            lock_dd.set_selected(seconds.index(current_lock))
        except ValueError:
            lock_dd.set_selected(2)
        lock_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("lock_timeout", seconds[d.get_selected()]))
        page.append(self.make_setting_row("Lock screen after", "", lock_dd))

        dpms_dd = Gtk.DropDown.new_from_strings(labels)
        current_dpms = self.store.get("display_off_timeout", 600)
        try:
            dpms_dd.set_selected(seconds.index(current_dpms))
        except ValueError:
            dpms_dd.set_selected(2)
        dpms_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("display_off_timeout", seconds[d.get_selected()]))
        page.append(self.make_setting_row("Turn off display after", "", dpms_dd))
        return page
