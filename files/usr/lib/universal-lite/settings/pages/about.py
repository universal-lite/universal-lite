import os
import socket
import subprocess
import sys
from gettext import gettext as _
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage

CATEGORY_KEYS = {
    "Appearance": [
        "theme", "accent", "wallpaper", "font_size",
        "cursor_size", "high_contrast", "reduce_motion",
    ],
    "Display": [
        "scale", "night_light_enabled", "night_light_temp",
        "night_light_schedule", "night_light_start", "night_light_end",
    ],
    "Panel": [
        "edge", "layout", "pinned", "clock_24h", "density",
    ],
    "Mouse & Touchpad": [
        "touchpad_tap_to_click", "touchpad_natural_scroll",
        "touchpad_pointer_speed", "touchpad_scroll_speed",
        "mouse_pointer_speed", "mouse_natural_scroll", "mouse_accel_profile",
    ],
    "Keyboard": [
        "keyboard_layout", "keyboard_variant",
        "keyboard_repeat_delay", "keyboard_repeat_rate",
        "capslock_behavior",
    ],
    "Power & Lock": [
        "lock_timeout", "display_off_timeout",
        "suspend_timeout", "lid_close_action",
    ],
}


class RestoreDefaultsDialog(Gtk.Window):
    """Modal dialog for selecting which setting categories to reset."""

    def __init__(self, parent: Gtk.Window, store):
        super().__init__(
            transient_for=parent,
            modal=True,
            decorated=False,
            default_width=1,
            default_height=1,
        )
        self._store = store
        self._checks: list[tuple[str, Gtk.CheckButton]] = []

        # Dim overlay background
        overlay_box = Gtk.Box()
        overlay_box.add_css_class("dialog-overlay")
        overlay_box.set_halign(Gtk.Align.FILL)
        overlay_box.set_valign(Gtk.Align.FILL)
        overlay_box.set_hexpand(True)
        overlay_box.set_vexpand(True)
        self.set_child(overlay_box)

        # Centered card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("dialog-card")
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        overlay_box.append(card)

        title = Gtk.Label(label=_("Restore Defaults"))
        title.add_css_class("dialog-title")
        title.set_halign(Gtk.Align.START)
        card.append(title)

        subtitle = Gtk.Label(
            label=_("Select which settings to reset to factory defaults."),
            xalign=0, wrap=True,
        )
        subtitle.add_css_class("dialog-subtitle")
        card.append(subtitle)

        # "Select All" checkbox
        self._select_all = Gtk.CheckButton(label=_("Select All"))
        self._select_all.set_active(False)
        self._select_all.connect("toggled", self._on_select_all_toggled)
        card.append(self._select_all)

        card.append(Gtk.Separator())

        # Category checkboxes
        for category in CATEGORY_KEYS:
            check = Gtk.CheckButton(label=_(category))
            check.connect("toggled", self._on_category_toggled)
            self._checks.append((category, check))
            card.append(check)

        card.append(Gtk.Separator())

        # Button row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=_("Cancel"))
        cancel_btn.connect("clicked", lambda _: self.close())
        btn_row.append(cancel_btn)

        self._reset_btn = Gtk.Button(label=_("Reset"))
        self._reset_btn.add_css_class("destructive-action")
        self._reset_btn.set_sensitive(False)
        self._reset_btn.connect("clicked", self._on_reset_clicked)
        btn_row.append(self._reset_btn)
        self._reset_btn.set_receives_default(True)
        self.set_default_widget(self._reset_btn)

        card.append(btn_row)

        BasePage.enable_escape_close(self)

        # Fullscreen so the overlay covers the parent
        self.fullscreen()

    def _on_select_all_toggled(self, btn: Gtk.CheckButton) -> None:
        active = btn.get_active()
        for _, check in self._checks:
            check.set_active(active)

    def _on_category_toggled(self, _btn: Gtk.CheckButton) -> None:
        any_checked = any(c.get_active() for _, c in self._checks)
        all_checked = all(c.get_active() for _, c in self._checks)
        self._reset_btn.set_sensitive(any_checked)
        # Update "Select All" without re-triggering its handler
        self._select_all.handler_block_by_func(self._on_select_all_toggled)
        self._select_all.set_active(all_checked)
        self._select_all.handler_unblock_by_func(self._on_select_all_toggled)

    def _on_reset_clicked(self, _btn: Gtk.Button) -> None:
        selected = [cat for cat, check in self._checks if check.get_active()]
        if not selected:
            return

        # Load defaults from the image (updated via bootc)
        defaults = self._store.get_defaults()
        if not defaults:
            self._store.show_toast(_("Could not read defaults file"), True)
            self.close()
            return

        # Collect all keys from selected categories
        keys = []
        for category in selected:
            keys.extend(CATEGORY_KEYS.get(category, []))

        # Write merged settings and apply
        self._store.restore_keys(keys, defaults)

        # Wait for apply-settings to finish, then restart
        self.close()

        def _restart():
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return GLib.SOURCE_REMOVE

        # Defer restart one idle tick so GTK finishes unmapping the
        # dialog. Fallback timeout guards against wait_for_apply never
        # firing if apply-settings has already raced to completion by
        # the time we call it.
        restarted = [False]
        def _do_restart():
            if restarted[0]:
                return GLib.SOURCE_REMOVE
            restarted[0] = True
            GLib.idle_add(_restart)
            return GLib.SOURCE_REMOVE

        self._store.wait_for_apply(_do_restart)
        GLib.timeout_add_seconds(10, _do_restart)


class AboutPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._update_label = None
        self._update_btn = None

    @property
    def search_keywords(self):
        return [
            (_("About"), _("Operating System")), (_("About"), _("Hostname")),
            (_("About"), _("Processor")), (_("About"), _("Memory")), (_("About"), _("Disk")),
            (_("About"), _("Desktop")), (_("About"), _("Graphics")), (_("About"), _("GPU")),
            (_("About"), _("Updates")),
            (_("About"), _("Restore Defaults")),
        ]

    def build(self):
        page = self.make_page_box()

        # About group: system info rows
        os_name = "Universal-Lite"
        os_version = ""
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("VERSION_ID="):
                    os_version = line.split("=", 1)[1].strip('"')
        except OSError:
            pass

        cpu = "Unknown"
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass

        ram = "Unknown"
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    ram = f"{int(line.split()[1]) / 1048576:.1f} GB"
                    break
        except (OSError, ValueError):
            pass

        disk_row = None
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            disk_row = self.make_info_row(_("Disk"), f"{used / 1073741824:.1f} GB used of {total / 1073741824:.1f} GB")
        except OSError:
            pass

        gpu = "Unknown"
        try:
            r = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "VGA" in line or "3D" in line or "Display" in line:
                    gpu = line.split(": ", 1)[-1] if ": " in line else line
                    break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        labwc_ver = "unknown"
        try:
            r = subprocess.run(["labwc", "--version"], capture_output=True, text=True, timeout=5)
            labwc_ver = (r.stderr.strip() or r.stdout.strip()) or "unknown"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        about_rows = [
            self.make_info_row(_("Operating System"), f"{os_name} {os_version}".strip()),
            self.make_info_row(_("Hostname"), socket.gethostname()),
            self.make_info_row(_("Processor"), cpu),
            self.make_info_row(_("Memory"), ram),
            self.make_info_row(_("Graphics"), gpu),
            self.make_info_row(_("Desktop"), f"labwc {labwc_ver}"),
        ]
        if disk_row is not None:
            about_rows.insert(4, disk_row)
        page.append(self.make_group(_("About"), about_rows))

        # OS Updates group
        update_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        update_box.set_valign(Gtk.Align.CENTER)
        self._update_label = Gtk.Label(label=_("Click to check for updates"), xalign=0)
        self._update_label.set_hexpand(True)
        update_box.append(self._update_label)
        check_btn = Gtk.Button(label=_("Check for Updates"))
        check_btn.connect("clicked", lambda _: self._check_updates())
        update_box.append(check_btn)
        self._update_btn = Gtk.Button(label=_("Update now..."))
        self._update_btn.add_css_class("suggested-action")
        self._update_btn.set_visible(False)
        self._update_btn.connect("clicked", lambda _: self._run_update())
        update_box.append(self._update_btn)
        page.append(self.make_group(_("Updates"), [update_box]))

        # Troubleshooting group
        restore_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        restore_row.set_valign(Gtk.Align.CENTER)
        restore_desc = Gtk.Label(
            label=_("Reset settings to factory defaults"),
            xalign=0,
        )
        restore_desc.set_hexpand(True)
        restore_row.append(restore_desc)
        restore_btn = Gtk.Button(label=_("Restore Defaults..."))
        restore_btn.add_css_class("destructive-action")
        restore_btn.connect("clicked", self._on_restore_defaults_clicked)
        restore_row.append(restore_btn)
        page.append(self.make_group(_("Troubleshooting"), [restore_row]))

        return page

    def _check_updates(self):
        self._update_label.set_text(_("Checking..."))
        import threading
        def _check():
            try:
                r = subprocess.run(
                    ["uupd", "update-check"],
                    capture_output=True, text=True, timeout=60,
                )
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._update_label.set_text, _("Update check timed out"))
                return
            except FileNotFoundError:
                GLib.idle_add(self._update_label.set_text, _("uupd not available"))
                return
            if r.returncode == 77:
                GLib.idle_add(self._update_label.set_text, _("Update available"))
                GLib.idle_add(self._set_update_button_visible, True)
            elif r.returncode == 0:
                GLib.idle_add(self._update_label.set_text, _("System is up to date"))
                GLib.idle_add(self._set_update_button_visible, False)
            else:
                GLib.idle_add(self._update_label.set_text, _("Could not check for updates"))
        threading.Thread(target=_check, daemon=True).start()

    def _set_update_button_visible(self, visible: bool) -> bool:
        if self._update_btn is not None:
            self._update_btn.set_visible(visible)
        return False

    def _run_update(self) -> None:
        # Spawn a foot terminal so the user sees the ujust update
        # progress and can respond to the sudo prompt.
        try:
            subprocess.Popen(
                ["foot", "-e", "ujust", "update"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            self.store.show_toast(_("Terminal not available"), True)

    def _on_restore_defaults_clicked(self, _btn: Gtk.Button) -> None:
        window = _btn.get_root()
        dialog = RestoreDefaultsDialog(window, self.store)
        dialog.present()
