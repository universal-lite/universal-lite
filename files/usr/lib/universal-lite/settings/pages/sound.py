import json
import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage
from ..dbus_helpers import PulseAudioSubscriber


class SoundPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._pa = None
        self._updating = False
        # Widget refs for live updates
        self._sink_dd = None
        self._out_vol = None
        self._out_mute = None
        self._source_dd = None
        self._in_vol = None
        self._in_mute = None
        self._sink_names = []
        self._source_names = []

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
        self._sink_names = [n for n, _ in sinks]
        sink_descs = [d for _, d in sinks]
        default_sink = self._get_default_sink()
        try:
            sink_idx = self._sink_names.index(default_sink)
        except ValueError:
            sink_idx = 0

        self._sink_dd = Gtk.DropDown.new(
            Gtk.StringList.new(sink_descs or ["(No output devices)"]), None,
        )
        self._sink_dd.set_selected(sink_idx)
        self._sink_dd.set_size_request(240, -1)
        self._sink_dd.connect("notify::selected", self._on_sink_selected)
        page.append(self.make_setting_row("Output device", "", self._sink_dd))

        self._out_vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._out_vol.set_value(self._get_volume("@DEFAULT_SINK@"))
        self._out_vol.set_size_request(200, -1)
        self._out_vol.set_draw_value(True)
        self._out_vol.set_format_value_func(lambda _s, v: f"{v:.0f}%")
        self._out_vol.connect("value-changed", self._on_out_vol_changed)
        page.append(self.make_setting_row("Volume", "", self._out_vol))

        self._out_mute = Gtk.Switch()
        self._out_mute.set_active(self._get_mute("@DEFAULT_SINK@"))
        self._out_mute.connect("state-set", self._on_out_mute_set)
        page.append(self.make_setting_row("Mute", "", self._out_mute))

        # -- Input --
        page.append(self.make_group_label("Input"))

        sources = self._get_sources()
        self._source_names = [n for n, _ in sources]
        source_descs = [d for _, d in sources]
        default_source = self._get_default_source()
        try:
            source_idx = self._source_names.index(default_source)
        except ValueError:
            source_idx = 0

        self._source_dd = Gtk.DropDown.new(
            Gtk.StringList.new(source_descs or ["(No input devices)"]), None,
        )
        self._source_dd.set_selected(source_idx)
        self._source_dd.set_size_request(240, -1)
        self._source_dd.connect("notify::selected", self._on_source_selected)
        page.append(self.make_setting_row("Input device", "", self._source_dd))

        self._in_vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._in_vol.set_value(self._get_volume("@DEFAULT_SOURCE@", is_source=True))
        self._in_vol.set_size_request(200, -1)
        self._in_vol.set_draw_value(True)
        self._in_vol.set_format_value_func(lambda _s, v: f"{v:.0f}%")
        self._in_vol.connect("value-changed", self._on_in_vol_changed)
        page.append(self.make_setting_row("Volume", "", self._in_vol))

        self._in_mute = Gtk.Switch()
        self._in_mute.set_active(self._get_mute("@DEFAULT_SOURCE@", is_source=True))
        self._in_mute.connect("state-set", self._on_in_mute_set)
        page.append(self.make_setting_row("Mute", "", self._in_mute))

        # Start PulseAudio event subscriber and wire up live updates
        self._pa = PulseAudioSubscriber(self.event_bus)
        self.event_bus.subscribe("audio-changed", self._on_audio_changed)
        page.connect("unmap", lambda _: self._pa.stop() if self._pa else None)

        return page

    # -- Signal handlers (user interaction) --

    def _on_sink_selected(self, dropdown, _pspec):
        if self._updating:
            return
        idx = dropdown.get_selected()
        if self._sink_names and idx < len(self._sink_names):
            try:
                subprocess.run(
                    ["pactl", "set-default-sink", self._sink_names[idx]],
                    capture_output=True, timeout=5,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass

    def _on_out_vol_changed(self, scale):
        if self._updating:
            return
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(scale.get_value())}%"],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    def _on_out_mute_set(self, _switch, state):
        if self._updating:
            return False
        try:
            subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if state else "0"],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass
        return False

    def _on_source_selected(self, dropdown, _pspec):
        if self._updating:
            return
        idx = dropdown.get_selected()
        if self._source_names and idx < len(self._source_names):
            try:
                subprocess.run(
                    ["pactl", "set-default-source", self._source_names[idx]],
                    capture_output=True, timeout=5,
                )
            except (subprocess.TimeoutExpired, OSError):
                pass

    def _on_in_vol_changed(self, scale):
        if self._updating:
            return
        try:
            subprocess.run(
                ["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{int(scale.get_value())}%"],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    def _on_in_mute_set(self, _switch, state):
        if self._updating:
            return False
        try:
            subprocess.run(
                ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "1" if state else "0"],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass
        return False

    # -- Live event handling --

    def _on_audio_changed(self, _data):
        self._refresh()

    def _refresh(self):
        self._updating = True
        try:
            # Re-read sinks
            sinks = self._get_sinks()
            new_sink_names = [n for n, _ in sinks]
            sink_descs = [d for _, d in sinks]

            # Update sink dropdown if device list changed
            if new_sink_names != self._sink_names:
                self._sink_names = new_sink_names
                model = Gtk.StringList.new(sink_descs or ["(No output devices)"])
                self._sink_dd.set_model(model)

            # Select current default sink
            default_sink = self._get_default_sink()
            try:
                sink_idx = self._sink_names.index(default_sink)
            except ValueError:
                sink_idx = 0
            if self._sink_names:
                self._sink_dd.set_selected(sink_idx)

            # Update output volume and mute
            self._out_vol.set_value(self._get_volume("@DEFAULT_SINK@"))
            self._out_mute.set_active(self._get_mute("@DEFAULT_SINK@"))

            # Re-read sources
            sources = self._get_sources()
            new_source_names = [n for n, _ in sources]
            source_descs = [d for _, d in sources]

            # Update source dropdown if device list changed
            if new_source_names != self._source_names:
                self._source_names = new_source_names
                model = Gtk.StringList.new(source_descs or ["(No input devices)"])
                self._source_dd.set_model(model)

            # Select current default source
            default_source = self._get_default_source()
            try:
                source_idx = self._source_names.index(default_source)
            except ValueError:
                source_idx = 0
            if self._source_names:
                self._source_dd.set_selected(source_idx)

            # Update input volume and mute
            self._in_vol.set_value(self._get_volume("@DEFAULT_SOURCE@", is_source=True))
            self._in_mute.set_active(self._get_mute("@DEFAULT_SOURCE@", is_source=True))
        finally:
            self._updating = False

    # -- Static helpers: read current PulseAudio state --

    @staticmethod
    def _get_sinks():
        try:
            r = subprocess.run(["pactl", "-f", "json", "list", "sinks"],
                               capture_output=True, text=True, timeout=5)
            return [(s["name"], s.get("description", s["name"])) for s in json.loads(r.stdout)]
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            return []

    @staticmethod
    def _get_default_sink():
        try:
            return subprocess.run(["pactl", "get-default-sink"],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    @staticmethod
    def _get_sources():
        try:
            r = subprocess.run(["pactl", "-f", "json", "list", "sources"],
                               capture_output=True, text=True, timeout=5)
            return [(s["name"], s.get("description", s["name"]))
                    for s in json.loads(r.stdout) if ".monitor" not in s["name"]]
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
            return []

    @staticmethod
    def _get_default_source():
        try:
            return subprocess.run(["pactl", "get-default-source"],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    @staticmethod
    def _get_volume(target, is_source=False):
        cmd = "get-source-volume" if is_source else "get-sink-volume"
        try:
            r = subprocess.run(["pactl", cmd, target], capture_output=True, text=True, timeout=5)
            m = re.search(r"(\d+)%", r.stdout)
            return int(m.group(1)) if m else 50
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return 50

    @staticmethod
    def _get_mute(target, is_source=False):
        cmd = "get-source-mute" if is_source else "get-sink-mute"
        try:
            return "yes" in subprocess.run(["pactl", cmd, target],
                                           capture_output=True, text=True, timeout=5).stdout.lower()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
