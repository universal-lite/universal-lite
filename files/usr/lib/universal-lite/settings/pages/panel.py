import copy

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage

MODULE_NAMES = {
    "custom/launcher": "Apps", "wlr/taskbar": "Window list",
    "pulseaudio": "Volume", "backlight": "Brightness", "battery": "Battery",
    "clock": "Clock", "custom/power": "Power", "tray": "System tray",
}
DEFAULT_LAYOUT = {
    "start": ["custom/launcher"],
    "center": ["wlr/taskbar"],
    "end": ["pulseaudio", "backlight", "battery", "clock", "custom/power", "tray"],
}
HORIZONTAL_LABELS = {"start": "Left", "center": "Center", "end": "Right"}
VERTICAL_LABELS = {"start": "Top", "center": "Center", "end": "Bottom"}
SECTION_ORDER = ["start", "center", "end"]


class PanelPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._layout_data: dict = {}
        self._section_boxes: dict = {}
        self._pinned_data: list = []
        self._pinned_list: Gtk.ListBox | None = None

    @property
    def search_keywords(self):
        return [
            ("Position", "Panel"), ("Density", "Compact"),
            ("Module Layout", "Modules"), ("Pinned Apps", "Pinned"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Position"))
        page.append(self.make_toggle_cards(
            [("bottom", "Bottom"), ("top", "Top"), ("left", "Left"), ("right", "Right")],
            self.store.get("edge", "bottom"),
            lambda v: self.store.save_and_apply("edge", v),
        ))
        page.append(self.make_group_label("Density"))
        page.append(self.make_toggle_cards(
            [("normal", "Normal"), ("compact", "Compact")],
            self.store.get("density", "normal"),
            lambda v: self.store.save_and_apply("density", v),
        ))
        page.append(self.make_group_label("Module Layout"))
        page.append(self._build_module_layout())
        page.append(self.make_group_label("Pinned Apps"))
        page.append(self._build_pinned_apps())
        reset_btn = Gtk.Button(label="Reset layout to defaults")
        reset_btn.set_halign(Gtk.Align.START)
        reset_btn.connect("clicked", lambda _: self._reset_layout())
        page.append(reset_btn)
        return page

    # -- Module layout --

    def _build_module_layout(self):
        self._layout_data = self._load_layout()
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._section_boxes = {}
        edge = self.store.get("edge", "bottom")
        labels = HORIZONTAL_LABELS if edge in ("top", "bottom") else VERTICAL_LABELS
        for section in SECTION_ORDER:
            section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            section_box.set_hexpand(True)
            header = Gtk.Label(label=labels[section], xalign=0)
            header.add_css_class("group-title")
            section_box.append(header)
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            self._section_boxes[section] = listbox
            section_box.append(listbox)
            container.append(section_box)
        self._refresh_module_lists()
        return container

    def _load_layout(self):
        saved = self.store.get("layout")
        if isinstance(saved, dict) and all(k in saved for k in SECTION_ORDER):
            return {k: list(saved[k]) for k in SECTION_ORDER}
        return copy.deepcopy(DEFAULT_LAYOUT)

    def _refresh_module_lists(self):
        for section in SECTION_ORDER:
            listbox = self._section_boxes[section]
            while (child := listbox.get_row_at_index(0)) is not None:
                listbox.remove(child)
            for mod_key in self._layout_data.get(section, []):
                listbox.append(self._build_module_row(mod_key, section))

    def _build_module_row(self, mod_key, section):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        label = Gtk.Label(label=MODULE_NAMES.get(mod_key, mod_key), xalign=0)
        label.set_hexpand(True)
        box.append(label)
        sec_idx = SECTION_ORDER.index(section)
        if sec_idx > 0:
            btn = Gtk.Button(label="\u25C2")
            btn.set_tooltip_text(f"Move to {SECTION_ORDER[sec_idx - 1]}")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) - 1]))
            box.append(btn)
        if sec_idx < len(SECTION_ORDER) - 1:
            btn = Gtk.Button(label="\u25B8")
            btn.set_tooltip_text(f"Move to {SECTION_ORDER[sec_idx + 1]}")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) + 1]))
            box.append(btn)
        row.set_child(box)
        return row

    def _move_module(self, mod_key, from_section, to_section):
        if mod_key in self._layout_data.get(from_section, []):
            self._layout_data[from_section].remove(mod_key)
        self._layout_data.setdefault(to_section, []).append(mod_key)
        self._refresh_module_lists()
        self.store.save_and_apply("layout", self._layout_data)

    # -- Pinned apps --

    def _build_pinned_apps(self):
        self._pinned_data = list(self.store.get("pinned", []))
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._pinned_list = Gtk.ListBox()
        self._pinned_list.set_selection_mode(Gtk.SelectionMode.NONE)
        vbox.append(self._pinned_list)
        add_btn = Gtk.Button(label="Add pinned app")
        add_btn.set_halign(Gtk.Align.START)
        add_btn.set_margin_top(8)
        add_btn.connect("clicked", lambda _: self._show_add_pinned_dialog())
        vbox.append(add_btn)
        self._refresh_pinned_list()
        return vbox

    def _refresh_pinned_list(self):
        if self._pinned_list is None:
            return
        while (child := self._pinned_list.get_row_at_index(0)) is not None:
            self._pinned_list.remove(child)
        for idx, app in enumerate(self._pinned_data):
            self._pinned_list.append(self._build_pinned_row(app, idx))

    def _build_pinned_row(self, app, idx):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        icon = Gtk.Image.new_from_icon_name(app.get("icon", "application-x-executable-symbolic"))
        icon.set_pixel_size(20)
        box.append(icon)
        name_label = Gtk.Label(label=app.get("name", app.get("command", "Unknown")), xalign=0)
        name_label.set_hexpand(True)
        box.append(name_label)
        remove_btn = Gtk.Button(label="Remove")
        remove_btn.connect("clicked", lambda _, i=idx: self._remove_pinned(i))
        box.append(remove_btn)
        row.set_child(box)
        return row

    def _remove_pinned(self, idx):
        if 0 <= idx < len(self._pinned_data):
            self._pinned_data.pop(idx)
            self._refresh_pinned_list()
            self.store.save_and_apply("pinned", self._pinned_data)

    def _show_add_pinned_dialog(self):
        dialog = Gtk.Window(title="Add Pinned App", modal=True)
        dialog.set_default_size(360, 220)
        dialog.set_resizable(False)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        outer.set_margin_top(24)
        outer.set_margin_bottom(24)
        outer.set_margin_start(24)
        outer.set_margin_end(24)
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(12)

        def _entry(row_idx, label_text, placeholder):
            lbl = Gtk.Label(label=label_text, xalign=1)
            entry = Gtk.Entry()
            entry.set_placeholder_text(placeholder)
            entry.set_hexpand(True)
            grid.attach(lbl, 0, row_idx, 1, 1)
            grid.attach(entry, 1, row_idx, 1, 1)
            return entry

        name_entry = _entry(0, "Name:", "e.g. Files")
        cmd_entry = _entry(1, "Command:", "e.g. nautilus")
        icon_entry = _entry(2, "Icon:", "e.g. folder-symbolic")
        outer.append(grid)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: dialog.destroy())
        btn_box.append(cancel_btn)
        add_btn = Gtk.Button(label="Add")
        add_btn.add_css_class("suggested-action")

        def _on_add(_btn):
            name = name_entry.get_text().strip()
            cmd = cmd_entry.get_text().strip()
            icon_name = icon_entry.get_text().strip() or "application-x-executable-symbolic"
            if not name or not cmd:
                return
            self._pinned_data.append({"name": name, "command": cmd, "icon": icon_name})
            self._refresh_pinned_list()
            self.store.save_and_apply("pinned", self._pinned_data)
            dialog.destroy()

        add_btn.connect("clicked", _on_add)
        btn_box.append(add_btn)
        outer.append(btn_box)
        dialog.set_child(outer)
        dialog.present()

    def _reset_layout(self):
        self._layout_data = copy.deepcopy(DEFAULT_LAYOUT)
        self._refresh_module_lists()
        self.store.save_and_apply("layout", self._layout_data)
        self._pinned_data = list(self.store.get("pinned", []))
        self._refresh_pinned_list()
