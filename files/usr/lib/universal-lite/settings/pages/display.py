import re
import subprocess
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage

SCALE_OPTIONS = ["75%", "100%", "125%", "150%", "175%", "200%", "225%", "250%"]
SCALE_VALUES = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]

SCHEDULE_LABELS = [_("Sunset to Sunrise"), _("Custom")]
SCHEDULE_VALUES = ["sunset-sunrise", "custom"]


class DisplayPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._scale_buttons: list[Gtk.ToggleButton] = []
        self._revert_timer_id: int | None = None
        self._revert_seconds: int = 15
        self._revert_dialog: Gtk.Window | None = None
        self._res_revert_timer_id: int | None = None
        self._res_revert_seconds: int = 15
        self._res_revert_dialog: Gtk.Window | None = None

    @property
    def search_keywords(self):
        return [
            (_("Display Scale"), _("Scale")),
            (_("Display Scale"), _("Resolution")),
            (_("Resolution & Refresh Rate"), _("Resolution")),
            (_("Resolution & Refresh Rate"), _("Refresh")),
            (_("Night Light"), _("Night Light")),
            (_("Night Light"), _("Temperature")),
            (_("Night Light"), _("Blue light")),
        ]

    def build(self):
        page = self.make_page_box()

        # ── Display Scale (existing) ──
        options = [(str(v), label) for v, label in zip(SCALE_VALUES, SCALE_OPTIONS)]
        active = str(self.store.get("scale", 1.0))
        cards_box = self.make_toggle_cards(
            options, active, lambda v: self._apply_scale(float(v)),
        )
        child = cards_box.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.ToggleButton):
                self._scale_buttons.append(child)
            child = child.get_next_sibling()
        page.append(self.make_group(_("Display Scale"), [cards_box]))

        # ── Resolution & Refresh Rate ──
        displays = self._get_displays()
        res_children: list[Gtk.Widget] = []
        if not displays:
            no_display = Gtk.Label(label=_("No displays detected"), xalign=0)
            no_display.add_css_class("setting-subtitle")
            res_children.append(no_display)
        else:
            for name, current, modes in displays:
                if not modes:
                    continue
                dd = Gtk.DropDown.new(
                    Gtk.StringList.new(modes), None,
                )
                if current and current in modes:
                    dd.set_selected(modes.index(current))
                dd.set_size_request(240, -1)
                dd.connect(
                    "notify::selected",
                    self._on_resolution_changed, name, modes, current,
                )
                res_children.append(self.make_setting_row(name, _("Resolution and refresh rate"), dd))
        page.append(self.make_group(_("Resolution & Refresh Rate"), res_children))

        # ── Night Light ──

        # Enable toggle
        nl_toggle = Gtk.Switch()
        nl_toggle.set_active(self.store.get("night_light_enabled", False))

        def _on_nl_toggle(_, state):
            self.store.save_and_apply("night_light_enabled", state)
            return False

        nl_toggle.connect("state-set", _on_nl_toggle)

        # Temperature slider
        temp_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 3500, 6500, 100,
        )
        temp_scale.set_value(self.store.get("night_light_temp", 4500))
        temp_scale.set_size_request(200, -1)
        temp_scale.set_draw_value(True)
        temp_scale.set_format_value_func(lambda _s, v: f"{v:.0f}K")
        temp_scale.connect(
            "value-changed",
            lambda s: self.store.save_debounced("night_light_temp", int(s.get_value())),
        )

        # Schedule dropdown
        schedule_dd = Gtk.DropDown.new_from_strings(list(SCHEDULE_LABELS))
        current_schedule = self.store.get("night_light_schedule", "sunset-sunrise")
        try:
            schedule_dd.set_selected(SCHEDULE_VALUES.index(current_schedule))
        except ValueError:
            schedule_dd.set_selected(0)
        schedule_dd.set_size_request(200, -1)

        # Custom time entries (start / end)
        custom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        def _validate_and_save_time(entry, key):
            text = entry.get_text().strip()
            if re.fullmatch(r"[0-2]\d:[0-5]\d", text):
                h, m = text.split(":")
                if int(h) < 24:
                    entry.remove_css_class("error")
                    self.store.save_and_apply(key, text)
                    return
            entry.add_css_class("error")

        start_entry = Gtk.Entry()
        start_entry.set_text(self.store.get("night_light_start", "20:00"))
        start_entry.set_placeholder_text(_("HH:MM"))
        start_entry.set_max_width_chars(5)
        start_entry.connect(
            "activate",
            lambda e: _validate_and_save_time(e, "night_light_start"),
        )
        custom_box.append(self.make_setting_row(_("Start time"), "", start_entry))

        end_entry = Gtk.Entry()
        end_entry.set_text(self.store.get("night_light_end", "06:00"))
        end_entry.set_placeholder_text(_("HH:MM"))
        end_entry.set_max_width_chars(5)
        end_entry.connect(
            "activate",
            lambda e: _validate_and_save_time(e, "night_light_end"),
        )
        custom_box.append(self.make_setting_row(_("End time"), "", end_entry))

        custom_box.set_visible(current_schedule == "custom")

        def _on_schedule_changed(dd, _param):
            idx = dd.get_selected()
            value = SCHEDULE_VALUES[idx]
            self.store.save_and_apply("night_light_schedule", value)
            custom_box.set_visible(value == "custom")

        schedule_dd.connect("notify::selected", _on_schedule_changed)

        page.append(self.make_group(_("Night Light"), [
            self.make_setting_row(_("Night Light"), _("Reduce blue light to help with sleep"), nl_toggle),
            self.make_setting_row(_("Temperature"), _("3500K (warm) to 6500K (cool)"), temp_scale),
            self.make_setting_row(_("Schedule"), "", schedule_dd),
            custom_box,
        ]))

        # ── Advanced ──
        adv_btn = Gtk.Button(label=_("Open wdisplays"))
        adv_btn.set_halign(Gtk.Align.START)
        adv_btn.connect("clicked", lambda _: subprocess.Popen(
            ["wdisplays"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        page.append(self.make_group(_("Advanced"), [
            self.make_setting_row(
                _("Advanced display settings"), _("Arrange and configure displays visually"), adv_btn),
        ]))

        page.connect("unmap", lambda _: self._cleanup_dialogs())
        return page

    def _cleanup_dialogs(self) -> None:
        """Clean up revert dialogs and timers when page is unmapped."""
        if hasattr(self, "_revert_timer_id") and self._revert_timer_id:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = 0
        if hasattr(self, "_revert_dialog") and self._revert_dialog:
            self._revert_dialog.close()
            self._revert_dialog = None
        if hasattr(self, "_res_revert_timer_id") and self._res_revert_timer_id:
            GLib.source_remove(self._res_revert_timer_id)
            self._res_revert_timer_id = 0
        if hasattr(self, "_res_revert_dialog") and self._res_revert_dialog:
            self._res_revert_dialog.close()
            self._res_revert_dialog = None

    # ── Display Scale helpers ──

    def _apply_scale(self, new_scale):
        if self._revert_timer_id is not None:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = None
        if self._revert_dialog is not None:
            self._revert_dialog.destroy()
            self._revert_dialog = None
        old_scale = self.store.get("scale", 1.0)
        self._set_scale(new_scale)
        self._show_revert_dialog(old_scale, new_scale)

    def _set_scale(self, scale):
        try:
            result = subprocess.run(
                ["wlr-randr"], capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                output_name = line.split()[0]
                try:
                    subprocess.run(
                        ["wlr-randr", "--output", output_name, "--scale", str(scale)],
                        check=False, timeout=5,
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass

    def _show_revert_dialog(self, old_scale, new_scale):
        dialog = Gtk.Window(title=_("Confirm Scale"), modal=True)
        if self._scale_buttons:
            dialog.set_transient_for(self._scale_buttons[0].get_root())
        dialog.set_default_size(400, 150)
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self._revert_seconds = 15
        label = Gtk.Label(label=_("Keep this display scale?\nReverting in {seconds}s...").format(seconds=self._revert_seconds))
        label.set_wrap(True)
        box.append(label)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        revert_btn = Gtk.Button(label=_("Revert"))
        revert_btn.connect("clicked", lambda _: self._revert(dialog, old_scale))
        btn_box.append(revert_btn)
        keep_btn = Gtk.Button(label=_("Keep"))
        keep_btn.add_css_class("suggested-action")
        keep_btn.connect("clicked", lambda _: self._keep(dialog, new_scale))
        keep_btn.set_receives_default(True)
        dialog.set_default_widget(keep_btn)
        btn_box.append(keep_btn)
        box.append(btn_box)
        dialog.set_child(box)
        self._revert_dialog = dialog
        self._revert_timer_id = GLib.timeout_add_seconds(
            1, self._tick_revert, label, dialog, old_scale,
        )
        dialog.connect("close-request", lambda _: self._revert(dialog, old_scale) or True)
        BasePage.enable_escape_close(dialog)
        dialog.present()

    def _tick_revert(self, label, dialog, old_scale):
        self._revert_seconds -= 1
        if self._revert_seconds <= 0:
            self._revert(dialog, old_scale)
            return GLib.SOURCE_REMOVE
        label.set_text(_("Keep this display scale?\nReverting in {seconds}s...").format(seconds=self._revert_seconds))
        return GLib.SOURCE_CONTINUE

    def _revert(self, dialog, old_scale):
        if self._revert_timer_id is not None:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = None
        self._revert_dialog = None
        self._set_scale(old_scale)
        self._sync_buttons(old_scale)
        dialog.destroy()

    def _keep(self, dialog, new_scale):
        if self._revert_timer_id is not None:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = None
        self._revert_dialog = None
        self.store.save_and_apply("scale", new_scale)
        self._sync_buttons(new_scale)
        dialog.destroy()

    def _sync_buttons(self, scale):
        scale_str = str(scale)
        value_to_label = {str(v): lbl for v, lbl in zip(SCALE_VALUES, SCALE_OPTIONS)}
        target_label = value_to_label.get(scale_str, "")
        for btn in self._scale_buttons:
            active = btn.get_label() == target_label
            if btn.get_active() != active:
                btn.set_active(active)

    # ── Resolution & Refresh Rate helpers ──

    @staticmethod
    def _get_displays():
        try:
            result = subprocess.run(
                ["wlr-randr"], capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        displays = []
        name = None
        current = None
        modes = []
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                if name:
                    displays.append((name, current, modes))
                name = line.split()[0]
                current = None
                modes = []
            else:
                m = re.search(r"(\d+x\d+)\s+px,\s+([\d.]+)\s+Hz", line)
                if m:
                    mode = f"{m.group(1)}@{m.group(2)}Hz"
                    if mode not in modes:
                        modes.append(mode)
                    if "current" in line.lower():
                        current = mode
        if name:
            displays.append((name, current, modes))
        return displays

    def _on_resolution_changed(self, dd, _param, output_name, modes, old_mode):
        idx = dd.get_selected()
        if idx < 0 or idx >= len(modes):
            return
        new_mode = modes[idx]
        if new_mode == old_mode:
            return
        if self._res_revert_timer_id is not None:
            GLib.source_remove(self._res_revert_timer_id)
            self._res_revert_timer_id = None
        if self._res_revert_dialog is not None:
            self._res_revert_dialog.destroy()
            self._res_revert_dialog = None
        self._apply_resolution(output_name, new_mode)
        self._show_res_revert_dialog(dd, output_name, modes, old_mode, new_mode)

    @staticmethod
    def _apply_resolution(output_name, mode_str):
        # mode_str: "1920x1080@60.0Hz" — strip "Hz" for wlr-randr's --mode flag
        mode_arg = mode_str.replace("Hz", "")
        try:
            subprocess.run(
                ["wlr-randr", "--output", output_name, "--mode", mode_arg],
                check=False, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _show_res_revert_dialog(self, dropdown, output_name, modes, old_mode, new_mode):
        dialog = Gtk.Window(title=_("Confirm Resolution"), modal=True)
        dialog.set_transient_for(dropdown.get_root())
        dialog.set_default_size(400, 150)
        dialog.set_resizable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self._res_revert_seconds = 15
        label = Gtk.Label(
            label=_("Keep this resolution?\nReverting in {seconds}s...").format(seconds=self._res_revert_seconds),
        )
        label.set_wrap(True)
        box.append(label)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        revert_btn = Gtk.Button(label=_("Revert"))
        revert_btn.connect(
            "clicked",
            lambda _: self._res_revert(dialog, dropdown, output_name, modes, old_mode),
        )
        btn_box.append(revert_btn)
        keep_btn = Gtk.Button(label=_("Keep"))
        keep_btn.add_css_class("suggested-action")
        keep_btn.connect("clicked", lambda _: self._res_keep(dialog, output_name, new_mode))
        keep_btn.set_receives_default(True)
        dialog.set_default_widget(keep_btn)
        btn_box.append(keep_btn)
        box.append(btn_box)
        dialog.set_child(box)
        self._res_revert_dialog = dialog
        self._res_revert_timer_id = GLib.timeout_add_seconds(
            1, self._tick_res_revert, label, dialog, dropdown, output_name, modes, old_mode,
        )
        dialog.connect(
            "close-request",
            lambda _: self._res_revert(dialog, dropdown, output_name, modes, old_mode) or True,
        )
        BasePage.enable_escape_close(dialog)
        dialog.present()

    def _tick_res_revert(self, label, dialog, dropdown, output_name, modes, old_mode):
        self._res_revert_seconds -= 1
        if self._res_revert_seconds <= 0:
            self._res_revert(dialog, dropdown, output_name, modes, old_mode)
            return GLib.SOURCE_REMOVE
        label.set_text(_("Keep this resolution?\nReverting in {seconds}s...").format(seconds=self._res_revert_seconds))
        return GLib.SOURCE_CONTINUE

    def _res_revert(self, dialog, dropdown, output_name, modes, old_mode):
        if self._res_revert_timer_id is not None:
            GLib.source_remove(self._res_revert_timer_id)
            self._res_revert_timer_id = None
        self._res_revert_dialog = None
        self._apply_resolution(output_name, old_mode)
        if old_mode in modes:
            dropdown.set_selected(modes.index(old_mode))
        dialog.destroy()

    def _res_keep(self, dialog, output_name, new_mode):
        if self._res_revert_timer_id is not None:
            GLib.source_remove(self._res_revert_timer_id)
            self._res_revert_timer_id = None
        self._res_revert_dialog = None
        self.store.save_and_apply(f"resolution_{output_name}", new_mode)
        dialog.destroy()
