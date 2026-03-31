import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage

TIMEOUT_OPTIONS = [
    ("1 minute", 60), ("2 minutes", 120), ("5 minutes", 300),
    ("10 minutes", 600), ("15 minutes", 900), ("30 minutes", 1800), ("Never", 0),
]

PROFILE_OPTIONS = [
    ("balanced", "Balanced"),
    ("power-saver", "Power Saver"),
    ("performance", "Performance"),
]

LID_OPTIONS = [
    ("Suspend", "suspend"),
    ("Lock", "lock"),
    ("Do Nothing", "nothing"),
]


class PowerLockPage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("Lock & Display", "Lock screen"),
            ("Lock & Display", "Display off"),
            ("Power Profile", "Power"),
            ("Power Profile", "Battery"),
            ("Suspend on Idle", "Suspend"),
            ("Suspend on Idle", "Idle"),
            ("Lid Close Behavior", "Lid"),
        ]

    def build(self):
        page = self.make_page_box()

        # ── Lock & Display ──
        page.append(self.make_group_label("Lock & Display"))
        labels = [l for l, _ in TIMEOUT_OPTIONS]
        seconds = [s for _, s in TIMEOUT_OPTIONS]

        lock_dd = Gtk.DropDown.new_from_strings(labels)
        current_lock = self.store.get("lock_timeout", 300)
        try:
            lock_dd.set_selected(seconds.index(current_lock))
        except ValueError:
            lock_dd.set_selected(2)
        lock_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("lock_timeout", seconds[d.get_selected()]))
        page.append(self.make_setting_row("Lock screen after", "", lock_dd))

        dpms_dd = Gtk.DropDown.new_from_strings(labels)
        current_dpms = self.store.get("display_off_timeout", 600)
        try:
            dpms_dd.set_selected(seconds.index(current_dpms))
        except ValueError:
            dpms_dd.set_selected(2)
        dpms_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("display_off_timeout", seconds[d.get_selected()]))
        page.append(self.make_setting_row("Turn off display after", "", dpms_dd))

        # ── Power Profile ──
        page.append(self.make_group_label("Power Profile"))

        from ..dbus_helpers import PowerProfilesHelper
        power_helper = PowerProfilesHelper(self.event_bus)
        current_profile = power_helper.get_active_profile()

        cards_box = self.make_toggle_cards(
            PROFILE_OPTIONS, current_profile,
            lambda v: power_helper.set_active_profile(v),
        )
        self._profile_buttons = []
        child = cards_box.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.ToggleButton):
                self._profile_buttons.append(child)
            child = child.get_next_sibling()
        page.append(cards_box)

        self.event_bus.subscribe("power-profile-changed", self._on_profile_changed)

        # ── Suspend on Idle ──
        page.append(self.make_group_label("Suspend on Idle"))

        suspend_dd = Gtk.DropDown.new_from_strings(labels)
        current_suspend = self.store.get("suspend_timeout", 0)
        try:
            suspend_dd.set_selected(seconds.index(current_suspend))
        except ValueError:
            suspend_dd.set_selected(6)
        suspend_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("suspend_timeout", seconds[d.get_selected()]))
        page.append(self.make_setting_row("Suspend after", "", suspend_dd))

        # ── Lid Close Behavior ──
        page.append(self.make_group_label("Lid Close Behavior"))

        lid_labels = [l for l, _ in LID_OPTIONS]
        lid_values = [v for _, v in LID_OPTIONS]
        lid_dd = Gtk.DropDown.new_from_strings(lid_labels)
        current_lid = self.store.get("lid_close_action", "suspend")
        try:
            lid_dd.set_selected(lid_values.index(current_lid))
        except ValueError:
            lid_dd.set_selected(0)
        lid_dd.connect("notify::selected", lambda d, _:
            self._on_lid_action_changed(lid_values[d.get_selected()]))
        page.append(self.make_setting_row("When lid is closed", "", lid_dd))

        return page

    def _on_profile_changed(self, new_profile):
        profile_to_label = {
            "balanced": "Balanced",
            "power-saver": "Power Saver",
            "performance": "Performance",
        }
        target = profile_to_label.get(new_profile, "")
        for btn in self._profile_buttons:
            active = btn.get_label() == target
            if btn.get_active() != active:
                btn.set_active(active)

    def _on_lid_action_changed(self, action):
        def _run():
            result = subprocess.run(
                ["pkexec", "/usr/libexec/universal-lite-lid-action", action],
                capture_output=True,
            )
            if result.returncode == 0:
                GLib.idle_add(lambda: self.store.save_and_apply("lid_close_action", action) or False)

        threading.Thread(target=_run, daemon=True).start()
