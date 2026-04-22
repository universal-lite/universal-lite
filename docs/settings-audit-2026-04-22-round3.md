# Settings App Audit — Round 3 (2026-04-22)

Third comprehensive production-readiness sweep. 12 parallel specialized audit agents
(threading, lifecycle, error-handling, file I/O, D-Bus, subprocess, i18n, accessibility,
apply-settings pipeline, and three page-specific deep-dives) produced ~120 findings;
8 parallel fix agents organized by file-conflict domain applied the verified HIGH-
severity subset.

Total scope: **19 files changed, +1159 / −373 lines.**

## Fixes applied

### apply-settings pipeline (libexec)

- **A1** All 7 consumer-config writers (waybar, GTK, mako, foot, labwc themerc,
  labwc rc overrides, swaylock) now use `_atomic_write_text()` (tmp + fsync +
  os.replace). Previously a mid-write OOM left zero-byte configs that silently
  stripped keybinds, wallpapers, notifications, or lock-screen theming.
- **A2** Any write failure now exits 1 so the store shows an error toast
  instead of the false "Settings applied".
- **A3** `_run_best_effort` now catches `OSError` (including PermissionError
  on SELinux context transitions) in addition to `FileNotFoundError` /
  `CalledProcessError` / `TimeoutExpired`.
- **A4** waybar respawn debounced: rapid successive applies no longer race to
  spawn two waybar processes competing for the layer-shell slot.
- **A5** `restart_program`/`reload_waybar` pkill guarded with try/except
  and `timeout=5`; absent procps-ng no longer kills the apply run.
- **A7** `makoctl reload` skipped when mako config unchanged — stops the
  first-boot stderr spam and avoids reloading mako for unrelated settings.
- **A8** `labwc --reconfigure` skipped when rc.xml/themerc-override unchanged —
  eliminates decoration-flicker on unrelated settings (mako position,
  font, power profile, etc.).
- **A9** `gtk-font-name` now uses `font_size_ui` (matches waybar/mako) instead
  of `font_size_mono` — sized consistently with other UI consumers.
- **A10** greeter-theme and greeter-accent files `unlink()`'d before write to
  survive the ostree hardlink invariant.
- **A11** Initial `settings.json` seed copy now atomic (was `shutil.copy2`).
- **A12** Comment documents that pin on-click runs via `sh -c`; panel.py
  normalizes commands with shlex (H7).
- **A13** `_user_keybind_overrides` accepts empty action as explicit unbind
  sentinel, activating previously-dead unbind branch in
  `_build_merged_keybinds_xml`.

### dbus_helpers.py

- **B1** Added gettext import so the module can translate user-visible strings.
- **B2** BlueZ signal subscriptions collected into `_sub_ids`; `teardown()`
  unsubscribes on page destroy. Prevents zombie callbacks and memory leaks
  across settings-app open/close cycles.
- **B3** PowerProfiles subscription tracked and torn down the same way.
- **B4** Converted sync `call_sync` → async `call` + `_on_*_done` callback
  for `set_powered`, `start_discovery`, `stop_discovery`, `disconnect_device`,
  `remove_device`. No more 5-second UI freezes after suspend/resume.
- **B5** `set_powered` done callback publishes `bluetooth-changed` on both
  success and failure — UI toggle no longer desynchronizes from adapter state.
- **B6** Pair-error now publishes `exc.message` (human-readable) instead of
  `str(GLib.Error)` (GLib repr). Orca stops reading error-domain junk.
- **B7** Generic NM connect failure publishes `_("Could not connect to
  network")` (localized, no SSID leak); raw NM message still logged to stderr.
- **B8** All user-visible strings in `dbus_helpers.py` now wrapped in `_()`:
  "Wrong password.", "Could not connect to network", "N/A" (IP/gateway/DNS),
  and the BlueZ device "Unknown" fallback now falls through to the page's
  already-localized `_("Unknown device")`.
- **B10** `pactl subscribe` Popen gets `start_new_session=True` — terminal
  SIGHUP no longer kills it unexpectedly.
- **B11** `PulseAudioSubscriber.stop()` restructured with `finally` to
  guarantee stdout close on every exception path.
- **B12** `_on_props_changed` wraps `params.unpack()` in try/except + bounds
  check — malformed BlueZ signals no longer crash the handler.
- **B13** `disconnect_wifi` / `forget_connection` now use proper done
  callbacks that surface D-Bus errors to stderr and publish `network-changed`
  for UI refresh.
- **B14** `is_powered` null-checks `_bus` before `call_sync`.

### settings_store, wallpapers, app, entry point

- **C1** `_load_defaults` first-boot seed write is now atomic.
- **C2** Custom-wallpaper manifest write is atomic; on write failure the
  orphan image copy is cleaned up.
- **C3** MIME sniff failure is no longer treated as "unknown = allowed";
  empty content_type is now rejected. Exception type narrowed to `GLib.Error`.
- **C4** Wallpaper `wp_id` hashed from file **content** instead of source
  path. Re-uploading the same file dedupes correctly regardless of path;
  different content at the same path no longer collides.
- **C5** `App.do_activate` CSS provider loading guarded by
  `_css_providers_loaded` flag so repeated activations don't stack providers
  on the default display.
- **C6** Entry point sets `locale.setlocale(locale.LC_ALL, "")` so
  `datetime.strftime` renders translated month/day names in non-English locales.

### about / datetime / language / mouse_touchpad

- **D1** **Restore Defaults never actually restarted the app** (caught by
  5 audit agents). The `_restart` closure was dead code; the `wait_for_apply`
  + 10s fallback block was indented inside `_restore_language_defaults` and
  referenced an out-of-scope `_restart`, triggering `NameError` at runtime.
  Fixed: restart logic moved into `_on_reset_clicked` where it runs for all
  category combinations; dead code removed.
- **D2** `clock_24h` moved from `CATEGORY_KEYS["Panel"]` to
  `CATEGORY_KEYS["Date & Time"]` — resetting Panel no longer wipes the
  user's clock-format preference.
- **D3** CPU/RAM/GPU "Unknown" fallbacks wrapped in `_()`.
- **D4** Disk-usage string converted from f-string to `_().format()`.
- **D5** `_check_updates` catches `OSError`; the "Checking…" subtitle no
  longer sticks forever on exec-permission errors.
- **D6** `lspci` except tuple extended with `OSError`.
- **D7** `_set_ntp` reverts the switch on timedatectl failure; re-entry
  guarded by `_ntp_updating` flag.
- **D8** Live clock timer: 1 s → 30 s, seconds dropped from format string.
  Orca no longer reads the current time aloud 60× per minute when focus
  lands anywhere on the Date & Time page.
- **D9** `_set_timezone` refreshes the EntryRow on success so the canonical
  form is shown (e.g. user types `us/ny`, row updates to `America/New_York`).
- **D10** DateTime page added missing `setup_cleanup` call.
- **D11** Language page: three blocking `localectl` calls moved off the main
  thread into a single worker; rows show a placeholder until populated.
- **D12** `_set_format` now preserves LANG when updating LC_TIME/NUMERIC/
  MONETARY — systemd ≥ 246's set-locale replace-all no longer strips LANG.
- **D13** Both localectl parsers use `LC_ALL=C` env for consistent output.
- **D14** Mouse pointer-speed scale gets `set_draw_value(True)` + format
  function (round-2 fix for touchpad wasn't propagated to mouse).

### keyboard.py

- **E1** Shift+letter keys downshifted: capturing Shift+t now stores
  `"S-t"` (labwc convention), not `"S-T"` (which never fires).
- **E2** "Reset All" now gated behind a destructive-confirmation
  AlertDialog. Previously a single mis-tap wiped all custom shortcuts.
- **E3** Variant ComboRow `notify::selected` guarded by
  `_updating_variant` flag during model swap — layout changes no longer
  fire spurious save_and_apply runs.
- **E4** Conflict reassignment: when the displaced binding has no default,
  the UI now shows a toast asking the user to rebind, instead of silently
  leaving a blank-subtitle phantom binding.
- **E5** `localectl` layout/variant queries cached at module load so
  second and later page opens skip the 10 s subprocess stall.
- **E6** Reset-to-default icon buttons get AT-SPI accessible labels.
- **E7** `keybindings.json` write: fsync + `os.replace` replaces
  `Path.rename` — no more silent loss on power failure.
- **E8** Reserved-key AlertDialog sets `close_response="ok"` so Escape
  dismisses it.
- **E9** Three `dialog.present(self)` sites now pass `self.get_root()`
  (the actual window) for correct focus return.
- **E10** Action-name fallback labels (Volume Up, Brightness Up, Screenshot,
  Run: {command}) wrapped in `_()` for translation.

### network.py

- **F1** `_connect_in_flight` set in `_do_password_connect` and
  `_do_hidden_connect` — double-tap on secured/hidden networks no longer
  fires two concurrent NM activate calls.
- **F2** `_connect_in_flight` declared in `__init__`; defensive `getattr`
  removed.
- **F3** "Forget" now shows a destructive-confirmation AlertDialog.
  Previously a single tap dropped the active session network instantly,
  which could interrupt a bootc upgrade in flight.
- **F4** Initial Wi-Fi scan fired on page open (previously relied on NM's
  2-minute background scan interval).
- **F5** Signal-strength icon updates live on scan events (was only updated
  when the row was rebuilt).
- **F6** Scan button accessible label.
- **F7** Signal-strength and security-lock icons get accessible labels with
  localized descriptions (excellent/good/fair/weak; password protected).
- **F8** Wi-Fi password minimum length check (8 chars) before NM
  add-and-activate round-trip.

### bluetooth / power_lock / sound

- **G1** Pairing in-flight guard prevents double-tap → `AlreadyInProgress`
  error toast on successful pairings.
- **G2** Bluetooth device-type icon gets accessible label.
- **G3** `_cleanup` calls `self._bt.teardown()` (B2) and null-checks bt
  in `_refresh_devices` to close the navigation-race crash window.
- **G4** Power-profile reconciliation: `_updating_profile` flag blocks
  re-entry when `set_selected` fires `notify::selected` during out-of-band
  daemon changes. No more redundant D-Bus calls + full apply-settings runs.
- **G5** Lid-action revert guarded by `_reverting_lid` — declining polkit
  no longer triggers a second pkexec for the original value.
- **G6** suspend_timeout clamped against lock_timeout with user toast.
  Machine no longer suspends before it locks.
- **G7** `_power_helper.teardown()` on unmap.
- **G8** `_refresh` (8 sync pactl calls) moved to a worker thread; UI
  updates via `GLib.idle_add`. No more 40-second main-thread stalls when
  pipewire-pulse is restarting.
- **G9** Four pactl helpers (`_get_default_sink`, `_get_default_source`,
  `_get_volume`, `_get_mute`) now catch `OSError` — OOM under pressure no
  longer crashes the settings window.
- **G10** Volume / refresh debounce timers cancelled on unmap.
- **G11** Mute-toggle and sink/source-select handlers moved to worker
  threads (slider drag was already debounced in round 2).

### users / appearance / panel / default_apps

- **H1** Password change moved to worker thread: `_hash_password` (openssl,
  up to 10 s) + `SetPassword` D-Bus call (up to 5 s) no longer freeze the
  UI for up to 15 seconds. Apply button disabled during the operation.
- **H2** `_on_name_activate` and `_on_autologin_set` worker-threaded;
  `_autologin_updating` guard preserved for the failure-revert path.
- **H3** Dark-mode switch disabled and uncaptured when High Contrast forces
  dark. Fixes latent bug where HC-disable flipped to light unexpectedly
  because `theme="light"` was quietly written while HC was active.
- **H4** Wallpaper tiles get accessible labels (Orca announces each
  wallpaper by name).
- **H5** "Add picture" button gets accessible label.
- **H6** Four panel module-reorder icon buttons get accessible labels.
- **H7** Pinned-app command normalized with shlex: `Exec` entries with
  spaces in paths are re-quoted before being written to waybar's on-click.
- **H8** `xdg-mime default` (default_apps) moved to worker thread.

## Deferred items (not addressed in round 3)

| ID | Item | Reason |
|----|------|--------|
| A14 | Activate GTK `HighContrast` theme when HC flag set | Uncertain whether theme is installed in the image; left `# TODO` comment. |
| B15 | BlueZHelper `_find_adapter` sync call at init | Bounded 5 s; larger refactor deferred. |
| DBUS-9 | BlueZ `PropertiesChanged` subscribes to `path=None` (RSSI churn) | Would need a debounce on publish — deferred as perf rather than correctness. |
| DBUS-10 | NM service restart recovery | Requires `notify::nm-running` handler and device-ref reset — larger patch. |
| KBD FlowBox | Double tab-stop on accent/wallpaper grids | Structural change; deferred as ergonomic rather than correctness. |
| DISP-1 | Display StatusPage doesn't refresh on hotplug | Needs rebuild-on-hotplug plumbing. |
| DISP-2 | Multi-output revert dialogs share single timer slot | Uncommon 2+ monitor edge case; per-output dict refactor deferred. |
| DISP-3 | `_apply_resolution` swallows wlr-randr exit code | Medium risk; defer until we can test multi-monitor flows. |
| APPS-1 | Font-size live-updates the settings window itself | Round-2 deferred, still deferred. |
| USER-3 | Current-password field for defense-in-depth password change | UX change; deferred. |
| PANEL-1 | Edge change icon direction refresh | Auditor retracted this on re-read. |

## Cross-agent corroboration

Every HIGH finding listed above was confirmed by at least one agent, and
several (about.py `_restart` dead code; mouse pointer-speed draw_value;
network `_connect_in_flight` gap in password path; non-atomic config writes
in apply-settings) were caught independently by 3+ agents, which is what
motivated treating them as definite bugs rather than speculative findings.

## Verification

- All 26 Python files pass `python -m py_compile`.
- No file was touched by more than one fix agent (file-conflict-domain
  partitioning).
- 19 files changed, +1159 / −373 lines.

## Commit

Round 3 landed as a single commit: `fix(settings): round-3 production-readiness sweep`.
