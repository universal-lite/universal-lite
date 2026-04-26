import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files/usr/lib/universal-lite"))

from settings.pages import default_apps, keyboard, panel  # noqa: E402


def test_keyboard_binding_clone_does_not_mutate_default_baseline():
    defaults = [{"key": "C-A-T", "action": "Execute", "command": "foot"}]

    cloned = keyboard._clone_bindings(defaults)
    cloned[0]["key"] = "C-A-Y"

    assert defaults[0]["key"] == "C-A-T"


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
