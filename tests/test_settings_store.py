import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files/usr/lib/universal-lite"))
from settings.settings_store import SettingsStore


def _make_store(tmp_path, defaults=None, existing=None):
    defaults = defaults or {"theme": "light", "accent": "blue"}
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps(defaults))
    settings_file = tmp_path / "settings.json"
    if existing is not None:
        settings_file.write_text(json.dumps(existing))
    return SettingsStore(
        settings_path=settings_file,
        defaults_path=defaults_file,
        apply_script="/bin/true",
    )


def test_loads_defaults_when_no_file(tmp_path):
    store = _make_store(tmp_path)
    assert store.get("theme") == "light"
    assert store.get("accent") == "blue"


def test_loads_existing_file(tmp_path):
    store = _make_store(tmp_path, existing={"theme": "dark", "accent": "red"})
    assert store.get("theme") == "dark"
    assert store.get("accent") == "red"


def test_get_with_default(tmp_path):
    store = _make_store(tmp_path)
    assert store.get("nonexistent", "fallback") == "fallback"


def test_save_and_apply_writes_json(tmp_path):
    store = _make_store(tmp_path)
    store.save_and_apply("theme", "dark")
    assert store.get("theme") == "dark"
    written = json.loads((tmp_path / "settings.json").read_text())
    assert written["theme"] == "dark"


def test_save_dict_and_apply(tmp_path):
    store = _make_store(tmp_path)
    store.save_dict_and_apply({"theme": "dark", "accent": "red"})
    assert store.get("theme") == "dark"
    assert store.get("accent") == "red"


def test_atomic_write_creates_file(tmp_path):
    store = _make_store(tmp_path)
    store.save_and_apply("theme", "dark")
    assert (tmp_path / "settings.json").exists()
    assert not (tmp_path / "settings.json.tmp").exists()


def test_flush_and_detach_writes_latest_pending_debounce(tmp_path):
    store = _make_store(tmp_path)

    with patch("settings.settings_store.GLib.timeout_add", return_value=123), \
         patch("settings.settings_store.GLib.source_remove") as source_remove, \
         patch.object(store, "_run_apply") as run_apply:
        store.save_debounced("theme", "dark")
        store.save_debounced("theme", "blue")

        store.flush_and_detach()

    assert store.get("theme") == "blue"
    written = json.loads((tmp_path / "settings.json").read_text())
    assert written["theme"] == "blue"
    assert source_remove.call_count == 2
    run_apply.assert_called_once_with()


def test_flush_and_detach_keeps_apply_queued_for_flushed_debounce(tmp_path):
    store = _make_store(tmp_path)
    store._apply_running = True

    with patch("settings.settings_store.GLib.timeout_add", return_value=123), \
         patch("settings.settings_store.GLib.source_remove"):
        store.save_debounced("accent", "red")

        store.flush_and_detach()

    assert store.get("accent") == "red"
    assert store._apply_pending is True


def test_flush_and_detach_preserves_existing_queued_apply(tmp_path):
    store = _make_store(tmp_path)
    store._apply_running = True
    store._apply_pending = True

    store.flush_and_detach()

    assert store._apply_pending is True
    assert store.has_apply_work() is True


def test_load_with_unusable_config_parent_falls_back_to_defaults(tmp_path):
    defaults = {"theme": "light"}
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps(defaults))
    bad_parent = tmp_path / "not-a-directory"
    bad_parent.write_text("blocking directory creation")

    store = SettingsStore(
        settings_path=bad_parent / "settings.json",
        defaults_path=defaults_file,
        apply_script="/bin/true",
    )

    assert store.get("theme") == "light"


def test_corrupted_file_resets_to_defaults(tmp_path):
    defaults = {"theme": "light"}
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps(defaults))
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{invalid json")
    store = SettingsStore(
        settings_path=settings_file,
        defaults_path=defaults_file,
        apply_script="/bin/true",
    )
    assert store.get("theme") == "light"
    assert (tmp_path / "settings.json.invalid").read_text() == "{invalid json"
    assert json.loads(settings_file.read_text()) == defaults


def test_non_object_file_resets_to_defaults(tmp_path):
    defaults = {"theme": "light"}
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps(defaults))
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("[]")
    store = SettingsStore(
        settings_path=settings_file,
        defaults_path=defaults_file,
        apply_script="/bin/true",
    )
    assert store.get("theme") == "light"
    assert json.loads((tmp_path / "settings.json.invalid").read_text()) == []
    assert json.loads(settings_file.read_text()) == defaults


def test_restore_keys_can_defer_apply_and_remove_dynamic_keys(tmp_path):
    store = _make_store(
        tmp_path,
        defaults={"theme": "light"},
        existing={"theme": "dark", "resolution_eDP-1": "1024x768@60Hz"},
    )

    with patch.object(store, "_run_apply") as run_apply:
        ok = store.restore_keys(
            ["theme"],
            {"theme": "light"},
            remove_predicate=lambda key: key.startswith("resolution_"),
            apply_now=False,
        )

    assert ok is True
    assert store.get("theme") == "light"
    assert store.get("resolution_eDP-1") is None
    assert json.loads((tmp_path / "settings.json").read_text()) == {"theme": "light"}
    run_apply.assert_not_called()


def test_restore_keys_write_failure_does_not_mutate_memory(tmp_path):
    store = _make_store(tmp_path, existing={"theme": "dark"})

    with patch.object(store, "_write_data", return_value=False):
        ok = store.restore_keys(["theme"], {"theme": "light"})

    assert ok is False
    assert store.get("theme") == "dark"


def test_invalid_known_value_type_falls_back_but_unknown_keys_survive(tmp_path):
    defaults = {"font_size": 11, "theme": "light"}
    store = _make_store(
        tmp_path,
        defaults=defaults,
        existing={"font_size": "large", "theme": "dark", "resolution_eDP-1": "1024x768@60Hz"},
    )
    assert store.get("font_size") == 11
    assert store.get("theme") == "dark"
    assert store.get("resolution_eDP-1") == "1024x768@60Hz"


def test_missing_defaults_file_returns_empty(tmp_path):
    """App must not crash when the defaults file is absent."""
    missing_defaults = tmp_path / "nonexistent_defaults.json"
    settings_file = tmp_path / "settings.json"
    store = SettingsStore(
        settings_path=settings_file,
        defaults_path=missing_defaults,
        apply_script="/bin/true",
    )
    assert store.get("anything", "fallback") == "fallback"


def test_corrupted_file_with_missing_defaults_returns_empty(tmp_path):
    """Corrupt user file + missing defaults must not crash."""
    missing_defaults = tmp_path / "nonexistent_defaults.json"
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{invalid json")
    store = SettingsStore(
        settings_path=settings_file,
        defaults_path=missing_defaults,
        apply_script="/bin/true",
    )
    assert store.get("anything", "fallback") == "fallback"
