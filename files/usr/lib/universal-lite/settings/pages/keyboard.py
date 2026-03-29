import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage

LAYOUT_NAMES = {
    "us": "English (US)", "gb": "English (UK)", "de": "German",
    "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
    "ru": "Russian", "jp": "Japanese", "kr": "Korean", "cn": "Chinese",
    "ar": "Arabic", "br": "Portuguese (Brazil)", "ca": "Canadian",
    "dk": "Danish", "fi": "Finnish", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "se": "Swedish", "ch": "Swiss", "tr": "Turkish",
    "ua": "Ukrainian", "in": "Indian", "il": "Hebrew", "th": "Thai",
    "cz": "Czech", "hu": "Hungarian", "ro": "Romanian", "sk": "Slovak",
    "hr": "Croatian", "si": "Slovenian", "bg": "Bulgarian", "gr": "Greek",
    "ir": "Persian", "et": "Amharic", "vn": "Vietnamese",
    "ke": "Swahili (Kenya)", "tz": "Swahili (Tanzania)", "ng": "Nigerian",
}


class KeyboardPage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("Layout", "Keyboard layout"), ("Layout", "Variant"),
            ("Repeat", "Repeat delay"), ("Repeat", "Repeat rate"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Layout"))

        layout_codes = self._get_layouts()
        display_names = [LAYOUT_NAMES.get(c, c) for c in layout_codes]
        current_layout = self.store.get("keyboard_layout", "us")
        try:
            layout_idx = layout_codes.index(current_layout)
        except ValueError:
            layout_idx = 0

        layout_dropdown = Gtk.DropDown.new(Gtk.StringList.new(display_names), None)
        layout_dropdown.set_selected(layout_idx)
        layout_dropdown.set_size_request(240, -1)

        current_variant = self.store.get("keyboard_variant", "")
        variant_codes: list[str] = []

        variant_dropdown = Gtk.DropDown.new(Gtk.StringList.new(["(Default)"]), None)
        variant_dropdown.set_size_request(240, -1)
        variant_row = self.make_setting_row("Variant", "", variant_dropdown)

        def _build_variant_dropdown(layout_code):
            variants = self._get_variants(layout_code)
            variant_codes.clear()
            variant_codes.append("")
            variant_codes.extend(variants)
            variant_dropdown.set_model(Gtk.StringList.new(["(Default)"] + variants))
            variant_row.set_visible(bool(variants))
            try:
                sel = variant_codes.index(current_variant if layout_code == current_layout else "")
            except ValueError:
                sel = 0
            variant_dropdown.set_selected(sel)

        def _on_variant_changed(dd, _pspec):
            idx = dd.get_selected()
            if idx == Gtk.INVALID_LIST_POSITION or not variant_codes:
                return
            code = variant_codes[idx] if idx < len(variant_codes) else ""
            self.store.save_and_apply("keyboard_variant", code)

        variant_dropdown.connect("notify::selected", _on_variant_changed)

        def _on_layout_changed(dd, _pspec):
            idx = dd.get_selected()
            if idx == Gtk.INVALID_LIST_POSITION or idx >= len(layout_codes):
                return
            code = layout_codes[idx]
            self.store.save_dict_and_apply({"keyboard_layout": code, "keyboard_variant": ""})
            _build_variant_dropdown(code)

        layout_dropdown.connect("notify::selected", _on_layout_changed)
        page.append(self.make_setting_row("Keyboard layout", "", layout_dropdown))
        _build_variant_dropdown(current_layout)
        page.append(variant_row)

        # -- Repeat --
        page.append(self.make_group_label("Repeat"))

        delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 150, 1000, 50)
        delay_scale.set_value(self.store.get("keyboard_repeat_delay", 300))
        delay_scale.set_size_request(200, -1)
        delay_scale.set_draw_value(True)
        delay_scale.set_format_value_func(lambda _s, v: f"{v:.0f} ms")
        delay_scale.connect("value-changed", lambda s: self.store.save_debounced(
            "keyboard_repeat_delay", int(s.get_value())))
        page.append(self.make_setting_row("Repeat delay", "", delay_scale))

        rate_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 80, 5)
        rate_scale.set_value(self.store.get("keyboard_repeat_rate", 40))
        rate_scale.set_size_request(200, -1)
        rate_scale.set_draw_value(True)
        rate_scale.set_format_value_func(lambda _s, v: f"{v:.0f}/s")
        rate_scale.connect("value-changed", lambda s: self.store.save_debounced(
            "keyboard_repeat_rate", int(s.get_value())))
        page.append(self.make_setting_row("Repeat rate", "", rate_scale))
        return page

    @staticmethod
    def _get_layouts():
        try:
            r = subprocess.run(["localectl", "list-x11-keymap-layouts"], capture_output=True, text=True)
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except FileNotFoundError:
            return ["us"]

    @staticmethod
    def _get_variants(layout):
        try:
            r = subprocess.run(["localectl", "list-x11-keymap-variants", layout], capture_output=True, text=True)
            return [v.strip() for v in r.stdout.splitlines() if v.strip()]
        except FileNotFoundError:
            return []
