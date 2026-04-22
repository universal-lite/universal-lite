import json
import os
import subprocess
import threading
from gettext import gettext as _
from pathlib import Path

from gi.repository import GLib


class SettingsStore:
    """JSON settings persistence with atomic writes, debounce, and apply feedback."""

    APPLY_TIMEOUT_SEC = 30

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
        self._apply_running = False
        self._apply_pending = False
        self._apply_wait_source: int | None = None

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

    def get_defaults(self) -> dict:
        """Load and return the factory defaults from the image."""
        return self._load_defaults()

    def restore_keys(self, keys: list[str], defaults: dict) -> None:
        """Overwrite specified keys with values from defaults, then apply."""
        for key in keys:
            if key in defaults:
                self._data[key] = defaults[key]
            else:
                self._data.pop(key, None)
        self._write()
        self._run_apply()

    def remove_keys_matching(self, predicate) -> None:
        """Drop every key for which *predicate* returns True. No apply side-effect.

        Intended for Restore Defaults to clear runtime-discovered keys
        (e.g. per-output ``resolution_*`` entries) that aren't listed in
        CATEGORY_KEYS. The caller triggers apply via restore_keys.
        """
        for key in [k for k in self._data if predicate(k)]:
            self._data.pop(key, None)

    def save_and_apply(self, key: str, value) -> None:
        self._data[key] = value
        self._write()
        self._run_apply()

    def save_dict_and_apply(self, updates: dict) -> None:
        self._data.update(updates)
        self._write()
        self._run_apply()

    def apply(self) -> None:
        """Trigger apply-settings without modifying stored values.

        Used when a page writes to an out-of-band file (e.g. user
        keybindings JSON) and needs the reconciler to re-read it.

        On completion, fires the toast callback ("Settings applied" or an
        error message) exactly as save_and_apply() would.
        """
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

    def show_toast(self, message: str, is_error: bool = False) -> None:
        if self._toast_callback is not None:
            self._toast_callback(message, is_error)

    def flush_and_detach(self) -> None:
        """Cancel pending debounces and detach the toast callback.

        Called from SettingsWindow.close-request. Without this, a user
        who changes a setting and closes the window within ~300 ms
        leaves a debounce timer scheduled; when it fires it runs
        save_and_apply, which spawns apply-settings, which completes
        on a background thread and calls self._toast_callback(...) ->
        self._show_toast on a freed Adw.ToastOverlay. Also detaches
        the callback so a pending apply from the old window doesn't
        toast on a new window's overlay after reopen.
        """
        for source_id in self._debounce_timers.values():
            GLib.source_remove(source_id)
        self._debounce_timers.clear()
        if self._apply_wait_source is not None:
            GLib.source_remove(self._apply_wait_source)
            self._apply_wait_source = None
        self._toast_callback = None

    def _write(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=2) + "\n", encoding="utf-8"
        )
        os.chmod(tmp, 0o600)
        os.rename(tmp, self._path)

    def _run_apply(self) -> None:
        if self._apply_running:
            self._apply_pending = True
            return
        self._apply_running = True

        try:
            proc = subprocess.Popen(
                [self._apply_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            # Any OS-level failure to launch the apply script would
            # otherwise leave _apply_running stuck True, silently
            # disabling every future save-and-apply for the session.
            # ENOMEM on 2 GB hardware, a transient bootc overlay swap
            # making the script briefly unreadable, or a permission
            # glitch during a rebase all hit this path. Also reset
            # _apply_pending so the retry-loop in _on_apply_done doesn't
            # attempt to re-enter this same broken state immediately.
            self._apply_running = False
            self._apply_pending = False
            if self._toast_callback:
                detail = str(exc) or exc.__class__.__name__
                self._toast_callback(f"Failed to apply settings: {detail}", True)
            return

        def _wait():
            try:
                _, stderr = proc.communicate(timeout=self.APPLY_TIMEOUT_SEC)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    _, stderr = proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    stderr = b""
                rc = -1  # sentinel for timeout
            GLib.idle_add(self._on_apply_done, rc, stderr)

        threading.Thread(target=_wait, daemon=True).start()

    def _on_apply_done(self, returncode: int, stderr_bytes: bytes) -> bool:
        self._apply_running = False
        if self._toast_callback is not None:
            if returncode == 0:
                self._toast_callback("Settings applied", False)
            elif returncode == -1:
                msg = _("Apply timed out after {n}s").format(n=self.APPLY_TIMEOUT_SEC)
                self._toast_callback(msg, True)
            else:
                err = stderr_bytes.decode("utf-8", errors="replace").strip()
                msg = f"Failed to apply: {err[:80]}" if err else "Failed to apply settings"
                self._toast_callback(msg, True)
        if self._apply_pending:
            self._apply_pending = False
            self._run_apply()
        return GLib.SOURCE_REMOVE

    def wait_for_apply(self, callback) -> None:
        """Call callback once the current apply-settings finishes.
        If no apply is running, calls immediately via idle_add.

        The poll source ID is tracked on the store so flush_and_detach
        can cancel it when the window closes; previously, a user
        clicking Restart from About and then closing the window while
        the apply was still running would leave a 50 ms poll firing
        until the 30 s APPLY_TIMEOUT_SEC expired (or the apply
        finished), at which point the callback would invoke _do_restart
        on a dead window.
        """
        if not self._apply_running:
            GLib.idle_add(callback)
            return

        def _poll():
            if self._apply_running:
                return GLib.SOURCE_CONTINUE
            self._apply_wait_source = None
            callback()
            return GLib.SOURCE_REMOVE
        self._apply_wait_source = GLib.timeout_add(50, _poll)
