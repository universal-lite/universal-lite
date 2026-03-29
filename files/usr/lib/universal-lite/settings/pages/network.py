import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from ..base import BasePage

class NetworkPage(BasePage):
    @property
    def search_keywords(self):
        return [("WiFi", "Network"), ("Wired", "Ethernet")]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Network"))
        page.append(Gtk.Label(label="Network settings — coming soon"))
        return page
