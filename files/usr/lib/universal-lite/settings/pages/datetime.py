import subprocess
import threading
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from ..base import BasePage


class DateTimePage(BasePage, Adw.PreferencesPage):
    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)
        self._timer_id = None
        self._mapped = False
        self._time_group: Adw.PreferencesGroup | None = None

    @property
    def search_keywords(self):
        return [
            (_("Date & Time"), _("Timezone")),
            (_("Date & Time"), _("Automatic time")),
            (_("Date & Time"), _("NTP")),
            (_("Date & Time"), _("24-hour clock")),
        ]

    def build(self):
        group = Adw.PreferencesGroup()
        group.set_title(_("Date & Time"))
        self._time_group = group

        # Seed the group description with the current time, then start the
        # 1 Hz timer. Re-arm the timer on every map so navigating away
        # and back doesn't leave the clock frozen — _cleanup cancels
        # the source and nulls the id, but only _build() previously
        # re-created it, so after the first unmap the clock stopped
        # updating permanently (pages are cached, _build() runs once).
        self._mapped = True
        self._update_time()
        self._timer_id = GLib.timeout_add_seconds(1, self._update_time)

        def _on_map(_w):
            self._mapped = True
            if self._timer_id is None:
                self._update_time()
                self._timer_id = GLib.timeout_add_seconds(1, self._update_time)

        self.connect("map", _on_map)
        self.connect("unmap", lambda _: self._cleanup())

        # Timezone — AdwEntryRow with an explicit apply button so the
        # subprocess is not called on every keystroke.
        tz_row = Adw.EntryRow()
        tz_row.set_title(_("Timezone"))
        tz_row.set_text(self._get_timezone())
        tz_row.set_show_apply_button(True)
        tz_row.connect("apply", lambda r: self._set_timezone(r.get_text().strip(), r))
        group.add(tz_row)

        # Automatic time (NTP)
        ntp_row = Adw.SwitchRow()
        ntp_row.set_title(_("Automatic time"))
        ntp_row.set_subtitle(_("Sync clock via network (NTP)"))
        ntp_row.set_active(self._get_ntp())
        ntp_row.connect("notify::active", lambda r, _p: self._set_ntp(r.get_active()))
        group.add(ntp_row)

        # 24-hour clock
        clock_row = Adw.SwitchRow()
        clock_row.set_title(_("24-hour clock"))
        clock_row.set_subtitle(_("Use 24-hour time format"))
        clock_row.set_active(self.store.get("clock_24h", False))
        clock_row.connect(
            "notify::active",
            lambda r, _p: self.store.save_and_apply("clock_24h", r.get_active()),
        )
        group.add(clock_row)

        self.add(group)
        return self

    # -- live clock ---------------------------------------------------------

    def _update_time(self):
        if not self._mapped:
            return GLib.SOURCE_REMOVE
        import datetime

        now = datetime.datetime.now()
        if self.store.get("clock_24h", False):
            fmt = "%A, %B %d, %Y  %H:%M:%S"
        else:
            fmt = "%A, %B %d, %Y  %I:%M:%S %p"
        if self._time_group is not None:
            self._time_group.set_description(now.strftime(fmt))
        return GLib.SOURCE_CONTINUE

    def _cleanup(self):
        self._mapped = False
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    # -- timezone -----------------------------------------------------------

    @staticmethod
    def _get_timezone():
        try:
            r = subprocess.run(
                ["timedatectl", "show", "--property=Timezone", "--value"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "UTC"

    def _set_timezone(self, tz, entry=None):
        # Clear any previous error tint before we start the attempt.
        # Previously the "error" CSS class was only removed on success,
        # so a user fixing a typo but then hitting a different failure
        # mode (timeout, missing tool) kept staring at a red-tinted row
        # even after editing the text. Clear once up front; failure
        # paths re-add as needed.
        if entry is not None:
            entry.remove_css_class("error")

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

        threading.Thread(target=_run, daemon=True).start()

    # -- NTP ----------------------------------------------------------------

    @staticmethod
    def _get_ntp():
        try:
            # Force C locale on the timedatectl invocation so the
            # "yes"/"no" value token can't be localized by a
            # non-English session env. Some downstream systemd builds
            # and older versions emit localized tokens; ours expects
            # literal "yes".
            import os
            env = {**os.environ, "LC_ALL": "C"}
            r = subprocess.run(
                ["timedatectl", "show", "--property=NTP", "--value"],
                capture_output=True, text=True, timeout=5, env=env,
            )
            return r.stdout.strip().lower() == "yes"
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
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
                    _("Time settings are unavailable on this system"), True) or False)
                return
            if result.returncode != 0:
                GLib.idle_add(lambda: self.store.show_toast(
                    _("Failed to change automatic time"), True) or False)

        threading.Thread(target=_run, daemon=True).start()
