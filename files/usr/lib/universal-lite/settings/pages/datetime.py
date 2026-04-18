import subprocess
import threading
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage


class DateTimePage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._time_label = None
        self._timer_id = None
        self._mapped = False

    @property
    def search_keywords(self):
        return [
            (_("Date & Time"), _("Timezone")),
            (_("Date & Time"), _("Automatic time")),
            (_("Date & Time"), _("NTP")),
            (_("Date & Time"), _("24-hour clock")),
        ]

    def build(self):
        page = self.make_page_box()

        # Current time display (live updating)
        self._time_label = Gtk.Label(xalign=0)
        self._time_label.add_css_class("group-title")
        self._mapped = True
        self._update_time()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_time)
        page.connect("map", lambda _: setattr(self, "_mapped", True))
        page.connect("unmap", lambda _: self._cleanup())

        # Timezone
        tz_entry = Gtk.Entry()
        tz_entry.set_text(self._get_timezone())
        tz_entry.set_placeholder_text(_("e.g. America/New_York"))
        tz_entry.set_size_request(280, -1)
        tz_entry.connect("activate", lambda e: self._set_timezone(e.get_text().strip(), e))

        # Automatic time (NTP)
        ntp_switch = Gtk.Switch()
        ntp_switch.set_active(self._get_ntp())
        ntp_switch.connect("state-set", lambda _, s: self._set_ntp(s) or False)

        # 24-hour clock
        clock_switch = Gtk.Switch()
        clock_switch.set_active(self.store.get("clock_24h", False))
        clock_switch.connect("state-set", lambda _, s: self.store.save_and_apply("clock_24h", s) or False)

        page.append(self.make_group(_("Date & Time"), [
            self._time_label,
            self.make_setting_row(_("Timezone"), _("Press Enter to apply"), tz_entry),
            self.make_setting_row(_("Automatic time"), _("Sync clock via network (NTP)"), ntp_switch),
            self.make_setting_row(_("24-hour clock"), _("Use 24-hour time format"), clock_switch),
        ]))

        return page

    def _update_time(self):
        if not self._mapped:
            return GLib.SOURCE_REMOVE
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
        self._mapped = False
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    @staticmethod
    def _get_timezone():
        try:
            r = subprocess.run(["timedatectl", "show", "--property=Timezone", "--value"],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "UTC"

    def _set_timezone(self, tz, entry=None):
        def _run():
            try:
                result = subprocess.run(
                    ["timedatectl", "set-timezone", tz],
                    capture_output=True, text=True, timeout=60,
                )
            except (subprocess.TimeoutExpired, OSError):
                GLib.idle_add(lambda: self.store.show_toast(
                    _("Failed to set timezone"), True) or False)
                return
            if result.returncode != 0:
                def _on_fail():
                    self.store.show_toast(_("Invalid timezone"), True)
                    if entry is not None:
                        entry.add_css_class("error")
                    return False
                GLib.idle_add(_on_fail)
            elif entry is not None:
                GLib.idle_add(lambda: entry.remove_css_class("error") or False)

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _get_ntp():
        try:
            r = subprocess.run(["timedatectl", "show", "--property=NTP", "--value"],
                               capture_output=True, text=True, timeout=5)
            return r.stdout.strip().lower() == "yes"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _set_ntp(self, enabled):
        def _run():
            try:
                result = subprocess.run(
                    ["timedatectl", "set-ntp", "true" if enabled else "false"],
                    capture_output=True, text=True, timeout=60,
                )
            except subprocess.TimeoutExpired:
                GLib.idle_add(lambda: self.store.show_toast(
                    _("Automatic time change timed out"), True) or False)
                return
            except FileNotFoundError:
                GLib.idle_add(lambda: self.store.show_toast(
                    _("timedatectl not available"), True) or False)
                return
            if result.returncode != 0:
                GLib.idle_add(lambda: self.store.show_toast(
                    _("Failed to change automatic time"), True) or False)

        threading.Thread(target=_run, daemon=True).start()
