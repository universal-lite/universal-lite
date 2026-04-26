import runpy
import sys
import types
from pathlib import Path


WIZARD = Path(__file__).resolve().parents[1] / "files/usr/bin/universal-lite-setup-wizard"


class _FakeGiNamespace(types.ModuleType):
    def __getattr__(self, name):
        value = type(name, (), {})
        setattr(self, name, value)
        return value


def _load_wizard_helpers(monkeypatch):
    gi = types.ModuleType("gi")
    gi.require_version = lambda *_args, **_kwargs: None
    repository = types.ModuleType("gi.repository")
    for name in ("Gtk", "Gdk", "GLib", "Gio", "NM", "Pango"):
        setattr(repository, name, _FakeGiNamespace(name))
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)
    return runpy.run_path(str(WIZARD), run_name="wizard_for_test")


def test_empty_app_selection_writes_zero_byte_flatpak_list(monkeypatch):
    module = _load_wizard_helpers(monkeypatch)

    assert module["_flatpak_app_list_contents"](set()) == ""


def test_app_selection_writes_deterministic_flatpak_list(monkeypatch):
    module = _load_wizard_helpers(monkeypatch)

    content = module["_flatpak_app_list_contents"]({
        "io.github.kolunmi.Bazaar",
        "com.google.Chrome",
    })

    assert content == "com.google.Chrome\nio.github.kolunmi.Bazaar\n"


def test_pinned_defaults_follow_selected_apps(monkeypatch):
    module = _load_wizard_helpers(monkeypatch)

    pinned = module["_pinned_apps_for_selected_flatpaks"]({
        "io.github.kolunmi.Bazaar",
        "org.gtk.Gtk3theme.adw-gtk3",
    })

    assert pinned == [{
        "name": "Bazaar",
        "command": "flatpak run io.github.kolunmi.Bazaar",
        "icon": "io.github.kolunmi.Bazaar",
    }]


def test_no_selected_apps_means_no_pinned_defaults(monkeypatch):
    module = _load_wizard_helpers(monkeypatch)

    assert module["_pinned_apps_for_selected_flatpaks"](set()) == []
