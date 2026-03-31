import json
import os
import subprocess
import threading
from pathlib import Path

from gi.repository import GLib


class SettingsStore:
    """JSON settings persistence with atomic writes, debounce, and apply feedback."""

    def __init__(self, settings_path=None, defaults_path=None, apply_script=None):
        self._path = Path(
            settings_path
            or Path.home() / ".config/universal-lite/settings.json"
        )
        self._defaults_path = Path(
            defaults_path
            or "/usr/share/universal-lite/defaults/settings.json"
        )
        self._apply_script = str(
            apply_script or "/usr/libexec/universal-lite-apply-settings"
        )
        self._debounce_timers: dict[str, int] = {}
        self._toast_callback = None
        self._data = self._load()

    def _load(self) -> dict:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return self._load_defaults(write_to_user=True)
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._load_defaults(write_to_user=True)

    def _load_defaults(self, write_to_user: bool = False) -> dict:
        try:
            default_text = self._defaults_path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            data = json.loads(default_text)
        except json.JSONDecodeError:
            return {}
        if write_to_user:
            try:
                self._path.write_text(default_text, encoding="utf-8")
            except OSError:
                pass
        return data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def save_and_apply(self, key: str, value) -> None:
        self._data[key] = value
        self._write()
        self._run_apply()

    def save_dict_and_apply(self, updates: dict) -> None:
        self._data.update(updates)
        self._write()
        self._run_apply()

    def save_debounced(self, key: str, value, delay_ms: int = 300) -> None:
        if key in self._debounce_timers:
            GLib.source_remove(self._debounce_timers[key])

        def _apply():
            self._debounce_timers.pop(key, None)
            self.save_and_apply(key, value)
            return GLib.SOURCE_REMOVE

        self._debounce_timers[key] = GLib.timeout_add(delay_ms, _apply)

    def set_toast_callback(self, callback) -> None:
        self._toast_callback = callback

    def _write(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2) + "\n", encoding="utf-8"
        )
        os.rename(tmp, self._path)

    def _run_apply(self) -> None:
        try:
            proc = subprocess.Popen(
                [self._apply_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            if self._toast_callback:
                self._toast_callback("Apply script not found", True)
            return

        def _wait():
            _, stderr = proc.communicate()
            GLib.idle_add(self._on_apply_done, proc.returncode, stderr)

        threading.Thread(target=_wait, daemon=True).start()

    def _on_apply_done(self, returncode: int, stderr_bytes: bytes) -> bool:
        if self._toast_callback is not None:
            if returncode == 0:
                self._toast_callback("Settings applied", False)
            else:
                err = stderr_bytes.decode("utf-8", errors="replace").strip()
                msg = f"Failed to apply: {err[:80]}" if err else "Failed to apply settings"
                self._toast_callback(msg, True)
        return GLib.SOURCE_REMOVE
