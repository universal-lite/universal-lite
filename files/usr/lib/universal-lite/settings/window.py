import sys
from gettext import gettext as _

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, GLib, GObject, Gio, Gtk

from .events import EventBus
from .settings_store import SettingsStore
from .toast import ToastWidget


class SettingsWindow(Adw.ApplicationWindow):
    """Top-level settings window.

    Structure:
        AdwApplicationWindow
        └── Gtk.Overlay (hosts the Toast)
            └── AdwOverlaySplitView (sidebar + content, collapsible)
                ├── sidebar: ScrolledWindow > ListBox (category rows)
                └── content: AdwToolbarView
                    ├── top bar: AdwHeaderBar (sidebar toggle, search toggle)
                    ├── top bar: GtkSearchBar
                    └── content: ScrolledWindow > GtkStack (the pages)

    An AdwBreakpoint watching the window's max-width flips the split
    view to collapsed mode (sidebar becomes an overlay drawer) and
    shows the sidebar-toggle button in the header. This is how the
    app stays usable on low-res displays at high scale factors.
    """

    # Below this window width the sidebar collapses into a drawer.
    # `sp` (scalable pixels) respects the Large Text accessibility
    # setting, so users with a bumped font size get the collapse
    # earlier, when they actually need the extra room.
    _COLLAPSE_WIDTH = "max-width: 700sp"

    def __init__(self, app: Adw.Application, store: SettingsStore,
                 event_bus: EventBus) -> None:
        super().__init__(application=app)
        self.set_title(_("Settings"))
        self.set_default_size(900, 600)
        # A small minimum lets the breakpoint actually fire on narrow
        # widths. Without it the window would refuse to shrink below
        # the natural content size of the widest page.
        self.set_size_request(360, 300)

        self._store = store
        self._event_bus = event_bus
        self._page_names: list[str] = []
        self._pages: list = []
        self._built: set[str] = set()

        # -- Sidebar --------------------------------------------------
        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_vexpand(True)
        self._sidebar = Gtk.ListBox()
        self._sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar.set_margin_top(8)
        self._sidebar.set_margin_bottom(8)
        # Adwaita's standard class for a sidebar-style ListBox -
        # gives the rows the correct navigation look and hover colours.
        self._sidebar.add_css_class("navigation-sidebar")
        sidebar_scroll.set_child(self._sidebar)

        # -- Content stack + its scroller ----------------------------
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)
        self._content_scroll = Gtk.ScrolledWindow()
        self._content_scroll.set_policy(Gtk.PolicyType.NEVER,
                                        Gtk.PolicyType.AUTOMATIC)
        self._content_scroll.set_child(self._stack)
        self._content_scroll.add_css_class("content-area")

        # -- Header bar with sidebar toggle + search toggle ----------
        content_header = Adw.HeaderBar()

        # Sidebar toggle. Hidden by default; the breakpoint makes it
        # visible when the sidebar collapses into a drawer so the user
        # can open and close it. A bidirectional bind to the split
        # view's show-sidebar keeps the button state and the actual
        # sidebar visibility in lockstep in either direction.
        sidebar_toggle = Gtk.ToggleButton()
        sidebar_toggle.set_icon_name("sidebar-show-symbolic")
        sidebar_toggle.set_tooltip_text(_("Show sidebar"))
        sidebar_toggle.set_active(True)
        sidebar_toggle.set_visible(False)
        content_header.pack_start(sidebar_toggle)

        search_btn = Gtk.ToggleButton()
        search_btn.set_icon_name("system-search-symbolic")
        search_btn.set_tooltip_text(_("Search settings"))
        content_header.pack_end(search_btn)

        # -- Search bar ----------------------------------------------
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Search settings\u2026"))
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_entry.connect("search-changed", self._on_search_changed)
        search_btn.bind_property(
            "active", self._search_bar, "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        # -- ToolbarView: header + search bar + content --------------
        # AdwToolbarView replaces the older GtkBox-with-headerbar
        # pattern and gets the right elevation + separators between
        # top bars and content for free.
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(content_header)
        toolbar_view.add_top_bar(self._search_bar)
        toolbar_view.set_content(self._content_scroll)

        # -- OverlaySplitView holds sidebar + content ----------------
        split = Adw.OverlaySplitView()
        split.set_sidebar(sidebar_scroll)
        split.set_content(toolbar_view)
        split.set_sidebar_width_fraction(0.25)
        split.set_min_sidebar_width(200.0)
        split.set_max_sidebar_width(280.0)
        self._split_view = split

        split.bind_property(
            "show-sidebar", sidebar_toggle, "active",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        # -- Toast overlay wraps the whole split so the toast widget
        #    floats above either pane -----------------------------------
        overlay = Gtk.Overlay()
        overlay.set_child(split)
        self._toast = ToastWidget()
        overlay.add_overlay(self._toast)
        store.set_toast_callback(self._toast.show_toast)

        self.set_content(overlay)

        # -- Breakpoint: collapse below _COLLAPSE_WIDTH --------------
        # When the window is narrower than the breakpoint, the split
        # view collapses (sidebar becomes an overlay drawer) and the
        # toggle button becomes visible so the user can open it. Both
        # setters revert automatically when the window widens again.
        breakpoint_ = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse(self._COLLAPSE_WIDTH)
        )
        breakpoint_.add_setter(split, "collapsed", True)
        breakpoint_.add_setter(sidebar_toggle, "visible", True)
        self.add_breakpoint(breakpoint_)

        # -- Pages + initial selection -------------------------------
        self._build_pages()
        self._sidebar.connect("row-selected", self._on_row_selected)
        first = self._sidebar.get_row_at_index(0)
        if first is not None:
            self._sidebar.select_row(first)

        # -- Actions -------------------------------------------------
        search_action = Gio.SimpleAction.new("search", None)
        search_action.connect("activate", lambda *_: self.toggle_search())
        self.add_action(search_action)

    def _build_pages(self) -> None:
        from .pages import ALL_PAGES

        for icon_name, label, page_cls in ALL_PAGES:
            try:
                page = page_cls(self._store, self._event_bus)
            except Exception as exc:
                print(f"Settings: failed to instantiate {label!r}: {exc!r}",
                      file=sys.stderr)
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
            print(f"Settings: failed to build {label!r}: {exc!r}",
                  file=sys.stderr)
            widget = None
        if widget is None:
            widget = Gtk.Label(
                label=_("Failed to load {label}").format(label=label),
                xalign=0,
            )
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

    def _on_row_selected(self, _listbox: Gtk.ListBox,
                         row: Gtk.ListBoxRow) -> None:
        if row is None:
            return
        idx = row.get_index()
        if not (0 <= idx < len(self._page_names)):
            return
        label = self._page_names[idx]
        # Build on demand. First selection at startup is deferred one
        # tick via GLib.idle_add so the window paints before we start
        # decoding wallpaper thumbnails or opening D-Bus connections.
        if label not in self._built:
            def _build_then_show() -> int:
                self._ensure_page_built(idx)
                self._stack.set_visible_child_name(label)
                self._reset_scroll()
                self._maybe_close_drawer()
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_build_then_show)
            return
        self._stack.set_visible_child_name(label)
        self._reset_scroll()
        self._maybe_close_drawer()

    def _reset_scroll(self) -> None:
        adj = self._content_scroll.get_vadjustment()
        if adj is not None:
            adj.set_value(0)

    def _maybe_close_drawer(self) -> None:
        """When the sidebar is an overlay drawer, dismiss it after a pick.

        In collapsed mode the sidebar hovers over the content; leaving
        it open after the user has navigated hides the page they just
        picked. Expanded mode (normal desktop width) is a permanent
        split, so we leave it alone there.
        """
        if self._split_view.get_collapsed():
            self._split_view.set_show_sidebar(False)

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
