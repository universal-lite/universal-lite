import subprocess
from gettext import gettext as _

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
        self._updating = False

    @property
    def search_keywords(self):
        return [
            (_("Bluetooth"), _("Bluetooth")), (_("Bluetooth"), _("Pair")),
            (_("Bluetooth"), _("Wireless")), (_("Bluetooth"), _("Device")),
        ]

    def build(self):
        from ..dbus_helpers import BlueZHelper
        self._bt = BlueZHelper(self.event_bus)

        page = self.make_page_box()

        # -- Bluetooth group with inline toggle --
        bt_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bt_lbl = Gtk.Label(label=_("Bluetooth"), xalign=0)
        bt_lbl.set_hexpand(True)
        bt_header.append(bt_lbl)
        self._toggle = Gtk.Switch()
        self._toggle.set_valign(Gtk.Align.CENTER)
        self._toggle.set_active(self._bt.is_powered())
        self._toggle.connect("state-set", self._on_toggle)
        bt_header.append(self._toggle)

        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("setting-subtitle")
        self._status_label.set_visible(False)

        page.append(self.make_group("", [bt_header, self._status_label]))

        if not self._bt.available:
            self._toggle.set_sensitive(False)
            page.append(Gtk.Label(label=_("No Bluetooth adapter found"), xalign=0))
            return page

        # -- Paired devices --
        self._paired_list = Gtk.ListBox()
        self._paired_list.set_selection_mode(Gtk.SelectionMode.NONE)
        page.append(self.make_group(_("Paired Devices"), [self._paired_list]))

        # -- Found devices --
        self._found_list = Gtk.ListBox()
        self._found_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._scan_btn = Gtk.Button(label=_("Search for devices"))
        self._scan_btn.set_halign(Gtk.Align.START)
        self._scan_btn.connect("clicked", self._on_scan_clicked)
        page.append(self.make_group(_("Available Devices"), [self._found_list]))
        page.append(self._scan_btn)

        # Advanced
        adv_btn = Gtk.Button(label=_("Advanced..."))
        adv_btn.set_halign(Gtk.Align.START)
        adv_btn.connect("clicked", lambda _: subprocess.Popen(
            ["blueman-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        page.append(adv_btn)

        # Subscribe
        self.subscribe("bluetooth-changed", lambda _: self._refresh_devices())
        self.subscribe("bluetooth-pair-success", self._on_pair_success)
        self.subscribe("bluetooth-pair-error", self._on_pair_error)

        self._refresh_devices()

        # Stop discovery if page is torn down
        page.connect("unmap", lambda _: self._cleanup())
        self.setup_cleanup(page)
        return page

    def _on_toggle(self, _switch, state):
        if self._updating:
            return True
        self._updating = True
        try:
            self._bt.set_powered(state)
        finally:
            self._updating = False
        return False

    def _on_scan_clicked(self, btn):
        self._bt.start_discovery()
        btn.set_sensitive(False)
        btn.set_label(_("Scanning..."))
        self._scan_timer = GLib.timeout_add_seconds(30, self._stop_scan)

    def _stop_scan(self):
        self._bt.stop_discovery()
        if self._scan_btn:
            self._scan_btn.set_sensitive(True)
            self._scan_btn.set_label(_("Search for devices"))
        self._scan_timer = None
        return GLib.SOURCE_REMOVE

    def _refresh_devices(self):
        if self._paired_list is None or self._found_list is None:
            return
        self._updating = True
        self._toggle.set_active(self._bt.is_powered())
        self._updating = False
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
                status = Gtk.Label(label=_("Connected"))
                status.add_css_class("setting-subtitle")
                box.append(status)
                dc_btn = Gtk.Button(label=_("Disconnect"))
                dc_btn.connect("clicked", lambda _, p=dev.path: self._bt.disconnect_device(p))
                box.append(dc_btn)
            else:
                conn_btn = Gtk.Button(label=_("Connect"))
                conn_btn.connect("clicked", lambda _, p=dev.path: self._bt.connect_device(p))
                box.append(conn_btn)
            forget_btn = Gtk.Button(label=_("Forget"))
            forget_btn.connect("clicked", lambda _, p=dev.path: self._bt.remove_device(p))
            box.append(forget_btn)
        else:
            pair_btn = Gtk.Button(label=_("Pair"))
            pair_btn.connect("clicked", lambda _, p=dev.path: self._pair(p))
            box.append(pair_btn)

        row.set_child(box)
        return row

    def _pair(self, device_path):
        self._status_label.set_text(_("Pairing..."))
        self._status_label.set_visible(True)
        self._bt.pair_device(device_path)

    def _on_pair_success(self, _data):
        self._status_label.set_text(_("Paired successfully"))
        self._status_label.set_visible(True)
        GLib.timeout_add_seconds(3, lambda: self._status_label.set_visible(False) or GLib.SOURCE_REMOVE)

    def _on_pair_error(self, message):
        self._status_label.set_text(_("Pairing failed: {message}").format(message=message))
        self._status_label.set_visible(True)

    def _cleanup(self, *_args):
        if self._scan_timer is not None:
            GLib.source_remove(self._scan_timer)
            self._scan_timer = None
        self._bt.stop_discovery()
        if self._scan_btn:
            self._scan_btn.set_sensitive(True)
            self._scan_btn.set_label(_("Search for devices"))
