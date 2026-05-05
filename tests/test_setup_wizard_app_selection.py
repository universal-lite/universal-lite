import ast
import re
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
        "desktop_id": "io.github.kolunmi.Bazaar.desktop",
        "app_id": "io.github.kolunmi.Bazaar",
        "startup_wm_class": "io.github.kolunmi.Bazaar",
    }]


def test_no_selected_apps_means_no_pinned_defaults(monkeypatch):
    module = _load_wizard_helpers(monkeypatch)

    assert module["_pinned_apps_for_selected_flatpaks"](set()) == []


def test_password_entries_avoid_missing_activates_default_api():
    tree = ast.parse(WIZARD.read_text())
    password_entries = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if not (
            isinstance(func, ast.Attribute)
            and func.attr == "PasswordEntry"
            and isinstance(func.value, ast.Name)
            and func.value.id == "Gtk"
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                password_entries.add(target.attr)
            elif isinstance(target, ast.Name):
                password_entries.add(target.id)

    bad_lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "set_activates_default":
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Attribute) and receiver.attr in password_entries:
            bad_lines.append(node.lineno)
        elif isinstance(receiver, ast.Name) and receiver.id in password_entries:
            bad_lines.append(node.lineno)

    assert not bad_lines, (
        "Gtk.PasswordEntry in the installer image lacks set_activates_default; "
        f"use the activate signal instead. Lines: {bad_lines}"
    )


def test_wizard_avoids_removed_accessibility_live_region_api():
    source = WIZARD.read_text()

    assert "Gtk.AccessibleProperty.LIVE" not in source
    assert "Gtk.AccessibleLive" not in source
    assert ".announce(" in source


def test_wizard_uses_current_alert_dialog_api():
    source = WIZARD.read_text()
    tree = ast.parse(source)

    assert "Gtk.MessageDialog" not in source

    helper = next(
        (
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_show_install_in_progress_alert"
        ),
        None,
    )
    assert helper is not None

    has_alert_dialog_guard = False
    for node in ast.walk(helper):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "hasattr"):
            continue
        if len(node.args) != 2:
            continue
        namespace, attribute = node.args
        if (
            isinstance(namespace, ast.Name)
            and namespace.id == "Gtk"
            and isinstance(attribute, ast.Constant)
            and attribute.value == "AlertDialog"
        ):
            has_alert_dialog_guard = True

    assert has_alert_dialog_guard


def test_wizard_dropdowns_force_dark_theme_foregrounds(monkeypatch):
    css = _load_wizard_helpers(monkeypatch)["CSS"]

    for selector in (
        "dropdown button",
        "dropdown button label",
        "dropdown button arrow",
        "dropdown popover label",
    ):
        assert re.search(
            rf"(^|\n){re.escape(selector)}\s*\{{[^}}]*\bcolor\s*:",
            css,
            flags=re.DOTALL,
        ), f"{selector} must set color for the wizard's dark custom theme"
