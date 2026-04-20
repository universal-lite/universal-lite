import subprocess
import threading
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, Gtk

from ..base import BasePage

# Timeout palette shared by Lock, Display, and Suspend rows. Order is
# the order the options appear in the dropdown. The second element is
# the seconds value persisted in settings (0 = Never).
TIMEOUT_OPTIONS: list[tuple[str, int]] = [
    (_("1 minute"), 60),
    (_("2 minutes"), 120),
    (_("5 minutes"), 300),
    (_("10 minutes"), 600),
    (_("15 minutes"), 900),
    (_("30 minutes"), 1800),
    (_("Never"), 0),
]

PROFILE_OPTIONS: list[tuple[str, str]] = [
    ("balanced", _("Balanced")),
    ("power-saver", _("Power Saver")),
    ("performance", _("Performance")),
]

LID_OPTIONS: list[tuple[str, str]] = [
    ("suspend", _("Suspend")),
    ("lock", _("Lock")),
    ("nothing", _("Do Nothing")),
]


class PowerLockPage(BasePage, Adw.PreferencesPage):
    """Power-management settings: screen/display timeouts, power profile,
    suspend-on-idle, and lid close action.

    Adwaita pilot page. Every other page converted after this one
    inherits this file's patterns:

      - Dual inheritance: BasePage (page protocol) + Adw.PreferencesPage (UI).
      - __init__ is cheap (stores refs only). build() populates and
        returns self so window.py's lazy-build machinery is unchanged.
      - A ComboRow pattern where the on-disk value and the visible
        label are separate: keep a parallel `values` list, map
        get_selected() -> values[idx] on change, values.index(current)
        -> set_selected() on load / external update.
      - Event-bus subscriptions set up in build() and torn down via
        setup_cleanup(self) on unmap.
    """

    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)
        # Widgets we need to reach from outside build() (event-bus
        # handlers, test hooks) are held as attributes. Initialised
        # to None here; populated in build().
        self._profile_row: Adw.ComboRow | None = None

    @property
    def search_keywords(self):
        return [
            (_("Lock & Display"), _("Lock screen")),
            (_("Lock & Display"), _("Display off")),
            (_("Power Profile"), _("Power")),
            (_("Power Profile"), _("Battery")),
            (_("Suspend on Idle"), _("Suspend")),
            (_("Suspend on Idle"), _("Idle")),
            (_("Lid Close Behavior"), _("Lid")),
        ]

    # -- build ----------------------------------------------------------

    def build(self):
        self.add(self._build_lock_display_group())
        self.add(self._build_power_profile_group())
        self.add(self._build_suspend_group())
        self.add(self._build_lid_group())

        # Fire when power-profiles-daemon reports an external change.
        self.subscribe("power-profile-changed", self._on_profile_changed)

        # Tear down event-bus subscriptions on unmap.
        self.setup_cleanup(self)
        return self

    # -- group builders -------------------------------------------------

    def _build_lock_display_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Lock & Display"))

        group.add(self._make_timeout_row(
            title=_("Lock screen after"),
            key="lock_timeout",
            default=300,
        ))
        group.add(self._make_timeout_row(
            title=_("Turn off display after"),
            key="display_off_timeout",
            default=600,
        ))
        return group

    def _build_power_profile_group(self) -> Adw.PreferencesGroup:
        from ..dbus_helpers import PowerProfilesHelper
        self._power_helper = PowerProfilesHelper(self.event_bus)

        row = Adw.ComboRow()
        row.set_title(_("Power profile"))
        row.set_subtitle(_("Balance between performance and battery life"))

        labels = [label for _value, label in PROFILE_OPTIONS]
        values = [value for value, _label in PROFILE_OPTIONS]
        row.set_model(Gtk.StringList.new(labels))

        current = self._power_helper.get_active_profile()
        row.set_selected(
            values.index(current) if current in values else 0
        )

        def _on_selected(r: Adw.ComboRow, _pspec) -> None:
            idx = r.get_selected()
            if 0 <= idx < len(values):
                self._power_helper.set_active_profile(values[idx])

        row.connect("notify::selected", _on_selected)
        self._profile_row = row

        group = Adw.PreferencesGroup()
        group.set_title(_("Power Profile"))
        group.add(row)
        return group

    def _build_suspend_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Suspend on Idle"))
        group.set_description(
            _("Put the computer to sleep after a period of inactivity.")
        )
        group.add(self._make_timeout_row(
            title=_("Suspend after"),
            key="suspend_timeout",
            default=0,  # Never, by default
        ))
        return group

    def _build_lid_group(self) -> Adw.PreferencesGroup:
        row = Adw.ComboRow()
        row.set_title(_("When lid is closed"))

        labels = [label for _value, label in LID_OPTIONS]
        values = [value for value, _label in LID_OPTIONS]
        row.set_model(Gtk.StringList.new(labels))

        current = self.store.get("lid_close_action", "suspend")
        row.set_selected(values.index(current) if current in values else 0)

        def _on_selected(r: Adw.ComboRow, _pspec) -> None:
            idx = r.get_selected()
            if 0 <= idx < len(values):
                self._on_lid_action_changed(values[idx])

        row.connect("notify::selected", _on_selected)

        group = Adw.PreferencesGroup()
        group.set_title(_("Lid Close Behavior"))
        group.add(row)
        return group

    # -- row factory ----------------------------------------------------

    def _make_timeout_row(self, *, title: str, key: str,
                          default: int) -> Adw.ComboRow:
        row = Adw.ComboRow()
        row.set_title(title)

        labels = [label for label, _secs in TIMEOUT_OPTIONS]
        values = [secs for _label, secs in TIMEOUT_OPTIONS]
        row.set_model(Gtk.StringList.new(labels))

        current = self.store.get(key, default)
        row.set_selected(values.index(current) if current in values else 0)

        def _on_selected(r: Adw.ComboRow, _pspec) -> None:
            idx = r.get_selected()
            if 0 <= idx < len(values):
                self.store.save_and_apply(key, values[idx])

        row.connect("notify::selected", _on_selected)
        return row

    # -- event handlers -------------------------------------------------

    def _on_profile_changed(self, new_profile: str) -> None:
        """Move the ComboRow selection to match an out-of-band profile change.

        Fires when power-profiles-daemon reports that the active
        profile changed via some mechanism other than our row (e.g.
        `powerprofilesctl set`). Guarded by an identity check against
        the current selection so we don't loop on our own save.
        """
        if self._profile_row is None:
            return
        values = [value for value, _label in PROFILE_OPTIONS]
        if new_profile not in values:
            return
        idx = values.index(new_profile)
        if self._profile_row.get_selected() != idx:
            self._profile_row.set_selected(idx)

    def _on_lid_action_changed(self, action: str) -> None:
        """Apply a new lid action via the privileged helper.

        Preserved verbatim from the pre-migration version: pkexec on
        a background thread; on success, persist via the store on the
        GLib main loop; on failure, show a toast.
        """
        def _run() -> None:
            try:
                result = subprocess.run(
                    ["pkexec", "/usr/libexec/universal-lite-lid-action", action],
                    capture_output=True, timeout=60,
                )
            except subprocess.TimeoutExpired:
                GLib.idle_add(
                    lambda: self.store.show_toast(
                        _("Lid action change timed out"), True) or False
                )
                return
            except OSError:
                GLib.idle_add(
                    lambda: self.store.show_toast(
                        _("pkexec not available"), True) or False
                )
                return

            if result.returncode == 0:
                GLib.idle_add(
                    lambda: self.store.save_and_apply(
                        "lid_close_action", action) or False
                )
            elif result.returncode == 126:
                # Polkit auth declined — silent, user already knows.
                pass
            else:
                GLib.idle_add(
                    lambda: self.store.show_toast(
                        _("Failed to change lid close action"), True) or False
                )

        threading.Thread(target=_run, daemon=True).start()
