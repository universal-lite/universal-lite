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
