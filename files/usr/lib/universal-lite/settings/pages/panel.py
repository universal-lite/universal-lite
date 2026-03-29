import copy

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

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

        edge = self.store.get("edge", "bottom")
        is_horizontal = edge in ("top", "bottom")
        sec_idx = SECTION_ORDER.index(section)
        modules = self._layout_data.get(section, [])
        mod_idx = modules.index(mod_key) if mod_key in modules else -1

        # Section-move buttons
        section_prev = "\u25C2" if is_horizontal else "\u25B2"
        section_next = "\u25B8" if is_horizontal else "\u25BC"
        # Reorder buttons (within section)
        reorder_up = "\u25B2" if is_horizontal else "\u25C2"
        reorder_down = "\u25BC" if is_horizontal else "\u25B8"

        if sec_idx > 0:
            btn = Gtk.Button(label=section_prev)
            btn.set_tooltip_text(f"Move to {SECTION_ORDER[sec_idx - 1]}")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) - 1]))
            box.append(btn)
        if sec_idx < len(SECTION_ORDER) - 1:
            btn = Gtk.Button(label=section_next)
            btn.set_tooltip_text(f"Move to {SECTION_ORDER[sec_idx + 1]}")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) + 1]))
            box.append(btn)
        if mod_idx > 0:
            btn = Gtk.Button(label=reorder_up)
            btn.set_tooltip_text("Move up in section")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._reorder_module(k, s, -1))
            box.append(btn)
        if mod_idx < len(modules) - 1:
            btn = Gtk.Button(label=reorder_down)
            btn.set_tooltip_text("Move down in section")
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._reorder_module(k, s, 1))
            box.append(btn)

        row.set_child(box)
        return row

    def _reorder_module(self, mod_key, section, direction):
        modules = self._layout_data.get(section, [])
        if mod_key not in modules:
            return
        idx = modules.index(mod_key)
        new_idx = idx + direction
        if 0 <= new_idx < len(modules):
            modules[idx], modules[new_idx] = modules[new_idx], modules[idx]
            self._refresh_module_lists()
            self.store.save_and_apply("layout", self._layout_data)

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
        dialog.set_transient_for(self._pinned_list.get_root())
        dialog.set_default_size(400, 500)
        dialog.set_resizable(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)

        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text("Search apps\u2026")
        outer.append(search_entry)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        app_list = Gtk.ListBox()
        app_list.set_selection_mode(Gtk.SelectionMode.NONE)

        apps = [a for a in Gio.AppInfo.get_all() if a.should_show()]
        apps.sort(key=lambda a: a.get_display_name().lower())

        for app in apps:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_top(4)
            row_box.set_margin_bottom(4)
            row_box.set_margin_start(4)
            row_box.set_margin_end(4)

            icon_info = app.get_icon()
            if icon_info:
                icon_widget = Gtk.Image.new_from_gicon(icon_info)
            else:
                icon_widget = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
            icon_widget.set_pixel_size(24)
            row_box.append(icon_widget)

            name_label = Gtk.Label(label=app.get_display_name(), xalign=0)
            name_label.set_hexpand(True)
            row_box.append(name_label)

            add_btn = Gtk.Button(label="Add")
            add_btn.connect("clicked", lambda _, a=app: self._add_app_from_info(a, dialog))
            row_box.append(add_btn)

            row.set_child(row_box)
            row._app_name = app.get_display_name().lower()
            app_list.append(row)

        def _filter_func(row):
            query = search_entry.get_text().lower()
            if not query:
                return True
            return query in row._app_name

        app_list.set_filter_func(_filter_func)
        search_entry.connect("search-changed", lambda _: app_list.invalidate_filter())

        scrolled.set_child(app_list)
        outer.append(scrolled)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.set_halign(Gtk.Align.END)
        cancel_btn.set_margin_top(4)
        cancel_btn.connect("clicked", lambda _: dialog.destroy())
        outer.append(cancel_btn)

        dialog.set_child(outer)
        dialog.present()

    def _add_app_from_info(self, app_info, dialog):
        name = app_info.get_display_name()
        cmd = app_info.get_commandline() or ""
        icon_gicon = app_info.get_icon()
        icon = icon_gicon.to_string() if icon_gicon else "application-x-executable-symbolic"
        self._pinned_data.append({"name": name, "command": cmd, "icon": icon})
        self._refresh_pinned_list()
        self.store.save_and_apply("pinned", self._pinned_data)
        dialog.destroy()

    def _reset_layout(self):
        self._layout_data = copy.deepcopy(DEFAULT_LAYOUT)
        self._refresh_module_lists()
        self.store.save_and_apply("layout", self._layout_data)
        self._pinned_data = list(self.store.get("pinned", []))
        self._refresh_pinned_list()
