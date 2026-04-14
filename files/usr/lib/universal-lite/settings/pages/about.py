import json
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
    "Sound": [],
    "Power & Lock": [
        "lock_timeout", "display_off_timeout",
        "suspend_timeout", "lid_close_action", "power_profile",
    ],
    "Default Apps": [
        "default_browser", "default_file_manager", "default_terminal",
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
        self._reset_btn.add_css_class("destructive-button")
        self._reset_btn.set_sensitive(False)
        self._reset_btn.connect("clicked", self._on_reset_clicked)
        btn_row.append(self._reset_btn)

        card.append(btn_row)

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
        try:
            defaults = json.loads(
                self._store._defaults_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            self._store.show_toast(_("Could not read defaults file"), True)
            self.close()
            return

        # Merge selected category keys from defaults into current settings
        for category in selected:
            for key in CATEGORY_KEYS.get(category, []):
                if key in defaults:
                    self._store._data[key] = defaults[key]
                else:
                    self._store._data.pop(key, None)

        # Write and apply
        self._store._write()
        try:
            subprocess.run(
                [self._store._apply_script],
                timeout=30, capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # Settings file is written; restart will re-apply

        # Restart the settings app
        self.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)


class AboutPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._update_label = None

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
        page.append(self.make_group_label(_("About")))

        os_name = "Universal-Lite"
        os_version = ""
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("VERSION_ID="):
                    os_version = line.split("=", 1)[1].strip('"')
        except OSError:
            pass
        page.append(self.make_info_row(_("Operating System"), f"{os_name} {os_version}".strip()))
        page.append(self.make_info_row(_("Hostname"), socket.gethostname()))

        cpu = "Unknown"
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        page.append(self.make_info_row(_("Processor"), cpu))

        ram = "Unknown"
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    ram = f"{int(line.split()[1]) / 1048576:.1f} GB"
                    break
        except (OSError, ValueError):
            pass
        page.append(self.make_info_row(_("Memory"), ram))

        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            page.append(self.make_info_row(_("Disk"), f"{used / 1073741824:.1f} GB used of {total / 1073741824:.1f} GB"))
        except OSError:
            pass

        gpu = "Unknown"
        try:
            r = subprocess.run(["lspci"], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if "VGA" in line or "3D" in line or "Display" in line:
                    gpu = line.split(": ", 1)[-1] if ": " in line else line
                    break
        except FileNotFoundError:
            pass
        page.append(self.make_info_row(_("Graphics"), gpu))

        labwc_ver = "unknown"
        try:
            r = subprocess.run(["labwc", "--version"], capture_output=True, text=True)
            labwc_ver = (r.stderr.strip() or r.stdout.strip()) or "unknown"
        except FileNotFoundError:
            pass
        page.append(self.make_info_row(_("Desktop"), f"labwc {labwc_ver}"))

        # OS Updates
        page.append(self.make_group_label(_("Updates")))
        update_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        update_box.set_valign(Gtk.Align.CENTER)
        self._update_label = Gtk.Label(label=_("Click to check for updates"), xalign=0)
        self._update_label.set_hexpand(True)
        update_box.append(self._update_label)
        check_btn = Gtk.Button(label=_("Check for Updates"))
        check_btn.connect("clicked", lambda _: self._check_updates())
        update_box.append(check_btn)
        page.append(update_box)

        # Troubleshooting
        page.append(self.make_group_label(_("Troubleshooting")))
        restore_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        restore_row.set_valign(Gtk.Align.CENTER)
        restore_desc = Gtk.Label(
            label=_("Reset settings to factory defaults"),
            xalign=0,
        )
        restore_desc.set_hexpand(True)
        restore_row.append(restore_desc)
        restore_btn = Gtk.Button(label=_("Restore Defaults..."))
        restore_btn.add_css_class("destructive-button")
        restore_btn.connect("clicked", self._on_restore_defaults_clicked)
        restore_row.append(restore_btn)
        page.append(restore_row)

        return page

    def _check_updates(self):
        self._update_label.set_text(_("Checking..."))
        import threading
        def _check():
            try:
                r = subprocess.run(["bootc", "status", "--json"],
                                   capture_output=True, text=True)
                import json as _json
                status = _json.loads(r.stdout)
                staged = status.get("status", {}).get("staged", None)
                if staged:
                    version = staged.get("image", {}).get("version", "unknown")
                    GLib.idle_add(self._update_label.set_text, _("Update available: {version}").format(version=version))
                else:
                    GLib.idle_add(self._update_label.set_text, _("System is up to date"))
            except Exception:
                GLib.idle_add(self._update_label.set_text, _("Could not check for updates"))
        threading.Thread(target=_check, daemon=True).start()

    def _on_restore_defaults_clicked(self, _btn: Gtk.Button) -> None:
        window = _btn.get_root()
        dialog = RestoreDefaultsDialog(window, self.store)
        dialog.present()
