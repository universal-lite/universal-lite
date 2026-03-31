import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage


class LanguagePage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("Language & Region", "Language"),
            ("Language & Region", "Locale"),
            ("Language & Region", "Regional format"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Language & Region"))

        # Info banner
        banner = Gtk.Label(
            label="Changes take effect after logging out",
            xalign=0,
        )
        banner.add_css_class("setting-subtitle")
        page.append(banner)

        # System language
        locales = self._get_locales()
        current_locale = self._get_current_locale()

        lang_dd = Gtk.DropDown.new_from_strings(locales if locales else ["en_US.UTF-8"])
        try:
            lang_dd.set_selected(locales.index(current_locale))
        except (ValueError, IndexError):
            lang_dd.set_selected(0)
        lang_dd.set_size_request(280, -1)
        lang_dd.connect("notify::selected", lambda d, _:
            self._set_locale(locales[d.get_selected()]) if locales else None)
        page.append(self.make_setting_row("System language", "", lang_dd))

        # Regional formats
        fmt_dd = Gtk.DropDown.new_from_strings(locales if locales else ["en_US.UTF-8"])
        current_fmt = self._get_current_format()
        try:
            fmt_dd.set_selected(locales.index(current_fmt))
        except (ValueError, IndexError):
            fmt_dd.set_selected(0)
        fmt_dd.set_size_request(280, -1)
        fmt_dd.connect("notify::selected", lambda d, _:
            self._set_format(locales[d.get_selected()]) if locales else None)
        page.append(self.make_setting_row("Regional formats", "Date, number, and currency format", fmt_dd))

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

    @staticmethod
    def _set_locale(locale):
        try:
            subprocess.run(["localectl", "set-locale", f"LANG={locale}"],
                           check=False, capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    @staticmethod
    def _set_format(locale):
        try:
            subprocess.run(["localectl", "set-locale", f"LC_TIME={locale}",
                            f"LC_NUMERIC={locale}", f"LC_MONETARY={locale}"],
                           check=False, capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
