import subprocess
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage


class NetworkPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._nm = None
        self._wifi_list: Gtk.ListBox | None = None
        self._wifi_toggle: Gtk.Switch | None = None
        self._active_box: Gtk.Box | None = None
        self._wired_label: Gtk.Label | None = None
        self._status_label: Gtk.Label | None = None
        self._updating = False

    @property
    def search_keywords(self):
        return [
            (_("WiFi"), _("WiFi")), (_("WiFi"), _("Network")), (_("WiFi"), _("Wireless")),
            (_("WiFi"), _("Hidden network")), (_("WiFi"), _("Password")),
            (_("Wired"), _("Ethernet")), (_("Connection"), _("IP address")),
        ]

    def build(self):
        from ..dbus_helpers import NetworkManagerHelper
        self._nm = NetworkManagerHelper(self.event_bus)

        page = self.make_page_box()

        # -- WiFi group (empty title — header row contains label + switch) --
        wifi_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        wifi_label = Gtk.Label(label=_("WiFi"), xalign=0)
        wifi_label.set_hexpand(True)
        wifi_header.append(wifi_label)
        self._wifi_toggle = Gtk.Switch()
        self._wifi_toggle.set_valign(Gtk.Align.CENTER)
        self._wifi_toggle.connect("state-set", self._on_wifi_toggled)
        wifi_header.append(self._wifi_toggle)

        # Status label (for connection feedback)
        self._status_label = Gtk.Label(xalign=0)
        self._status_label.add_css_class("setting-subtitle")
        self._status_label.set_visible(False)

        # WiFi networks list
        self._wifi_list = Gtk.ListBox()
        self._wifi_list.set_selection_mode(Gtk.SelectionMode.NONE)

        # Buttons row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        scan_btn = Gtk.Button(label=_("Scan"))
        scan_btn.connect("clicked", lambda _: self._nm.request_scan() if self._nm else None)
        btn_row.append(scan_btn)
        hidden_btn = Gtk.Button(label=_("Connect to Hidden Network..."))
        hidden_btn.connect("clicked", lambda _: self._show_hidden_dialog())
        btn_row.append(hidden_btn)

        page.append(self.make_group("", [
            wifi_header, self._status_label, self._wifi_list, btn_row,
        ]))

        # -- Active Connection --
        self._active_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        page.append(self.make_group(_("Active Connection"), [self._active_box]))

        # -- Wired --
        self._wired_label = Gtk.Label(label=_("Checking..."), xalign=0)
        page.append(self.make_group(_("Wired"), [self._wired_label]))

        # Advanced button
        adv_btn = Gtk.Button(label=_("Advanced..."))
        adv_btn.set_halign(Gtk.Align.START)
        def _open_connection_editor(_btn):
            try:
                subprocess.Popen(["nm-connection-editor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                self.store.show_toast(_("Connection editor not found"), True)

        adv_btn.connect("clicked", _open_connection_editor)
        page.append(self.make_group("", [adv_btn]))

        # Subscribe to events
        self.subscribe("nm-ready", self._on_nm_ready)
        self.subscribe("network-changed", lambda _: self._refresh_all())
        self.subscribe("network-connect-success", self._on_connect_success)
        self.subscribe("network-connect-error", self._on_connect_error)

        self.setup_cleanup(page)
        return page

    def _on_nm_ready(self, _data):
        self._updating = True
        self._wifi_toggle.set_active(self._nm.is_wifi_enabled())
        self._updating = False
        self._refresh_all()

    def _on_wifi_toggled(self, _switch, state):
        if self._updating:
            return True
        self._updating = True
        try:
            if self._nm:
                self._nm.set_wifi_enabled(state)
        finally:
            self._updating = False
        return False

    def _refresh_all(self):
        self._refresh_networks()
        self._refresh_active()
        self._refresh_wired()

    def _refresh_networks(self):
        if self._wifi_list is None or self._nm is None:
            return
        while (child := self._wifi_list.get_row_at_index(0)) is not None:
            self._wifi_list.remove(child)
        if not self._nm.ready:
            return
        self._updating = True
        self._wifi_toggle.set_active(self._nm.is_wifi_enabled())
        self._updating = False
        for ap in self._nm.get_access_points():
            self._wifi_list.append(self._build_network_row(ap))

    def _build_network_row(self, ap):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        if ap.strength >= 75:
            icon_name = "network-wireless-signal-excellent-symbolic"
        elif ap.strength >= 50:
            icon_name = "network-wireless-signal-good-symbolic"
        elif ap.strength >= 25:
            icon_name = "network-wireless-signal-ok-symbolic"
        else:
            icon_name = "network-wireless-signal-weak-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        box.append(icon)

        if ap.secured:
            lock = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            lock.set_pixel_size(16)
            box.append(lock)

        name = Gtk.Label(label=ap.ssid, xalign=0)
        name.set_hexpand(True)
        box.append(name)

        if ap.active:
            status = Gtk.Label(label=_("Connected"))
            status.add_css_class("setting-subtitle")
            box.append(status)
            forget = Gtk.Button(label=_("Forget"))
            forget.connect("clicked", lambda _, s=ap.ssid: self._forget(s))
            box.append(forget)
        else:
            connect = Gtk.Button(label=_("Connect"))
            connect.connect("clicked", lambda _, a=ap: self._connect(a))
            box.append(connect)

        row.set_child(box)
        return row

    def _connect(self, ap):
        if ap.secured:
            self._show_password_dialog(ap)
        else:
            self._status_label.set_text(_("Connecting to {ssid}...").format(ssid=ap.ssid))
            self._status_label.set_visible(True)
            self._nm.connect_wifi(ap.ssid, None)

    def _show_password_dialog(self, ap):
        dialog = Gtk.Window(title=_("Connect to {ssid}").format(ssid=ap.ssid), modal=True)
        dialog.set_transient_for(self._wifi_list.get_root())
        dialog.set_default_size(360, 180)
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        pw_entry = Gtk.PasswordEntry()
        pw_entry.set_show_peek_icon(True)
        pw_entry.set_placeholder_text(_("Password"))
        box.append(pw_entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _: dialog.destroy())
        btn_box.append(cancel)
        connect = Gtk.Button(label=_("Connect"))
        connect.add_css_class("suggested-action")

        def _do_connect(_btn):
            pw = pw_entry.get_text()
            if not pw:
                return
            self._status_label.set_text(_("Connecting to {ssid}...").format(ssid=ap.ssid))
            self._status_label.set_visible(True)
            self._nm.connect_wifi(ap.ssid, pw)
            dialog.destroy()

        connect.connect("clicked", _do_connect)
        pw_entry.connect("activate", _do_connect)
        btn_box.append(connect)
        box.append(btn_box)
        dialog.set_child(box)
        dialog.present()

    def _show_hidden_dialog(self):
        dialog = Gtk.Window(title=_("Connect to Hidden Network"), modal=True)
        dialog.set_transient_for(self._wifi_list.get_root())
        dialog.set_default_size(360, 260)
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        ssid_entry = Gtk.Entry()
        ssid_entry.set_placeholder_text(_("Network name (SSID)"))
        box.append(ssid_entry)

        sec_dd = Gtk.DropDown.new_from_strings([_("None"), _("WPA/WPA2"), _("WPA3")])
        box.append(self.make_setting_row(_("Security"), "", sec_dd))

        pw_entry = Gtk.PasswordEntry()
        pw_entry.set_show_peek_icon(True)
        pw_entry.set_placeholder_text(_("Password"))
        box.append(pw_entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label=_("Cancel"))
        cancel.connect("clicked", lambda _: dialog.destroy())
        btn_box.append(cancel)
        connect = Gtk.Button(label=_("Connect"))
        connect.add_css_class("suggested-action")

        def _do_connect(_btn):
            ssid = ssid_entry.get_text().strip()
            if not ssid:
                return
            pw = pw_entry.get_text() if sec_dd.get_selected() > 0 else None
            self._status_label.set_text(_("Connecting to {ssid}...").format(ssid=ssid))
            self._status_label.set_visible(True)
            self._nm.connect_wifi(ssid, pw, hidden=True)
            dialog.destroy()

        connect.connect("clicked", _do_connect)
        btn_box.append(connect)
        box.append(btn_box)
        dialog.set_child(box)
        dialog.present()

    def _forget(self, ssid):
        self._nm.forget_connection(ssid)

    def _on_connect_success(self, _data):
        self._status_label.set_text(_("Connected successfully"))
        self._status_label.set_visible(True)
        GLib.timeout_add_seconds(3, lambda: self._status_label.set_visible(False) or GLib.SOURCE_REMOVE)

    def _on_connect_error(self, message):
        self._status_label.set_text(str(message))
        self._status_label.set_visible(True)

    def _refresh_active(self):
        if self._active_box is None or self._nm is None:
            return
        while (child := self._active_box.get_first_child()) is not None:
            self._active_box.remove(child)
        info = self._nm.get_active_connection_info()
        if info is None:
            self._active_box.append(Gtk.Label(label=_("Not connected"), xalign=0))
            return
        self._active_box.append(self.make_info_row(_("Network"), info.name))
        self._active_box.append(self.make_info_row(_("Type"), info.type))
        self._active_box.append(self.make_info_row(_("IP Address"), info.ip_address))
        self._active_box.append(self.make_info_row(_("Gateway"), info.gateway))
        self._active_box.append(self.make_info_row(_("DNS"), info.dns))

    def _refresh_wired(self):
        if self._wired_label is None or self._nm is None:
            return
        if not self._nm.has_wired():
            self._wired_label.set_text(_("No wired adapter detected"))
        elif self._nm.is_wired_connected():
            self._wired_label.set_text(_("Connected"))
        else:
            self._wired_label.set_text(_("Disconnected"))
