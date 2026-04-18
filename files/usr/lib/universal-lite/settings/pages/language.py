import subprocess
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage


class LanguagePage(BasePage):
    @property
    def search_keywords(self):
        return [
            (_("Language & Region"), _("Language")),
            (_("Language & Region"), _("Locale")),
            (_("Language & Region"), _("Regional format")),
        ]

    def build(self):
        page = self.make_page_box()

        # Info banner
        banner = Gtk.Label(
            label=_("Changes take effect after logging out"),
            xalign=0,
        )
        banner.add_css_class("setting-subtitle")

        # System language
        locales = self._get_locales()
        current_locale = self._get_current_locale()
        current_fmt = self._get_current_format()
        loaded = [False]  # mutable so nested lambdas can read it

        lang_dd = Gtk.DropDown.new_from_strings(locales if locales else ["en_US.UTF-8"])
        try:
            lang_dd.set_selected(locales.index(current_locale))
        except (ValueError, IndexError):
            lang_dd.set_selected(0)
        lang_dd.set_size_request(280, -1)
        lang_dd.connect("notify::selected", lambda d, _:
            None if not loaded[0] or not locales
            else self._set_locale(locales[d.get_selected()]))

        # Regional formats
        fmt_dd = Gtk.DropDown.new_from_strings(locales if locales else ["en_US.UTF-8"])
        try:
            fmt_dd.set_selected(locales.index(current_fmt))
        except (ValueError, IndexError):
            fmt_dd.set_selected(0)
        fmt_dd.set_size_request(280, -1)
        fmt_dd.connect("notify::selected", lambda d, _:
            None if not loaded[0] or not locales
            else self._set_format(locales[d.get_selected()]))

        page.append(self.make_group(_("Language & Region"), [
            banner,
            self.make_setting_row(_("System language"), "", lang_dd),
            self.make_setting_row(_("Regional formats"), _("Date, number, and currency format"), fmt_dd),
        ]))

        # Flip the flag AFTER both initial selections have fired so the
        # page-load set_selected calls don't trigger localectl/polkit.
        loaded[0] = True
        return page

    @staticmethod
    def _get_locales():
        try:
            r = subprocess.run(["localectl", "list-locales"],
                               capture_output=True, text=True, timeout=10)
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ["en_US.UTF-8"]

    @staticmethod
    def _get_current_locale():
        try:
            r = subprocess.run(["localectl", "status"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "LANG=" in line:
                    return line.split("LANG=")[-1].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return "en_US.UTF-8"

    @staticmethod
    def _get_current_format():
        try:
            r = subprocess.run(["localectl", "status"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "LC_TIME=" in line:
                    return line.split("LC_TIME=")[-1].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return LanguagePage._get_current_locale()

    def _set_locale(self, locale):
        try:
            # localectl talks to systemd-localed via D-Bus, which triggers a
            # polkit password dialog (xfce-polkit).  Give the user up to 60s
            # to authenticate — the previous 5s timeout killed the process
            # before the dialog could be answered.
            result = subprocess.run(
                ["localectl", "set-locale", f"LANG={locale}"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                self.store.show_toast(_("Failed to set language"))
        except FileNotFoundError:
            self.store.show_toast(_("localectl not found"))
        except subprocess.TimeoutExpired:
            self.store.show_toast(_("Language change timed out"))

    def _set_format(self, locale):
        try:
            result = subprocess.run(
                ["localectl", "set-locale", f"LC_TIME={locale}",
                 f"LC_NUMERIC={locale}", f"LC_MONETARY={locale}"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                self.store.show_toast(_("Failed to set regional format"))
        except FileNotFoundError:
            self.store.show_toast(_("localectl not found"))
        except subprocess.TimeoutExpired:
            self.store.show_toast(_("Format change timed out"))
