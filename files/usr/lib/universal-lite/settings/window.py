import sys
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, GObject, Gio, Gtk

from .events import EventBus
from .settings_store import SettingsStore
from .toast import ToastWidget


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, store: SettingsStore, event_bus: EventBus) -> None:
        super().__init__(application=app)
        self.set_title(_("Settings"))
        self.set_default_size(900, 600)
        self.set_size_request(700, 500)

        self._store = store
        self._event_bus = event_bus
        self._page_names: list[str] = []
        self._pages: list = []

        # HeaderBar with search toggle. Explicit decoration layout so the
        # minimize/maximize controls appear even when the GTK settings.ini
        # default hasn't propagated into this process yet.
        header = Gtk.HeaderBar()
        header.set_decoration_layout(":minimize,maximize,close")
        search_btn = Gtk.ToggleButton()
        search_btn.set_icon_name("system-search-symbolic")
        search_btn.set_tooltip_text(_("Search settings"))
        header.pack_end(search_btn)
        self.set_titlebar(header)

        # Toast overlay wraps everything
        overlay = Gtk.Overlay()
        self.set_child(overlay)
        self._toast = ToastWidget()
        overlay.add_overlay(self._toast)
        store.set_toast_callback(self._toast.show_toast)

        # Main vertical box: search bar + paned
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.set_child(main_box)

        # Search bar (below headerbar, above paned)
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Search settings\u2026"))
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_btn.bind_property("active", self._search_bar, "search-mode-enabled",
                                 GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        main_box.append(self._search_bar)

        # Paned layout
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(220)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_vexpand(True)
        main_box.append(paned)

        # Sidebar — the `.sidebar` class lives on the outer box so the
        # headerbar-tinted fill extends over the whole pane (no gap above
        # or below the row list).
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(220, -1)
        sidebar_box.add_css_class("sidebar")
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_vexpand(True)
        self._sidebar = Gtk.ListBox()
        self._sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar.set_margin_top(8)
        self._sidebar.set_margin_bottom(8)
        sidebar_scroll.set_child(self._sidebar)
        sidebar_box.append(sidebar_scroll)
        paned.set_start_child(sidebar_box)

        # Content stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self._content_scroll = Gtk.ScrolledWindow()
        self._content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._content_scroll.set_child(self._stack)
        self._content_scroll.set_hexpand(True)
        self._content_scroll.set_vexpand(True)
        self._content_scroll.add_css_class("content-area")
        paned.set_end_child(self._content_scroll)

        # Lazy-build tracking: _pages holds every page INSTANCE (cheap —
        # just stores the store/event_bus references), but widgets are only
        # built on first navigation. That's what lets the window map and
        # paint its first frame without having to touch D-Bus for NM/BlueZ/
        # power-profiles or decode wallpaper thumbnails up front.
        self._built: set[str] = set()
        self._build_pages()
        self._sidebar.connect("row-selected", self._on_row_selected)
        first = self._sidebar.get_row_at_index(0)
        if first is not None:
            self._sidebar.select_row(first)

        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", lambda *_: self.toggle_search())
        self.add_action(search_action)

    def _build_pages(self) -> None:
        from .pages import ALL_PAGES

        for icon_name, label, page_cls in ALL_PAGES:
            try:
                page = page_cls(self._store, self._event_bus)
            except Exception as exc:
                print(f"Settings: failed to instantiate {label!r}: {exc!r}", file=sys.stderr)
                page = None

            row = self._build_sidebar_row(icon_name, _(label))
            self._sidebar.append(row)
            self._page_names.append(label)
            self._pages.append(page)

    def _ensure_page_built(self, idx: int) -> None:
        """Build the page's widgets the first time it's shown."""
        label = self._page_names[idx]
        if label in self._built:
            return
        self._built.add(label)
        page = self._pages[idx]
        try:
            widget = page.build() if page is not None else None
        except Exception as exc:
            print(f"Settings: failed to build {label!r}: {exc!r}", file=sys.stderr)
            widget = None
        if widget is None:
            widget = Gtk.Label(label=_("Failed to load {label}").format(label=label), xalign=0)
            widget.add_css_class("setting-subtitle")
        self._stack.add_named(widget, label)

    @staticmethod
    def _build_sidebar_row(icon_name: str, label: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(16)
        icon.add_css_class("category-icon")
        box.append(icon)
        lbl = Gtk.Label(label=label, xalign=0)
        lbl.add_css_class("category-label")
        lbl.set_hexpand(True)
        box.append(lbl)
        row.set_child(box)
        return row

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if row is None:
            return
        idx = row.get_index()
        if not (0 <= idx < len(self._page_names)):
            return
        label = self._page_names[idx]
        # Build on demand. First selection at startup is deferred one tick
        # via GLib.idle_add so the window paints before we start decoding
        # wallpaper thumbnails or opening D-Bus connections — that's what
        # kills the open-time flicker.
        if label not in self._built:
            def _build_then_show():
                self._ensure_page_built(idx)
                self._stack.set_visible_child_name(label)
                adj = self._content_scroll.get_vadjustment()
                if adj:
                    adj.set_value(0)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_build_then_show)
            return
        self._stack.set_visible_child_name(label)
        adj = self._content_scroll.get_vadjustment()
        if adj:
            adj.set_value(0)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text().lower().strip()
        if not text:
            self._sidebar.set_filter_func(None)
            return

        matching: set[int] = set()
        for i, page in enumerate(self._pages):
            if page is None:
                continue
            for group, setting in page.search_keywords:
                if text in group.lower() or text in setting.lower():
                    matching.add(i)
                    break

        self._sidebar.set_filter_func(lambda row: row.get_index() in matching)

    def toggle_search(self) -> None:
        active = self._search_bar.get_search_mode()
        self._search_bar.set_search_mode(not active)
        if not active:
            self._search_entry.grab_focus()
