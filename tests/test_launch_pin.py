"""Tests for the transient Waybar pinned-app launch helper."""

import importlib.machinery
import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "files/usr/libexec/universal-lite-launch-pin"
_loader = importlib.machinery.SourceFileLoader("launch_pin", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("launch_pin", _loader, origin=str(_SCRIPT))
launch_pin = importlib.util.module_from_spec(_spec)
launch_pin.__file__ = str(_SCRIPT)
_spec.loader.exec_module(launch_pin)


def test_set_and_clear_pending_state(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(launch_pin, "_refresh_waybar", lambda: None)

    launch_pin._set_pending(2, timeout=15.0, fallback_seconds=1.4)

    state_path = tmp_path / "universal-lite" / launch_pin.STATE_NAME
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert "2" in data["pins"]
    assert data["pins"]["2"]["expires_at"] > data["pins"]["2"]["started_at"]

    launch_pin._clear_pending(2)

    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert "2" not in data["pins"]


def test_parse_requires_command_for_launch_mode():
    try:
        launch_pin._parse_args(["--pin", "1"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected parser failure")


def test_monitor_mode_does_not_require_command():
    args = launch_pin._parse_args(["--monitor", "--pin", "1", "--app-id", "app"])
    assert args.monitor is True
    assert args.command is None
    assert args.app_id == ["app"]


def test_existing_window_uses_short_fallback_monitor(monkeypatch):
    calls = []
    args = SimpleNamespace(
        pin=0,
        app_id=["com.example.App"],
        command="true",
        timeout=15.0,
        fallback_seconds=1.4,
    )
    monkeypatch.setattr(launch_pin, "_matching_window_exists", lambda ids: True)
    monkeypatch.setattr(launch_pin, "_set_pending", lambda *a: calls.append(("set", a)))
    monkeypatch.setattr(launch_pin, "_clear_pending", lambda *a: calls.append(("clear", a)))
    monkeypatch.setattr(
        launch_pin.subprocess,
        "Popen",
        lambda *a, **kw: calls.append(("popen", a, kw)),
    )

    assert launch_pin._launch(args) == 0

    monitor = calls[-1]
    assert monitor[0] == "popen"
    assert "--monitor" in monitor[1][0]
    assert "--app-id" not in monitor[1][0]
