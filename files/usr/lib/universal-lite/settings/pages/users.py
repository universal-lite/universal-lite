import os
import subprocess
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, GLib, Gtk

from ..base import BasePage


def _hash_password(plaintext: str) -> str:
    """Return a SHA-512 crypt(3) hash suitable for AccountsService.SetPassword.

    Uses openssl which produces the $6$salt$hash format required by
    /etc/shadow.  The stdlib crypt module was removed in Python 3.13.
    """
    result = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=plaintext,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


class UsersPage(BasePage, Adw.PreferencesPage):
    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)
        self._bus = None
        self._user_path = None
        self._nav = None

    @property
    def search_keywords(self):
        return [
            (_("Users"), _("Display name")),
            (_("Users"), _("Password")),
            (_("Users"), _("Auto-login")),
            (_("Users"), _("Account")),
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
        try:
            self._ensure_dbus()
        except GLib.Error:
            status = Adw.StatusPage()
            status.set_icon_name("dialog-error-symbolic")
            status.set_title(_("Could not connect to AccountsService"))
            status.set_description(_("User account settings are unavailable."))
            self.add(status)
            return self

        # Account group
        group = Adw.PreferencesGroup()
        group.set_title(_("Account"))

        # Display name — AdwEntryRow with explicit apply button
        real_name = ""
        try:
            real_name = self._get_property("RealName")
        except GLib.Error:
            pass
        name_row = Adw.EntryRow()
        name_row.set_title(_("Display name"))
        name_row.set_text(real_name)
        name_row.set_show_apply_button(True)
        name_row.connect("apply", self._on_name_activate)
        group.add(name_row)

        # Password — navigation row with chevron suffix
        pw_row = Adw.ActionRow()
        pw_row.set_title(_("Password"))
        pw_row.set_subtitle(_("Set a new password for your account"))
        pw_row.set_activatable(True)
        pw_row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        pw_row.connect("activated", self._push_change_password)
        group.add(pw_row)

        # Automatic login — AdwSwitchRow
        auto_login = False
        try:
            auto_login = self._get_property("AutomaticLogin")
        except GLib.Error:
            pass
        auto_row = Adw.SwitchRow()
        auto_row.set_title(_("Automatic login"))
        auto_row.set_subtitle(_("Log in without a password at startup"))
        auto_row.set_active(auto_login)
        auto_row.connect("notify::active", self._on_autologin_set)
        group.add(auto_row)

        self.add(group)

        # Wrap self in an AdwNavigationView so _push_change_password can push
        self._nav = Adw.NavigationView()
        root_page = Adw.NavigationPage()
        root_page.set_title(_("Users"))
        root_page.set_child(self)  # self IS the PreferencesPage
        self._nav.add(root_page)

        setup_cleanup_target = self._nav
        self.setup_cleanup(setup_cleanup_target)
        return self._nav

    def _on_name_activate(self, row):
        new_name = row.get_text().strip()
        if not new_name:
            return
        try:
            self._bus.call_sync(
                "org.freedesktop.Accounts", self._user_path,
                "org.freedesktop.Accounts.User", "SetRealName",
                GLib.Variant("(s)", (new_name,)),
                None, Gio.DBusCallFlags.NONE, self._DBUS_TIMEOUT_MS, None,
            )
        except GLib.Error:
            pass

    def _on_autologin_set(self, row, _pspec):
        try:
            self._bus.call_sync(
                "org.freedesktop.Accounts", self._user_path,
                "org.freedesktop.Accounts.User", "SetAutomaticLogin",
                GLib.Variant("(b)", (row.get_active(),)),
                None, Gio.DBusCallFlags.NONE, self._DBUS_TIMEOUT_MS, None,
            )
        except GLib.Error:
            pass

    def _push_change_password(self, *_):
        sub = Adw.NavigationPage()
        sub.set_title(_("Change Password"))

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        inner = Adw.PreferencesPage()
        group = Adw.PreferencesGroup()
        group.set_description(_("Enter a new password for your account."))

        new_pw = Adw.PasswordEntryRow()
        new_pw.set_title(_("New password"))
        group.add(new_pw)

        confirm_pw = Adw.PasswordEntryRow()
        confirm_pw.set_title(_("Confirm password"))
        group.add(confirm_pw)

        inner.add(group)

        # Apply button as a suggested-action row below the entries
        action_group = Adw.PreferencesGroup()
        apply_row = Adw.ActionRow()
        apply_btn = Gtk.Button(label=_("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect("clicked", lambda _b: self._apply_password_change(
            new_pw, confirm_pw, sub))
        apply_row.add_suffix(apply_btn)
        action_group.add(apply_row)
        inner.add(action_group)

        toolbar.set_content(inner)
        sub.set_child(toolbar)
        self._nav.push(sub)

    def _apply_password_change(self, new_pw, confirm_pw, sub):
        pw = new_pw.get_text()
        cpw = confirm_pw.get_text()
        if not pw:
            self.store.show_toast(_("Password cannot be empty"))
            return
        if pw != cpw:
            self.store.show_toast(_("Passwords do not match"))
            return
        try:
            hashed = _hash_password(pw)
            self._bus.call_sync(
                "org.freedesktop.Accounts", self._user_path,
                "org.freedesktop.Accounts.User", "SetPassword",
                GLib.Variant("(ss)", (hashed, "")),
                None, Gio.DBusCallFlags.NONE, self._DBUS_TIMEOUT_MS, None,
            )
            self._nav.pop()
        except (GLib.Error, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            self.store.show_toast(_("Failed to set password"))
