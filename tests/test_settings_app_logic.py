import sys
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files/usr/lib/universal-lite"))

from settings.pages import about, default_apps, keyboard, panel, power_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_keyboard_binding_clone_does_not_mutate_default_baseline():
    defaults = [{"key": "C-A-T", "action": "Execute", "command": "foot"}]

    cloned = keyboard._clone_bindings(defaults)
    cloned[0]["key"] = "C-A-Y"

    assert defaults[0]["key"] == "C-A-T"


def test_keyboard_user_keybindings_coerce_malformed_optional_fields(
    monkeypatch, tmp_path
):
    path = tmp_path / "keybindings.json"
    path.write_text(
        """
        [
          {
            "key": "C-A-Y",
            "action": "Execute",
            "command": [],
            "direction": {},
            "menu": 12,
            "display_name": []
          }
        ]
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(keyboard, "USER_KEYBINDINGS", path)

    loaded = keyboard._load_user_keybindings()

    assert loaded == [{
        "key": "C-A-Y",
        "action": "Execute",
        "command": "",
        "direction": "",
        "menu": "",
        "display_name": "Execute",
    }]


def test_keyboard_layouts_fall_back_when_localectl_returns_empty(monkeypatch):
    monkeypatch.setattr(keyboard, "_layouts_cache", None)
    monkeypatch.setattr(
        keyboard.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )

    assert keyboard.KeyboardPage._get_layouts() == ["us"]


def test_panel_sanitize_pinned_skips_invalid_entries():
    pinned = panel.PanelPage._sanitize_pinned([
        "bad",
        {"name": "No command"},
        {"name": "Files", "command": "Thunar", "icon": ""},
        {"command": "foot"},
    ])

    assert pinned == [
        {
            "name": "Files",
            "command": "Thunar",
            "icon": "application-x-executable-symbolic",
        },
        {
            "name": "foot",
            "command": "foot",
            "icon": "application-x-executable-symbolic",
        },
    ]


def test_panel_sanitize_layout_filters_unknowns_and_duplicates():
    raw = {
        "start": ["custom/launcher", "clock", "clock", "unknown"],
        "center": ["wlr/taskbar"],
        "end": ["battery"],
    }

    layout = panel.PanelPage._sanitize_layout(raw)

    assert layout == {
        "start": ["custom/launcher", "clock"],
        "center": ["wlr/taskbar"],
        "end": ["battery", "pulseaudio", "backlight", "tray"],
    }


def test_panel_edge_change_saves_and_relabels_sections():
    class Store:
        def __init__(self):
            self.data = {"edge": "bottom"}
            self.saved = []

        def get(self, key, default=None):
            return self.data.get(key, default)

        def save_and_apply(self, key, value):
            self.data[key] = value
            self.saved.append((key, value))

    class Group:
        def __init__(self):
            self.title = None

        def set_title(self, title):
            self.title = title

    page = panel.PanelPage.__new__(panel.PanelPage)
    page.store = Store()
    page._updating = False
    page._section_groups = {section: Group() for section in panel.SECTION_ORDER}
    page._refresh_module_lists = lambda: None

    page._on_edge_changed("left")

    assert page.store.saved == [("edge", "left")]
    assert [page._section_groups[s].title for s in panel.SECTION_ORDER] == [
        "Top", "Center", "Bottom",
    ]


def test_terminal_desktop_write_is_atomic_and_reports_success(monkeypatch, tmp_path):
    class FakeAppInfo:
        def get_commandline(self):
            return "/bin/sh"

        def get_executable(self):
            return "/bin/sh"

        def get_display_name(self):
            return "Shell\nTerminal"

    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_apps.DefaultAppsPage._set_terminal(FakeAppInfo()) is True

    desktop = tmp_path / ".local/share/applications/terminal.desktop"
    assert desktop.exists()
    content = desktop.read_text(encoding="utf-8")
    assert "Name=Shell Terminal" in content
    assert "Exec=/bin/sh" in content
    assert not desktop.with_suffix(".desktop.tmp").exists()


def test_terminal_desktop_write_reports_invalid_command(monkeypatch, tmp_path):
    class FakeAppInfo:
        def get_commandline(self):
            return "/definitely/missing/terminal"

        def get_executable(self):
            return "/definitely/missing/terminal"

        def get_display_name(self):
            return "Missing"

    monkeypatch.setenv("HOME", str(tmp_path))

    assert default_apps.DefaultAppsPage._set_terminal(FakeAppInfo()) is False


def test_default_apps_browser_row_covers_related_mime_types():
    groups = dict(default_apps.APP_MIME_TYPES)

    assert groups["Web Browser"] == (
        "x-scheme-handler/http",
        "x-scheme-handler/https",
        "text/html",
    )


def test_restore_defaults_category_titles_escape_markup_ampersands():
    assert about._row_title_text("Mouse & Touchpad") == "Mouse &amp; Touchpad"
    assert about._row_title_text("Date & Time") == "Date &amp; Time"


def test_restore_defaults_has_accessibility_category_separate_from_appearance():
    assert about.CATEGORY_KEYS["Appearance"] == ["theme", "accent", "wallpaper"]
    assert about.CATEGORY_KEYS["Accessibility"] == [
        "font_size", "cursor_size", "high_contrast", "reduce_motion",
    ]


def test_power_timeout_sanitizer_matches_apply_defaults():
    assert power_lock._sanitize_timeout(999, 300) == 300
    assert power_lock._sanitize_timeout("600", 300) == 600
    assert power_lock._sanitize_timeout("bad", 0) == 0


def test_settings_launcher_guards_vm_renderer_before_importing_gtk_app():
    source = (ROOT / "files/usr/bin/universal-lite-settings").read_text(
        encoding="utf-8"
    )

    guard_idx = source.index("_guard_gtk_renderer_for_virtualized_sessions()")
    import_idx = source.index("from settings.app import main")
    assert guard_idx < import_idx
    assert "systemd-detect-virt" in source
    assert 'os.environ["GSK_RENDERER"] = "gl"' in source


def test_power_lock_helper_survives_transient_unmap():
    source = (
        ROOT / "files/usr/lib/universal-lite/settings/pages/power_lock.py"
    ).read_text(encoding="utf-8")

    assert 'connect("unrealize", lambda _w: self._teardown_helpers())' in source
    assert 'connect("unmap", lambda _w: self._teardown_helpers())' not in source


def test_power_profile_set_uses_async_dbus_call():
    source = (
        ROOT / "files/usr/lib/universal-lite/settings/dbus_helpers.py"
    ).read_text(encoding="utf-8")
    body = source.split("def set_active_profile", 1)[1].split(
        "def _on_props_changed", 1
    )[0]

    assert "self._bus.call(" in body
    assert "call_sync(" not in body
    assert "def _on_set_active_profile_done" in body


def test_window_close_holds_application_until_apply_work_drains():
    source = (
        ROOT / "files/usr/lib/universal-lite/settings/window.py"
    ).read_text(encoding="utf-8")

    assert "if self._store.has_apply_work():" in source
    assert "app.hold()" in source
    assert "self._store.wait_for_apply(_release_app)" in source


def test_failed_page_build_unsubscribes_partial_subscriptions():
    source = (
        ROOT / "files/usr/lib/universal-lite/settings/window.py"
    ).read_text(encoding="utf-8")

    assert "page.unsubscribe_all()" in source
