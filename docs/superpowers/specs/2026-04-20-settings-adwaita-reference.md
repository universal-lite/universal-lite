# Settings-Adwaita Reference Pack

**Purpose:** Pattern library for agents converting settings pages to libadwaita preference widgets. Read this before touching your assigned page. For anything not covered here, query Context7 with library id `/websites/gnome_pages_gitlab_gnome_libadwaita_doc_1-latest`.

**All examples are PyGObject** (what our codebase uses). C names in libadwaita docs map to Python via the usual rules: `adw_switch_row_new()` → `Adw.SwitchRow()`, `adw_switch_row_set_active()` → `switch_row.set_active()`, etc.

---

## Page skeleton

Every converted page follows this exact shape:

```python
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk

from ..base import BasePage


class MyPage(BasePage, Adw.PreferencesPage):
    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)

    @property
    def search_keywords(self):
        return [
            (_("Group Title"), _("Setting Label")),
            # ...
        ]

    def build(self):
        group = Adw.PreferencesGroup()
        group.set_title(_("Group Title"))
        group.set_description(_("Optional description text."))

        # ... add rows to group ...
        group.add(some_row)

        self.add(group)
        return self
```

- `__init__` is cheap: stores references only. `build()` does the widget work on first navigation.
- `build()` returns `self` so the existing lazy-build machinery in `window.py` keeps working unchanged.
- Multiple diamond inheritance is fine because `BasePage.__init__` does not call `super().__init__()`; each init is explicit.

---

## Rows: the stock 80%

### `AdwSwitchRow` — bool settings

Replaces `Gtk.Switch` in `make_setting_row`. Whole-row tappable.

```python
row = Adw.SwitchRow()
row.set_title(_("Setting title"))
row.set_subtitle(_("Optional longer description"))  # skip if empty
row.set_active(self.store.get("key", default))
row.connect("notify::active", self._on_toggle)
group.add(row)

def _on_toggle(self, row, _pspec):
    self.store.save_and_apply("key", row.get_active())
```

- Use `notify::active`, not `state-set`. The old `state-set` was on `Gtk.Switch` and required returning `False`; `notify::active` is the idiomatic Adwaita signal and has no return-value gotcha.
- Don't pass an empty string to `set_subtitle`; just omit the call.

### `AdwComboRow` — enum/choice settings

Replaces `Gtk.DropDown` and our toggle-cards-for-enum pattern.

```python
row = Adw.ComboRow()
row.set_title(_("Power profile"))

# Simple string list:
model = Gtk.StringList.new(["Balanced", "Power Saver", "Performance"])
row.set_model(model)

# Map visible index → stored value:
VALUES = ["balanced", "power-saver", "performance"]
current = self.store.get("power_profile", "balanced")
row.set_selected(VALUES.index(current) if current in VALUES else 0)

row.connect("notify::selected", self._on_profile_changed)
group.add(row)

def _on_profile_changed(self, row, _pspec):
    idx = row.get_selected()
    if 0 <= idx < len(VALUES):
        self.store.save_and_apply("power_profile", VALUES[idx])
```

- If you want the current value shown in the subtitle (GNOME Settings pattern), `row.set_use_subtitle(True)`. Don't set `subtitle` manually when `use_subtitle` is on.
- For large models (timezones, languages) use an `Adw.NavigationPage` push instead — ComboRow's popover gets unusable past ~30 items.

### `AdwSpinRow` — integer settings

Replaces `Gtk.Scale` where the range is small and discrete (timeouts in minutes, repeat rates, etc.).

```python
row = Adw.SpinRow.new_with_range(min=0.0, max=3600.0, step=30.0)
row.set_title(_("Lock timeout"))
row.set_subtitle(_("Seconds of inactivity before lock"))
row.set_value(float(self.store.get("lock_timeout", 300)))
row.connect("notify::value", self._on_timeout_changed)
group.add(row)

def _on_timeout_changed(self, row, _pspec):
    self.store.save_debounced("lock_timeout", int(row.get_value()))
```

- `set_digits(0)` if you want an integer display (defaults to reasonable precision based on step).
- For continuous sliders (volume, pointer speed), use `AdwActionRow` + `Gtk.Scale` (below), not SpinRow.

### `AdwActionRow` — generic row

Replaces our `make_setting_row` for everything that isn't a switch/combo/spin.

**Info row (key + value):**
```python
row = Adw.ActionRow()
row.set_title(_("OS version"))
row.set_subtitle(os_version_string)
row.set_subtitle_selectable(True)
row.add_css_class("property")  # emphasises subtitle over title
group.add(row)
```

**Navigation row (chevron suffix, tap to open):**
```python
row = Adw.ActionRow()
row.set_title(_("Timezone"))
row.set_subtitle(current_tz_name)
row.set_activatable(True)
row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
row.connect("activated", self._push_timezone_picker)
group.add(row)
```

**Row with custom suffix widget (slider, button, etc.):**
```python
row = Adw.ActionRow()
row.set_title(_("Pointer speed"))

scale = Gtk.Scale.new_with_range(
    Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.1)
scale.set_value(self.store.get("touchpad_pointer_speed", 0.0))
scale.set_size_request(200, -1)
scale.set_draw_value(False)
scale.set_valign(Gtk.Align.CENTER)
scale.connect("value-changed", self._on_speed_changed)

row.add_suffix(scale)
group.add(row)
```

- `add_prefix(widget)` and `add_suffix(widget)` — can be called multiple times for icon + secondary widget.
- `set_activatable_widget(widget)` — clicking anywhere on the row triggers that widget's default action (useful with `add_suffix(switch)` patterns, though `AdwSwitchRow` is preferred for pure-toggle cases).

### `AdwExpanderRow` — collapsible section inside a group

Replaces our "Advanced" group pattern where we want it collapsed by default.

```python
expander = Adw.ExpanderRow()
expander.set_title(_("Custom schedule"))
expander.set_subtitle(_("Set exact on/off times"))
expander.set_show_enable_switch(False)  # True if the whole section has its own on/off
expander.set_expanded(False)

start_row = Adw.ActionRow()
start_row.set_title(_("Start time"))
start_row.add_suffix(start_time_entry)
expander.add_row(start_row)

end_row = Adw.ActionRow()
end_row.set_title(_("End time"))
end_row.add_suffix(end_time_entry)
expander.add_row(end_row)

group.add(expander)
```

- `add_row(child_row)` — children nest under the expander.
- `set_show_enable_switch(True)` exposes a switch in the header that enables/disables the section (useful for night-light's custom schedule).

### `AdwEntryRow` — text input

Replaces `Gtk.Entry` in rows. Use where the user types a value.

```python
row = Adw.EntryRow()
row.set_title(_("Computer name"))
row.set_text(self.store.get("hostname", "localhost"))
row.set_show_apply_button(True)
row.connect("apply", self._on_hostname_applied)
group.add(row)

def _on_hostname_applied(self, row):
    self.store.save_and_apply("hostname", row.get_text())
```

- `set_show_apply_button(True)` shows a checkmark button when the value changes; tapping or pressing Enter emits `apply`. Use this for anything with side-effects so we don't apply mid-typing.

### `AdwPasswordEntryRow`

Same as `AdwEntryRow` but with the value hidden and a show/hide eye toggle. Use for password fields (WiFi password capture, user password set).

---

## Empty / warning widgets

### `AdwStatusPage` — empty states

Use inside a group-less page (or as the only child) when there's nothing to show.

```python
status = Adw.StatusPage()
status.set_icon_name("network-wireless-signal-none-symbolic")
status.set_title(_("No networks found"))
status.set_description(_("Make sure you're in range of a Wi-Fi network."))

action_btn = Gtk.Button(label=_("Scan again"))
action_btn.add_css_class("pill")
action_btn.add_css_class("suggested-action")
action_btn.connect("clicked", self._on_rescan)
status.set_child(action_btn)

self.add(status)  # or replace the group content with status
```

- `set_paintable(paintable)` instead of `set_icon_name` for a custom image (e.g., AdwAvatar).
- Clearing the icon: `set_icon_name(None)`.

### `AdwBanner` — persistent warnings at the top of a page

A strip banner with optional button. Shown above groups.

```python
banner = Adw.Banner.new(_("Bluetooth is off"))
banner.set_button_label(_("Turn on"))
banner.connect("button-clicked", self._on_enable_bt)
banner.set_revealed(not self._bt_enabled)
# Place banner BEFORE the first group in build(), or swap it in dynamically.
```

- Banners live outside `AdwPreferencesGroup`. Put them at page top or reveal/dismiss dynamically via `set_revealed(bool)`.

---

## Navigation: pushing sub-pages

Replaces in-page `Gtk.Window` / `Gtk.Dialog` patterns for things like password entry, edit user, pick timezone, capture shortcut.

### Setup once per page that needs it

Wrap your `build()` output in an `AdwNavigationView`. The root page is your preferences content; sub-pages push over it.

```python
def build(self):
    self._nav = Adw.NavigationView()

    root = Adw.NavigationPage()
    root.set_title(_("Keyboard"))
    root_content = Adw.PreferencesPage()
    # ... populate root_content with groups ...
    root.set_child(root_content)
    self._nav.add(root)

    # Return the nav view instead of self. Since `self` IS a
    # PreferencesPage, we need a wrapper widget here: return the nav,
    # not self.
    return self._nav
```

Note: the page's own class is still `Adw.PreferencesPage`, but if you need navigation you return the nav view from `build()` and add `root_content` under it. Only heavy-custom pages need this (network, keyboard, users, about's factory-reset flow).

### Pushing a sub-page

```python
def _push_shortcut_editor(self, _row, shortcut):
    sub = Adw.NavigationPage()
    sub.set_title(_("Edit shortcut"))

    toolbar = Adw.ToolbarView()
    toolbar.add_top_bar(Adw.HeaderBar())  # automatic back button

    # ... build capture UI inside toolbar.set_content(...) ...

    sub.set_child(toolbar)
    self._nav.push(sub)
```

Popping:
```python
self._nav.pop()          # pop current
self._nav.pop_to_tag("root")  # pop back to a tagged page
```

- The back button is automatic — don't add one manually.
- Back gesture and Escape shortcut work out of the box.

---

## Dialogs

### `AdwAlertDialog` — modal confirmations

Replaces `Gtk.MessageDialog` (deprecated in GTK4) and our custom confirm windows.

```python
dialog = Adw.AlertDialog.new(
    _("Restore defaults?"),
    _("This will reset all settings to their initial values.")
)
dialog.add_response("cancel", _("Cancel"))
dialog.add_response("restore", _("Restore"))
dialog.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
dialog.set_default_response("cancel")
dialog.set_close_response("cancel")
dialog.connect("response", self._on_restore_response)
dialog.present(self.get_root())

def _on_restore_response(self, _dialog, response_id):
    if response_id == "restore":
        self.store.restore_defaults()
```

- `add_response(id, label)` — button per response. Use `DESTRUCTIVE` or `SUGGESTED` appearance for emphasis.
- `present(parent_widget)` — pass the window; dialog is auto-centred.
- The response signal carries the chosen id; use `close_response` for what happens when the dialog is dismissed via Escape or back gesture.

---

## Groups with header-suffix buttons

Common pattern for "add user" / "add pinned app" / "add shortcut".

```python
group = Adw.PreferencesGroup()
group.set_title(_("Users"))

add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
add_btn.set_tooltip_text(_("Add user"))
add_btn.add_css_class("flat")
add_btn.connect("clicked", self._push_add_user)
group.set_header_suffix(add_btn)

# ... populate rows from users list ...
self.add(group)
```

- `set_header_suffix(widget)` — the widget floats at the right end of the group title row.

---

## Widgets for page-specific features

### `AdwAvatar` — user pictures

Use inside an `AdwActionRow` as prefix for user lists.

```python
avatar = Adw.Avatar.new(size=32, text=user.full_name, show_initials=True)
if user.icon_path:
    avatar.set_custom_image(Gdk.Texture.new_from_filename(user.icon_path))

row = Adw.ActionRow()
row.set_title(user.full_name)
row.set_subtitle(user.username)
row.add_prefix(avatar)
group.add(row)
```

- `show_initials=True` renders initials from `text` as a fallback when no image is set.

---

## Anti-patterns — don't do these

- **Don't** put rows directly inside `AdwPreferencesPage` without an `AdwPreferencesGroup`. Groups are the required container for rows; without one you lose the boxed-list styling.
- **Don't** use `Gtk.Switch` anywhere a `AdwSwitchRow` would work. We keep them only as suffix widgets in non-row contexts.
- **Don't** set `set_subtitle("")`. Rows auto-hide empty subtitles — just omit the call.
- **Don't** build manual "Cancel / OK" button bars. Use `AdwAlertDialog` with `add_response(...)`.
- **Don't** wrap `AdwPreferencesGroup` in a `Gtk.ScrolledWindow`. `AdwPreferencesPage` scrolls internally.
- **Don't** apply `.boxed-list` manually — that's a libadwaita-internal class used to style `AdwPreferencesGroup`'s inner list. Groups get it automatically.
- **Don't** call `row.connect("state-set", ...)` on `AdwSwitchRow`. Use `notify::active`. The state-set signal is from `Gtk.Switch` and has a gotcha return value.

---

## Signal / handler preservation checklist

When converting a page, the Code-Quality Reviewer subagent verifies each item:

1. Every `store.save_and_apply(...)` call in the old page is present in the new page (same key, same transform).
2. Every `store.save_debounced(...)` call is preserved.
3. Every `self.subscribe(event, cb)` call is preserved (event-bus lifecycle).
4. `self.setup_cleanup(widget)` is called once on the returned root widget so unmap triggers `unsubscribe_all()`.
5. D-Bus subscriptions, timer handles, and any async operations are unchanged.
6. Dialog-escape wiring: if the old page created a dialog via `BasePage.enable_escape_close`, the new page uses `AdwAlertDialog` (which handles Escape natively) OR imports `settings.utils.enable_escape_close` for custom navigation pages.

---

## Falling back to Context7

For patterns not here, query `/websites/gnome_pages_gitlab_gnome_libadwaita_doc_1-latest`. Good queries are specific:

- *"AdwAvatar set_custom_image Python pygobject example"* — narrow, returns usage code
- *"AdwAvatar"* — too broad, returns documentation lists

Do not call Context7 more than 3 times per page conversion. If you need more, you're probably overfitting — report back to the controller instead.
