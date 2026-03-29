import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage


class BluetoothPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._bt = None
        self._toggle: Gtk.Switch | None = None
        self._paired_list: Gtk.ListBox | None = None
        self._found_list: Gtk.ListBox | None = None
        self._scan_btn: Gtk.Button | None = None
        self._scan_timer: int | None = None
        self._status_label: Gtk.Label | None = None

    @property
    def search_keywords(self):
        return [
            ("Bluetooth", "Bluetooth"), ("Bluetooth", "Pair"),
            ("Bluetooth", "Wireless"), ("Bluetooth", "Device"),
        ]

    def build(self):
        from ..dbus_helpers import BlueZHelper
        self._bt = BlueZHelper(self.event_bus)

        page = self.make_page_box()

        # -- Header with toggle --
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.append(self.make_group_label("Bluetooth"))
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header.append(spacer)
        self._toggle = Gtk.Switch()
        self._toggle.set_valign(Gtk.Align.CENTER)
        self._toggle.set_active(self._bt.is_powered())
        self._toggle.connect("state-set", self._on_toggle)
        header.append(self._toggle)
        page.append(header)

        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("setting-subtitle")
        self._status_label.set_visible(False)
        page.append(self._status_label)

        if not self._bt.available:
            page.append(Gtk.Label(label="No Bluetooth adapter found", xalign=0))
            return page

        # -- Paired devices --
        page.append(self.make_group_label("Paired Devices"))
        self._paired_list = Gtk.ListBox()
        self._paired_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(self._paired_list)

        # -- Found devices --
        page.append(self.make_group_label("Available Devices"))
        self._found_list = Gtk.ListBox()
        self._found_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(self._found_list)

        self._scan_btn = Gtk.Button(label="Search for devices")
        self._scan_btn.set_halign(Gtk.Align.START)
        self._scan_btn.connect("clicked", self._on_scan_clicked)
        page.append(self._scan_btn)

        # Advanced
        adv_btn = Gtk.Button(label="Advanced...")
        adv_btn.set_halign(Gtk.Align.START)
        adv_btn.connect("clicked", lambda _: subprocess.Popen(
            ["blueman-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        page.append(adv_btn)

        # Subscribe
        self.event_bus.subscribe("bluetooth-changed", lambda _: self._refresh_devices())
        self.event_bus.subscribe("bluetooth-pair-success", self._on_pair_success)
        self.event_bus.subscribe("bluetooth-pair-error", self._on_pair_error)

        self._refresh_devices()

        # Stop discovery if page is torn down
        page.connect("unmap", lambda _: self._cleanup())
        return page

    def _on_toggle(self, _switch, state):
        self._bt.set_powered(state)
        return False

    def _on_scan_clicked(self, btn):
        self._bt.start_discovery()
        btn.set_sensitive(False)
        btn.set_label("Scanning...")
        self._scan_timer = GLib.timeout_add_seconds(30, self._stop_scan)

    def _stop_scan(self):
        self._bt.stop_discovery()
        if self._scan_btn:
            self._scan_btn.set_sensitive(True)
            self._scan_btn.set_label("Search for devices")
        self._scan_timer = None
        return GLib.SOURCE_REMOVE

    def _refresh_devices(self):
        if self._paired_list is None or self._found_list is None:
            return
        self._toggle.set_active(self._bt.is_powered())
        # Clear lists
        for lb in (self._paired_list, self._found_list):
            while (child := lb.get_row_at_index(0)) is not None:
                lb.remove(child)
        for dev in self._bt.get_devices():
            row = self._build_device_row(dev)
            if dev.paired:
                self._paired_list.append(row)
            else:
                self._found_list.append(row)

    def _build_device_row(self, dev):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name(dev.icon or "bluetooth-symbolic")
        icon.set_pixel_size(16)
        box.append(icon)

        name = Gtk.Label(label=dev.name, xalign=0)
        name.set_hexpand(True)
        box.append(name)

        if dev.paired:
            if dev.connected:
                status = Gtk.Label(label="Connected")
                status.add_css_class("setting-subtitle")
                box.append(status)
                dc_btn = Gtk.Button(label="Disconnect")
                dc_btn.connect("clicked", lambda _, p=dev.path: self._bt.disconnect_device(p))
                box.append(dc_btn)
            else:
                conn_btn = Gtk.Button(label="Connect")
                conn_btn.connect("clicked", lambda _, p=dev.path: self._bt.connect_device(p))
                box.append(conn_btn)
            forget_btn = Gtk.Button(label="Forget")
            forget_btn.connect("clicked", lambda _, p=dev.path: self._bt.remove_device(p))
            box.append(forget_btn)
        else:
            pair_btn = Gtk.Button(label="Pair")
            pair_btn.connect("clicked", lambda _, p=dev.path: self._pair(p))
            box.append(pair_btn)

        row.set_child(box)
        return row

    def _pair(self, device_path):
        self._status_label.set_text("Pairing...")
        self._status_label.set_visible(True)
        self._bt.pair_device(device_path)

    def _on_pair_success(self, _data):
        self._status_label.set_text("Paired successfully")
        self._status_label.set_visible(True)
        GLib.timeout_add_seconds(3, lambda: self._status_label.set_visible(False) or GLib.SOURCE_REMOVE)

    def _on_pair_error(self, message):
        self._status_label.set_text(f"Pairing failed: {message}")
        self._status_label.set_visible(True)

    def _cleanup(self, *_args):
        if self._scan_timer is not None:
            GLib.source_remove(self._scan_timer)
            self._scan_timer = None
        self._bt.stop_discovery()
