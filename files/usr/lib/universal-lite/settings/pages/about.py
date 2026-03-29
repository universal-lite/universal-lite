import os
import socket
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage


class AboutPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._update_label = None

    @property
    def search_keywords(self):
        return [
            ("About", "Operating System"), ("About", "Hostname"),
            ("About", "Processor"), ("About", "Memory"), ("About", "Disk"),
            ("About", "Desktop"), ("About", "Graphics"), ("About", "GPU"),
            ("About", "Updates"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("About"))

        os_name = "Universal-Lite"
        os_version = ""
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("VERSION_ID="):
                    os_version = line.split("=", 1)[1].strip('"')
        except OSError:
            pass
        page.append(self.make_info_row("Operating System", f"{os_name} {os_version}".strip()))
        page.append(self.make_info_row("Hostname", socket.gethostname()))

        cpu = "Unknown"
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
        page.append(self.make_info_row("Processor", cpu))

        ram = "Unknown"
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    ram = f"{int(line.split()[1]) / 1048576:.1f} GB"
                    break
        except (OSError, ValueError):
            pass
        page.append(self.make_info_row("Memory", ram))

        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            used = (st.f_blocks - st.f_bfree) * st.f_frsize
            page.append(self.make_info_row("Disk", f"{used / 1073741824:.1f} GB used of {total / 1073741824:.1f} GB"))
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
        page.append(self.make_info_row("Graphics", gpu))

        labwc_ver = "unknown"
        try:
            labwc_ver = subprocess.run(["labwc", "--version"], capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            pass
        page.append(self.make_info_row("Desktop", f"labwc {labwc_ver}"))

        # OS Updates
        page.append(self.make_group_label("Updates"))
        update_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        update_box.set_valign(Gtk.Align.CENTER)
        self._update_label = Gtk.Label(label="Click to check for updates", xalign=0)
        self._update_label.set_hexpand(True)
        update_box.append(self._update_label)
        check_btn = Gtk.Button(label="Check for Updates")
        check_btn.connect("clicked", lambda _: self._check_updates())
        update_box.append(check_btn)
        page.append(update_box)

        return page

    def _check_updates(self):
        self._update_label.set_text("Checking...")
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
                    GLib.idle_add(self._update_label.set_text, f"Update available: {version}")
                else:
                    GLib.idle_add(self._update_label.set_text, "System is up to date")
            except Exception:
                GLib.idle_add(self._update_label.set_text, "Could not check for updates")
        threading.Thread(target=_check, daemon=True).start()
