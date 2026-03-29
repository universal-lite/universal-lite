import json
import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage


class SoundPage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("Output", "Output device"), ("Output", "Volume"), ("Output", "Mute"),
            ("Input", "Input device"), ("Input", "Microphone"),
        ]

    def build(self):
        page = self.make_page_box()

        # -- Output --
        page.append(self.make_group_label("Output"))
        sinks = self._get_sinks()
        sink_names = [n for n, _ in sinks]
        sink_descs = [d for _, d in sinks]
        default_sink = self._get_default_sink()
        try:
            sink_idx = sink_names.index(default_sink)
        except ValueError:
            sink_idx = 0

        sink_dd = Gtk.DropDown.new(Gtk.StringList.new(sink_descs or ["(No output devices)"]), None)
        sink_dd.set_selected(sink_idx)
        sink_dd.set_size_request(240, -1)
        sink_dd.connect("notify::selected", lambda d, _: (
            subprocess.run(["pactl", "set-default-sink", sink_names[d.get_selected()]], capture_output=True)
            if sink_names and d.get_selected() < len(sink_names) else None
        ))
        page.append(self.make_setting_row("Output device", "", sink_dd))

        out_vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        out_vol.set_value(self._get_volume("@DEFAULT_SINK@"))
        out_vol.set_size_request(200, -1)
        out_vol.set_draw_value(True)
        out_vol.set_format_value_func(lambda _s, v: f"{v:.0f}%")
        out_vol.connect("value-changed", lambda s: subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(s.get_value())}%"], capture_output=True))
        page.append(self.make_setting_row("Volume", "", out_vol))

        out_mute = Gtk.Switch()
        out_mute.set_active(self._get_mute("@DEFAULT_SINK@"))
        out_mute.connect("state-set", lambda _, s: subprocess.run(
            ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if s else "0"], capture_output=True) or False)
        page.append(self.make_setting_row("Mute", "", out_mute))

        # -- Input --
        page.append(self.make_group_label("Input"))
        sources = self._get_sources()
        source_names = [n for n, _ in sources]
        source_descs = [d for _, d in sources]
        default_source = self._get_default_source()
        try:
            source_idx = source_names.index(default_source)
        except ValueError:
            source_idx = 0

        source_dd = Gtk.DropDown.new(Gtk.StringList.new(source_descs or ["(No input devices)"]), None)
        source_dd.set_selected(source_idx)
        source_dd.set_size_request(240, -1)
        source_dd.connect("notify::selected", lambda d, _: (
            subprocess.run(["pactl", "set-default-source", source_names[d.get_selected()]], capture_output=True)
            if source_names and d.get_selected() < len(source_names) else None
        ))
        page.append(self.make_setting_row("Input device", "", source_dd))

        in_vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        in_vol.set_value(self._get_volume("@DEFAULT_SOURCE@", is_source=True))
        in_vol.set_size_request(200, -1)
        in_vol.set_draw_value(True)
        in_vol.set_format_value_func(lambda _s, v: f"{v:.0f}%")
        in_vol.connect("value-changed", lambda s: subprocess.run(
            ["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{int(s.get_value())}%"], capture_output=True))
        page.append(self.make_setting_row("Volume", "", in_vol))

        in_mute = Gtk.Switch()
        in_mute.set_active(self._get_mute("@DEFAULT_SOURCE@", is_source=True))
        in_mute.connect("state-set", lambda _, s: subprocess.run(
            ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if s else "0"], capture_output=True) or False)
        page.append(self.make_setting_row("Mute", "", in_mute))
        return page

    @staticmethod
    def _get_sinks():
        try:
            r = subprocess.run(["pactl", "-f", "json", "list", "sinks"], capture_output=True, text=True)
            return [(s["name"], s.get("description", s["name"])) for s in json.loads(r.stdout)]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return []

    @staticmethod
    def _get_default_sink():
        try:
            return subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            return ""

    @staticmethod
    def _get_sources():
        try:
            r = subprocess.run(["pactl", "-f", "json", "list", "sources"], capture_output=True, text=True)
            return [(s["name"], s.get("description", s["name"]))
                    for s in json.loads(r.stdout) if ".monitor" not in s["name"]]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return []

    @staticmethod
    def _get_default_source():
        try:
            return subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            return ""

    @staticmethod
    def _get_volume(target, is_source=False):
        cmd = "get-source-volume" if is_source else "get-sink-volume"
        try:
            r = subprocess.run(["pactl", cmd, target], capture_output=True, text=True)
            m = re.search(r"(\d+)%", r.stdout)
            return int(m.group(1)) if m else 50
        except FileNotFoundError:
            return 50

    @staticmethod
    def _get_mute(target, is_source=False):
        cmd = "get-source-mute" if is_source else "get-sink-mute"
        try:
            return "yes" in subprocess.run(["pactl", cmd, target], capture_output=True, text=True).stdout.lower()
        except FileNotFoundError:
            return False
