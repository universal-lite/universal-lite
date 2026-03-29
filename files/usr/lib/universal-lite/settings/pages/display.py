import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from ..base import BasePage

SCALE_OPTIONS = ["75%", "100%", "125%", "150%", "175%", "200%", "225%", "250%"]
SCALE_VALUES = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]


class DisplayPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._scale_buttons: list[Gtk.ToggleButton] = []
        self._revert_timer_id: int | None = None
        self._revert_seconds: int = 15

    @property
    def search_keywords(self):
        return [("Display Scale", "Scale"), ("Display Scale", "Resolution")]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Display Scale"))

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
        page.append(cards_box)
        return page

    def _apply_scale(self, new_scale):
        old_scale = self.store.get("scale", 1.0)
        self._set_scale(new_scale)
        self._show_revert_dialog(old_scale, new_scale)

    def _set_scale(self, scale):
        try:
            result = subprocess.run(["wlr-randr"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if line and not line[0].isspace():
                    output_name = line.split()[0]
                    subprocess.run(
                        ["wlr-randr", "--output", output_name, "--scale", str(scale)],
                        check=False,
                    )
        except FileNotFoundError:
            pass

    def _show_revert_dialog(self, old_scale, new_scale):
        dialog = Gtk.Window(title="Confirm Scale", modal=True)
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
        label = Gtk.Label(label=f"Keep this display scale?\nReverting in {self._revert_seconds}s...")
        label.set_wrap(True)
        box.append(label)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        revert_btn = Gtk.Button(label="Revert")
        revert_btn.connect("clicked", lambda _: self._revert(dialog, old_scale))
        btn_box.append(revert_btn)
        keep_btn = Gtk.Button(label="Keep")
        keep_btn.add_css_class("suggested-action")
        keep_btn.connect("clicked", lambda _: self._keep(dialog, new_scale))
        btn_box.append(keep_btn)
        box.append(btn_box)
        dialog.set_child(box)
        self._revert_timer_id = GLib.timeout_add_seconds(
            1, self._tick_revert, label, dialog, old_scale,
        )
        dialog.connect("close-request", lambda _: self._revert(dialog, old_scale) or True)
        dialog.present()

    def _tick_revert(self, label, dialog, old_scale):
        self._revert_seconds -= 1
        if self._revert_seconds <= 0:
            self._revert(dialog, old_scale)
            return GLib.SOURCE_REMOVE
        label.set_text(f"Keep this display scale?\nReverting in {self._revert_seconds}s...")
        return GLib.SOURCE_CONTINUE

    def _revert(self, dialog, old_scale):
        if self._revert_timer_id is not None:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = None
        self._set_scale(old_scale)
        self._sync_buttons(old_scale)
        dialog.destroy()

    def _keep(self, dialog, new_scale):
        if self._revert_timer_id is not None:
            GLib.source_remove(self._revert_timer_id)
            self._revert_timer_id = None
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
