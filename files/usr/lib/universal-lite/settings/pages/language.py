import subprocess
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk

from ..base import BasePage


class LanguagePage(BasePage, Adw.PreferencesPage):
    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)

    @property
    def search_keywords(self):
        return [
            (_("Language & Region"), _("Language")),
            (_("Language & Region"), _("Locale")),
            (_("Language & Region"), _("Regional format")),
        ]

    def build(self):
        # Info banner — lives outside the group, above it.
        self._banner = Adw.Banner.new(_("Changes take effect after logging out"))
        self._banner.set_revealed(True)

        # Gather locale data before building rows.
        locales = self._get_locales()
        current_locale = self._get_current_locale()
        current_fmt = self._get_current_format()
        loaded = [False]  # mutable so nested lambdas can read it

        # System language row
        lang_row = Adw.ComboRow()
        lang_row.set_title(_("System language"))
        lang_row.set_model(Gtk.StringList.new(locales if locales else ["en_US.UTF-8"]))
        try:
            lang_row.set_selected(locales.index(current_locale))
        except (ValueError, IndexError):
            lang_row.set_selected(0)
        lang_row.connect(
            "notify::selected",
            lambda r, _: None if not loaded[0] or not locales
            else self._set_locale(locales[r.get_selected()]),
        )

        # Regional formats row
        fmt_row = Adw.ComboRow()
        fmt_row.set_title(_("Regional formats"))
        fmt_row.set_subtitle(_("Date, number, and currency format"))
        fmt_row.set_model(Gtk.StringList.new(locales if locales else ["en_US.UTF-8"]))
        try:
            fmt_row.set_selected(locales.index(current_fmt))
        except (ValueError, IndexError):
            fmt_row.set_selected(0)
        fmt_row.connect(
            "notify::selected",
            lambda r, _: None if not loaded[0] or not locales
            else self._set_format(locales[r.get_selected()]),
        )

        group = Adw.PreferencesGroup()
        group.set_title(_("Language & Region"))
        group.add(lang_row)
        group.add(fmt_row)
        self.add(group)

        # Flip the flag AFTER both initial selections have fired so the
        # page-load set_selected calls don't trigger localectl/polkit.
        loaded[0] = True

        wrapper = Adw.ToolbarView()
        wrapper.add_top_bar(self._banner)
        wrapper.set_content(self)
        return wrapper

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
