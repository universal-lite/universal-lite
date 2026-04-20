import copy
import json
import re
from gettext import gettext as _
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, Gtk

from ..base import BasePage

MODULE_NAMES = {
    "custom/launcher": _("Apps"), "wlr/taskbar": _("Window list"),
    "pulseaudio": _("Volume"), "backlight": _("Brightness"), "battery": _("Battery"),
    "clock": _("Clock"), "tray": _("System tray"),
}

_DEFAULTS_PATH = Path("/usr/share/universal-lite/defaults/settings.json")

def _load_default_layout():
    try:
        data = json.loads(_DEFAULTS_PATH.read_text(encoding="utf-8"))
        layout = data.get("layout")
        if isinstance(layout, dict) and all(
            k in layout and isinstance(layout[k], list) for k in ("start", "center", "end")
        ):
            return layout
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return {
        "start": ["custom/launcher"],
        "center": ["wlr/taskbar"],
        "end": ["pulseaudio", "backlight", "battery", "clock", "tray"],
    }

DEFAULT_LAYOUT = _load_default_layout()
HORIZONTAL_LABELS = {"start": _("Left"), "center": _("Center"), "end": _("Right")}
VERTICAL_LABELS = {"start": _("Top"), "center": _("Center"), "end": _("Bottom")}
SECTION_ORDER = ["start", "center", "end"]

EDGE_OPTIONS: list[tuple[str, str]] = [
    ("bottom", _("Bottom")),
    ("top", _("Top")),
    ("left", _("Left")),
    ("right", _("Right")),
]

DENSITY_OPTIONS: list[tuple[str, str]] = [
    ("normal", _("Normal")),
    ("compact", _("Compact")),
]


class PanelPage(BasePage, Adw.PreferencesPage):
    """Panel position, density, twilight, module layout, and pinned apps.

    Returns an AdwNavigationView from build() so the Add Pinned App
    picker can push a sub-page over the top-level preferences content.
    The module-layout editor is kept as a custom 3-column HBox (arrow
    buttons move modules between sections and reorder within a section)
    wrapped in an AdwActionRow suffix — the appearance.py pattern.
    """

    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)
        self._layout_data: dict = {}
        self._section_boxes: dict = {}
        self._section_labels: dict = {}
        self._pinned_data: list = []
        self._pinned_group: Adw.PreferencesGroup | None = None
        self._pinned_rows: list[Adw.ActionRow] = []
        self._nav: Adw.NavigationView | None = None

    @property
    def search_keywords(self):
        return [
            (_("Position"), _("Panel")), (_("Density"), _("Compact")),
            (_("Twilight"), _("Invert")),
            (_("Module Layout"), _("Modules")), (_("Pinned Apps"), _("Pinned")),
        ]

    # -- build ----------------------------------------------------------

    def build(self):
        self.add(self._build_position_group())
        self.add(self._build_density_group())
        self.add(self._build_twilight_group())
        self.add(self._build_module_layout_group())
        self.add(self._build_pinned_apps_group())

        # Tear down event-bus subscriptions on unmap. Call on self
        # (the PreferencesPage), not on the nav wrapper.
        self.setup_cleanup(self)

        # Wrap the preferences page in a NavigationView so the Add
        # Pinned App picker can push a sub-page. Back button + Escape
        # are handled natively by AdwNavigationView.
        self._nav = Adw.NavigationView()
        root_page = Adw.NavigationPage()
        root_page.set_title(_("Panel"))
        root_page.set_child(self)
        self._nav.add(root_page)
        return self._nav

    # -- Position / Density / Twilight ---------------------------------

    def _build_position_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Position"))

        row = Adw.ComboRow()
        row.set_title(_("Panel position"))

        labels = [label for _v, label in EDGE_OPTIONS]
        values = [v for v, _label in EDGE_OPTIONS]
        row.set_model(Gtk.StringList.new(labels))

        current = self.store.get("edge", "bottom")
        row.set_selected(values.index(current) if current in values else 0)

        def _on_selected(r: Adw.ComboRow, _pspec) -> None:
            idx = r.get_selected()
            if 0 <= idx < len(values):
                self._on_edge_changed(values[idx])

        row.connect("notify::selected", _on_selected)
        group.add(row)
        return group

    def _build_density_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Density"))

        row = Adw.ComboRow()
        row.set_title(_("Panel density"))

        labels = [label for _v, label in DENSITY_OPTIONS]
        values = [v for v, _label in DENSITY_OPTIONS]
        row.set_model(Gtk.StringList.new(labels))

        current = self.store.get("density", "normal")
        row.set_selected(values.index(current) if current in values else 0)

        def _on_selected(r: Adw.ComboRow, _pspec) -> None:
            idx = r.get_selected()
            if 0 <= idx < len(values):
                self.store.save_and_apply("density", values[idx])

        row.connect("notify::selected", _on_selected)
        group.add(row)
        return group

    def _build_twilight_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Twilight"))

        row = Adw.SwitchRow()
        row.set_title(_("Twilight"))
        row.set_subtitle(_("Invert panel colors from the system theme"))
        row.set_active(self.store.get("panel_twilight", False))

        def _on_active(r: Adw.SwitchRow, _pspec) -> None:
            self.store.save_and_apply("panel_twilight", r.get_active())

        row.connect("notify::active", _on_active)
        group.add(row)
        return group

    # -- Module layout -------------------------------------------------

    def _build_module_layout_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        group.set_title(_("Module Layout"))

        # Custom 3-column editor wrapped in an AdwActionRow suffix —
        # same pattern as appearance.py's wallpaper grid. The row is
        # non-activatable so clicks don't steal focus from the arrow
        # buttons.
        editor_row = Adw.ActionRow()
        editor_row.set_activatable(False)
        editor_row.add_suffix(self._build_module_layout())
        group.add(editor_row)

        # Trailing reset row, destructive-action button in the suffix.
        reset_row = Adw.ActionRow()
        reset_row.set_title(_("Reset layout to defaults"))
        reset_row.set_activatable(False)
        reset_btn = Gtk.Button(label=_("Reset"))
        reset_btn.add_css_class("destructive-action")
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.connect("clicked", lambda _b: self._reset_layout())
        reset_row.add_suffix(reset_btn)
        group.add(reset_row)

        return group

    def _on_edge_changed(self, edge):
        self.store.save_and_apply("edge", edge)
        self._update_section_labels()
        self._refresh_module_lists()

    def _update_section_labels(self):
        edge = self.store.get("edge", "bottom")
        labels = HORIZONTAL_LABELS if edge in ("top", "bottom") else VERTICAL_LABELS
        for section, widget in self._section_labels.items():
            widget.set_label(labels[section])

    def _build_module_layout(self):
        self._layout_data = self._load_layout()
        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        inner.set_hexpand(True)
        self._section_boxes = {}
        self._section_labels = {}
        edge = self.store.get("edge", "bottom")
        labels = HORIZONTAL_LABELS if edge in ("top", "bottom") else VERTICAL_LABELS
        for section in SECTION_ORDER:
            section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            section_box.set_hexpand(True)
            header = Gtk.Label(label=labels[section], xalign=0)
            header.add_css_class("group-title")
            self._section_labels[section] = header
            section_box.append(header)
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            self._section_boxes[section] = listbox
            section_box.append(listbox)
            inner.append(section_box)
        self._refresh_module_lists()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scrolled.set_hexpand(True)
        scrolled.set_child(inner)
        return scrolled

    def _load_layout(self):
        saved = self.store.get("layout")
        if (
            isinstance(saved, dict)
            and all(k in saved and isinstance(saved[k], list) for k in SECTION_ORDER)
        ):
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
            btn.set_tooltip_text(_("Move to {section}").format(section=SECTION_ORDER[sec_idx - 1]))
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) - 1]))
            box.append(btn)
        if sec_idx < len(SECTION_ORDER) - 1:
            btn = Gtk.Button(label=section_next)
            btn.set_tooltip_text(_("Move to {section}").format(section=SECTION_ORDER[sec_idx + 1]))
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._move_module(
                k, s, SECTION_ORDER[SECTION_ORDER.index(s) + 1]))
            box.append(btn)
        if mod_idx > 0:
            btn = Gtk.Button(label=reorder_up)
            btn.set_tooltip_text(_("Move up in section"))
            btn.connect("clicked", lambda _, k=mod_key, s=section: self._reorder_module(k, s, -1))
            box.append(btn)
        if mod_idx < len(modules) - 1:
            btn = Gtk.Button(label=reorder_down)
            btn.set_tooltip_text(_("Move down in section"))
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

    def _reset_layout(self):
        self._layout_data = copy.deepcopy(DEFAULT_LAYOUT)
        self._refresh_module_lists()
        self.store.save_and_apply("layout", self._layout_data)
        # Pinned apps are not affected by layout reset

    # -- Pinned apps ---------------------------------------------------

    def _build_pinned_apps_group(self) -> Adw.PreferencesGroup:
        raw = self.store.get("pinned", [])
        self._pinned_data = list(raw) if isinstance(raw, list) else []

        group = Adw.PreferencesGroup()
        group.set_title(_("Pinned Apps"))

        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.set_tooltip_text(_("Add pinned app"))
        add_btn.connect("clicked", lambda _b: self._push_add_pinned_page())
        group.set_header_suffix(add_btn)

        self._pinned_group = group
        self._refresh_pinned_list()
        return group

    def _refresh_pinned_list(self):
        group = self._pinned_group
        if group is None:
            return

        # Remove existing pinned rows. Only our cached rows so future
        # siblings (group description etc.) aren't touched.
        for row in self._pinned_rows:
            group.remove(row)
        self._pinned_rows = []

        if not self._pinned_data:
            group.set_description(_("No pinned apps"))
            return
        group.set_description("")

        for idx, app in enumerate(self._pinned_data):
            row = self._build_pinned_row(app, idx)
            group.add(row)
            self._pinned_rows.append(row)

    def _build_pinned_row(self, app, idx):
        row = Adw.ActionRow()
        row.set_title(app.get("name", app.get("command", _("Unknown"))))

        icon = Gtk.Image.new_from_icon_name(
            app.get("icon", "application-x-executable-symbolic"))
        icon.set_pixel_size(20)
        row.add_prefix(icon)

        remove_btn = Gtk.Button(label=_("Remove"))
        remove_btn.add_css_class("flat")
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.connect("clicked", lambda _b, i=idx: self._remove_pinned(i))
        row.add_suffix(remove_btn)
        return row

    def _remove_pinned(self, idx):
        if 0 <= idx < len(self._pinned_data):
            self._pinned_data.pop(idx)
            self._refresh_pinned_list()
            self.store.save_and_apply("pinned", self._pinned_data)

    # -- Add-pinned sub-page -------------------------------------------

    def _push_add_pinned_page(self):
        if self._nav is None:
            return

        sub = Adw.NavigationPage()
        sub.set_title(_("Add Pinned App"))

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())  # automatic back button

        inner = Adw.PreferencesPage()

        # Search group: single AdwEntryRow used as a filter driver. No
        # apply side-effects — we just watch `notify::text` to
        # invalidate the apps group filter.
        search_group = Adw.PreferencesGroup()
        search_row = Adw.EntryRow()
        search_row.set_title(_("Search apps"))
        search_group.add(search_row)
        inner.add(search_group)

        # Apps group populated from Gio.AppInfo.get_all(). Each row is
        # an AdwActionRow with an icon prefix and an Add button suffix
        # that calls _add_app_from_info + pops the nav page.
        apps_group = Adw.PreferencesGroup()
        apps_group.set_title(_("Applications"))
        inner.add(apps_group)

        apps = [a for a in Gio.AppInfo.get_all() if a.should_show()]
        apps.sort(key=lambda a: a.get_display_name().lower())

        app_rows: list[tuple[Adw.ActionRow, str]] = []

        for app in apps:
            row = Adw.ActionRow()
            row.set_title(app.get_display_name())

            icon_info = app.get_icon()
            if icon_info is not None:
                icon_widget = Gtk.Image.new_from_gicon(icon_info)
            else:
                icon_widget = Gtk.Image.new_from_icon_name(
                    "application-x-executable-symbolic")
            icon_widget.set_pixel_size(24)
            row.add_prefix(icon_widget)

            add_btn = Gtk.Button(label=_("Add"))
            add_btn.add_css_class("suggested-action")
            add_btn.set_valign(Gtk.Align.CENTER)
            add_btn.connect(
                "clicked", lambda _b, a=app: self._on_add_app_clicked(a))
            row.add_suffix(add_btn)

            apps_group.add(row)
            app_rows.append((row, app.get_display_name().lower()))

        def _on_search_changed(entry: Adw.EntryRow, _pspec) -> None:
            query = entry.get_text().lower().strip()
            for row, name in app_rows:
                row.set_visible(not query or query in name)

        search_row.connect("notify::text", _on_search_changed)

        toolbar.set_content(inner)
        sub.set_child(toolbar)
        self._nav.push(sub)

    def _on_add_app_clicked(self, app_info):
        self._add_app_from_info(app_info)
        if self._nav is not None:
            self._nav.pop()

    def _add_app_from_info(self, app_info):
        name = app_info.get_display_name()
        cmd = re.sub(r'\s*%[uUfFdDnNickvm]', '', app_info.get_commandline() or "").strip()
        if not cmd:
            self.store.show_toast(
                _("{app} has no launch command").format(app=name), True)
            return

        icon_gicon = app_info.get_icon()
        icon = ""
        if icon_gicon is not None:
            # Prefer simple themed-icon names (first name in a GThemedIcon) over
            # the full GIcon serialization — downstream waybar and Gtk.Image
            # both accept icon *names*, not serialized GIcon strings.
            if isinstance(icon_gicon, Gio.ThemedIcon):
                names = icon_gicon.get_names() or []
                icon = names[0] if names else ""
            elif isinstance(icon_gicon, Gio.FileIcon):
                f = icon_gicon.get_file()
                icon = f.get_path() if f else ""
            else:
                icon = icon_gicon.to_string() or ""
        if not icon:
            icon = "application-x-executable-symbolic"

        self._pinned_data.append({"name": name, "command": cmd, "icon": icon})
        self._refresh_pinned_list()
        self.store.save_and_apply("pinned", self._pinned_data)
