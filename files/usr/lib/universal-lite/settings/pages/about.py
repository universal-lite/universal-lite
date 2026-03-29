import os
import socket
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from ..base import BasePage


class AboutPage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("About", "Operating System"), ("About", "Hostname"),
            ("About", "Processor"), ("About", "Memory"), ("About", "Disk"),
            ("About", "Desktop"),
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

        labwc_ver = "unknown"
        try:
            labwc_ver = subprocess.run(["labwc", "--version"], capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            pass
        page.append(self.make_info_row("Desktop", f"labwc {labwc_ver}"))
        return page
