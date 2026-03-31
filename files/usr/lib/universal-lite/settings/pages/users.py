import os
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from ..base import BasePage


def _hash_password(plaintext: str) -> str:
    """Return a SHA-512 crypt(3) hash suitable for AccountsService.SetPassword."""
    result = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=plaintext,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class UsersPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._bus = None
        self._user_path = None

    @property
    def search_keywords(self):
        return [
            ("Users", "Display name"),
            ("Users", "Password"),
            ("Users", "Auto-login"),
            ("Users", "Account"),
        ]

    _DBUS_TIMEOUT_MS = 5000

    def _ensure_dbus(self):
        """Lazily connect to the system bus and find the current user's object path."""
        if self._bus is not None:
            return
        self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        uid = os.getuid()
        result = self._bus.call_sync(
            "org.freedesktop.Accounts",
            "/org/freedesktop/Accounts",
            "org.freedesktop.Accounts",
            "FindUserById",
            GLib.Variant("(x)", (uid,)),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE, self._DBUS_TIMEOUT_MS, None,
        )
        self._user_path = result.unpack()[0]

    def _get_property(self, prop_name):
        """Get a property from the AccountsService User interface."""
        result = self._bus.call_sync(
            "org.freedesktop.Accounts", self._user_path,
            "org.freedesktop.DBus.Properties", "Get",
            GLib.Variant("(ss)", ("org.freedesktop.Accounts.User", prop_name)),
            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, self._DBUS_TIMEOUT_MS, None,
        )
        return result.unpack()[0]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Users"))

        try:
            self._ensure_dbus()
        except GLib.Error:
            error_label = Gtk.Label(
                label="Could not connect to AccountsService",
                xalign=0,
            )
            error_label.add_css_class("setting-subtitle")
            page.append(error_label)
            return page

        # Display name
        real_name = ""
        try:
            real_name = self._get_property("RealName")
        except GLib.Error:
            pass
        name_entry = Gtk.Entry()
        name_entry.set_text(real_name)
        name_entry.set_placeholder_text("Display name")
        name_entry.set_size_request(280, -1)
        name_entry.connect("activate", self._on_name_activate)
        page.append(self.make_setting_row("Display name", "Press Enter to apply", name_entry))

        # Change Password
        pw_button = Gtk.Button(label="Change Password")
        pw_button.connect("clicked", self._on_change_password)
        page.append(self.make_setting_row("Password", "Set a new password for your account", pw_button))

        # Auto-login
        auto_login = False
        try:
            auto_login = self._get_property("AutomaticLogin")
        except GLib.Error:
            pass
        auto_switch = Gtk.Switch()
        auto_switch.set_active(auto_login)
        auto_switch.connect("state-set", self._on_autologin_set)
        page.append(self.make_setting_row("Automatic login", "Log in without a password at startup", auto_switch))

        return page

    def _on_name_activate(self, entry):
        new_name = entry.get_text().strip()
        if not new_name:
            return
        try:
            self._bus.call_sync(
                "org.freedesktop.Accounts", self._user_path,
                "org.freedesktop.Accounts.User", "SetRealName",
                GLib.Variant("(s)", (new_name,)),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass

    def _on_autologin_set(self, switch, state):
        try:
            self._bus.call_sync(
                "org.freedesktop.Accounts", self._user_path,
                "org.freedesktop.Accounts.User", "SetAutomaticLogin",
                GLib.Variant("(b)", (state,)),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass
        return False

    def _on_change_password(self, button):
        dialog = Gtk.Window(title="Change Password")
        dialog.set_default_size(400, -1)
        dialog.set_modal(True)
        root = button.get_root()
        if root:
            dialog.set_transient_for(root)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        heading = Gtk.Label(label="Change Password")
        heading.add_css_class("group-title")
        box.append(heading)

        new_pw = Gtk.PasswordEntry()
        new_pw.set_show_peek_icon(True)
        new_pw.set_placeholder_text("New password")
        box.append(new_pw)

        confirm_pw = Gtk.PasswordEntry()
        confirm_pw.set_show_peek_icon(True)
        confirm_pw.set_placeholder_text("Confirm password")
        box.append(confirm_pw)

        error_label = Gtk.Label(label="")
        error_label.add_css_class("setting-subtitle")
        box.append(error_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: dialog.close())
        button_box.append(cancel_btn)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")

        def _apply(_):
            pw = new_pw.get_text()
            cpw = confirm_pw.get_text()
            if not pw:
                error_label.set_text("Password cannot be empty")
                return
            if pw != cpw:
                error_label.set_text("Passwords do not match")
                return
            try:
                hashed = _hash_password(pw)
                self._bus.call_sync(
                    "org.freedesktop.Accounts", self._user_path,
                    "org.freedesktop.Accounts.User", "SetPassword",
                    GLib.Variant("(ss)", (hashed, "")),
                    None, Gio.DBusCallFlags.NONE, -1, None,
                )
                dialog.close()
            except (GLib.Error, subprocess.CalledProcessError):
                error_label.set_text("Failed to set password")

        apply_btn.connect("clicked", _apply)
        button_box.append(apply_btn)
        box.append(button_box)

        dialog.set_child(box)
        dialog.present()
