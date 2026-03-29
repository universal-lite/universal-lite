import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage


class DateTimePage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._time_label = None
        self._timer_id = None

    @property
    def search_keywords(self):
        return [
            ("Date & Time", "Timezone"),
            ("Date & Time", "Automatic time"),
            ("Date & Time", "NTP"),
            ("Date & Time", "24-hour clock"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Date & Time"))

        # Current time display (live updating)
        self._time_label = Gtk.Label(xalign=0)
        self._time_label.add_css_class("group-title")
        self._update_time()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_time)
        page.append(self._time_label)
        page.connect("unmap", lambda _: self._cleanup())

        # Timezone
        tz_entry = Gtk.Entry()
        tz_entry.set_text(self._get_timezone())
        tz_entry.set_placeholder_text("e.g. America/New_York")
        tz_entry.set_size_request(280, -1)
        tz_entry.connect("activate", lambda e: self._set_timezone(e.get_text().strip()))
        page.append(self.make_setting_row("Timezone", "Press Enter to apply", tz_entry))

        # Automatic time (NTP)
        ntp_switch = Gtk.Switch()
        ntp_switch.set_active(self._get_ntp())
        ntp_switch.connect("state-set", lambda _, s: self._set_ntp(s) or False)
        page.append(self.make_setting_row("Automatic time", "Sync clock via network (NTP)", ntp_switch))

        # 24-hour clock
        clock_switch = Gtk.Switch()
        clock_switch.set_active(self.store.get("clock_24h", False))
        clock_switch.connect("state-set", lambda _, s: self.store.save_and_apply("clock_24h", s) or False)
        page.append(self.make_setting_row("24-hour clock", "Use 24-hour time format", clock_switch))

        return page

    def _update_time(self):
        import datetime

        now = datetime.datetime.now()
        if self.store.get("clock_24h", False):
            fmt = "%A, %B %d, %Y  %H:%M:%S"
        else:
            fmt = "%A, %B %d, %Y  %I:%M:%S %p"
        if self._time_label:
            self._time_label.set_text(now.strftime(fmt))
        return GLib.SOURCE_CONTINUE

    def _cleanup(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    @staticmethod
    def _get_timezone():
        try:
            r = subprocess.run(["timedatectl", "show", "--property=Timezone", "--value"],
                               capture_output=True, text=True)
            return r.stdout.strip()
        except FileNotFoundError:
            return "UTC"

    @staticmethod
    def _set_timezone(tz):
        subprocess.run(["timedatectl", "set-timezone", tz], check=False,
                       capture_output=True)

    @staticmethod
    def _get_ntp():
        try:
            r = subprocess.run(["timedatectl", "show", "--property=NTP", "--value"],
                               capture_output=True, text=True)
            return r.stdout.strip().lower() == "yes"
        except FileNotFoundError:
            return False

    @staticmethod
    def _set_ntp(enabled):
        subprocess.run(["timedatectl", "set-ntp", "true" if enabled else "false"],
                       check=False, capture_output=True)
