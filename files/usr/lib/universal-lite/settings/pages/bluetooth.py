import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from ..base import BasePage

class BluetoothPage(BasePage):
    @property
    def search_keywords(self):
        return [("Bluetooth", "Bluetooth")]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Bluetooth"))
        page.append(Gtk.Label(label="Bluetooth settings — coming soon"))
        return page
