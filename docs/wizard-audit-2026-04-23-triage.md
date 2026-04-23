# Wizard Audit Triage — 2026-04-23

14-agent audit (state, thread, err, disk, bootc, UX, validation, i18n, mem,
quality, log, resume, handoff, edge). ~120 findings total; ~40 HIGH. This
doc triages them into priority tiers for a focused fix pass.

## Tier 1 — Data loss / security / crash

**F-VALID-1 HIGH (line 2262-2269, 2965-2970):** `fullname` written unsanitized
into `/etc/passwd` GECOS — a value containing `:` or `\n` can inject a new
UID 0 account. Fix: reject control chars and `:` in `_validate_account`.

**F-STATE-3 HIGH (line 3515-3527):** After fatal install failure, `_progress_go_back`
returns user to Confirm. Passwords were cleared on Install click. Clicking
Install again re-reads empty entries → `_hash_password("")` → user account
with hash-of-empty-string. Fix: cache `_setup_hashed_password` and skip
re-hash if plaintext is empty; or route `_progress_go_back` to PAGE_ACCOUNT.

**F-ERR-4 HIGH (line 2507-2517):** `findmnt` TimeoutExpired swallowed with
"No mounts found". Proceeding to `wipefs -af` on a possibly-mounted disk.
Fix: separate CalledProcessError (safe) from TimeoutExpired (return error).

**F-DISK-1 HIGH (line 577-605):** `boot_disk` detection fails on live ISOs
where `/` is overlay and `/sysroot` is unset. USB stick appears in drive list.
Fix: fall back to scanning `/run/initramfs/live`, `/run/media/*`,
`iso9660` mounts, and fail closed (no drives shown) rather than open.

**F-DISK-3 HIGH (line 3495-3526):** No "are you sure?" gate before `wipefs`.
Stray Enter on Confirm jumps to install. Fix: require a `GtkCheckButton`
"I understand this erases {drive}" to enable the Install button.

**F-HANDOFF-1 HIGH (line 3279-3281):** `install-config.json` written with
`Path.write_text` — no fsync, no tmp+rename. Partial JSON after power loss
crashes first-boot under `set -euo pipefail`.

**F-HANDOFF-2 HIGH (line 3279):** `install-config.json` created with default
umask (0644) — username + disk layout world-readable.

**F-HANDOFF-4 HIGH (first-boot:32-35):** `json.load` with no try/except.
Partial JSON (see F-HANDOFF-1) crashes the service; `setup-done` never
written → boot loop.

**F-BOOTC-1 HIGH (line 2776-2779):** `os.unlink(log_path)` always runs —
even on failure. User loses the only record of registry/mkfs/network errors.

**F-BOOTC-3 HIGH (line 2685-2691):** `/ostree` tmpfs mount happens OUTSIDE
the try block. If mount fails on a retry (stacked from previous run),
function returns without the finally umount running.

**F-BOOTC-8 HIGH (line 2633+):** No pre-install `shutil.disk_usage` check.
Install proceeds on 4 GB disk; bootc fails deep into the pull with
opaque ENOSPC.

**F-RESUME-2 HIGH:** No `atexit`, no SIGTERM handler, no `close-request`
handler. Wizard crash/OOM/close mid-install leaves `/ostree` tmpfs-masked
and target partitions mounted. Next launch fails mysteriously.

**F-RESUME-3 HIGH:** Retry after failed install doesn't handle the case
where `/ostree` is already tmpfs from the previous attempt. `check=True`
raises CalledProcessError → misleading "Failed to prepare install environment".

**F-VALID-2 HIGH (line 2286-2291, 489-503):** No maximum password length.
10 MB paste could OOM a 2 GB Chromebook at `openssl passwd`.

**F-VALID-3 HIGH (line 1320-1324, 2435-2443):** Custom swap size accepts
arbitrarily huge values when drive size parse fails (drive_gb=None → no
upper bound check).

## Tier 2 — Accessibility (primary user is vision-impaired)

**F-UX-1 HIGH (line 798-875):** Language list uses `SelectionMode.NONE` +
`GestureClick` — keyboard-inaccessible. A blind user cannot change language
on step 1.

**F-UX-2 HIGH (line 1173-1177, 1914-1916):** Wi-Fi rows mouse-only. Cannot
connect to Wi-Fi with keyboard. Dead end if no Ethernet.

**F-UX-3 HIGH (whole file):** Zero AT-SPI labels across the entire wizard.
Orca announces entries as "password entry" with no field name.

**F-UX-4 HIGH (line 668-675, 2405-2410):** `_status_label` not a live
region → Orca doesn't announce validation failures.

**F-UX-5 HIGH (line 690-694, 2118-2125):** No `set_default_widget` or
`set_activates_default` on entries — Enter doesn't advance pages.

**F-UX-6 HIGH (line 1541-1554):** No spinner/heartbeat during the
20-30 minute install. Vision-impaired user has no way to tell if the
install has frozen.

**F-UX-9 MED (line 73-421):** CSS hardcodes pixel font sizes and dark
colors — ignores user font scale and high-contrast preferences.

**F-UX-12 HIGH (line 2114-2116, 2260-2303):** Validation failure leaves
focus on Next; the offending field is never re-focused.

**F-EDGE-1 HIGH (line 1658-1662, 1791-1797):** No Wi-Fi adapter → empty
"Scanning for networks..." label forever. Section should hide or say
"No Wi-Fi adapter detected."

**F-EDGE-2 HIGH (line 2319-2328):** When `_nm_client is None`, Network
page is auto-skipped and can't be reached via Back — user hits Confirm
"Network not available" with no escape.

**F-EDGE-9 MED (line 1275-1290):** Multi-disk default selection is
non-deterministic (alphabetic) — eMMC+SD user could wipe SD thinking
it's eMMC. Fix: sort by (removable, transport, size desc).

## Tier 3 — Memory / performance for 2 GB

**F-MEM-1/F-MEM-14 HIGH (line 3448-3463):** `_run_logged` accumulates
unbounded `output_lines` list. bootc + setfiles emit tens of thousands
of lines → multiple MB of dead memory. Fix: `collections.deque(maxlen=200)`.

**F-MEM-2 MED:** All 8 pages built eagerly at `__init__` (~10-20 MB).
Lazy-build progress + apps is the biggest single win. [Deferred — larger
refactor.]

## Tier 4 — Errors / logging / validation

**F-ERR-1 HIGH (line 3627-3630):** Blanket `except Exception as exc:
err = f"Unexpected error: {exc}"` — loses traceback.

**F-ERR-2 HIGH (line 3639-3642):** `setenforce 1` in finally has no
try/except — can mask original install error.

**F-ERR-3 HIGH (line 2669-2678):** `bootc status` parse uses broad
`except Exception` — one generic message for JSON/subprocess/missing-key
failures.

**F-LOG-1 HIGH (line 1572, 3481):** Install log never persisted to disk
— lives only in Gtk.TextBuffer which vanishes at reboot. Temp files
unlink'd immediately.

**F-LOG-2 HIGH (line 3666-3691):** On failure, log revealer is collapsed,
error truncated to 80 chars, no path to a saved log.

**F-VALID-4 MED (line 429, 2305-2317):** Hostname regex permits uppercase
— hostnamed lowercases silently, creating inconsistency.

**F-VALID-15 HIGH (line 2295-2302):** Root password has no min-length
check; `x` is accepted (user password requires ≥6).

**F-I18N-1 HIGH (~20 sites):** Step error strings returned as untranslated
f-strings — land in the step label text.

**F-I18N-2 HIGH (line 2123, 3521):** `_set_status(f"...")` untranslated.

**F-I18N-3 HIGH (line 1993-2020):** Raw NM `str(exc)` interpolated into
translated wrapper.

## Tier 5 — Code quality

**F-QUAL-1 LOW (line 2057-2060):** Dead `_tr` helper.
**F-QUAL-2 LOW (line 32):** Unused `time` import.
**F-QUAL-3 MED:** Dead "skippable" error-behavior path.
**F-QUAL-4 MED (line 891-895):** No-op retranslation lambda for
keyboard-layout label.
**F-QUAL-5 MED (line 2977-3029):** Duplicated wheel-group mutation for
/etc/group and /etc/gshadow.
**F-QUAL-7 LOW (line 2728, 3423):** `import tempfile` inside function
bodies.
**F-QUAL-14 LOW (line 1666-1668):** `_connectivity_retries` lazy-init via
hasattr.
**F-QUAL-18 LOW (line 3556-3568):** Step list mixes literal + .append.

## Deferred (larger refactors, flag for later)

- F-MEM-2: Lazy page construction (~10-20 MB but invasive).
- F-QUAL-16: Split `_step_configure_user` (245 lines, 7 concerns).
- F-QUAL-17: Split `_step_install_system` (233 lines, 4 phases).
- F-RESUME-8: "Previous install did not complete" resume detection.
- F-BOOTC-5: Conditional systemd-boot vs grub bootloader selection.
- F-BOOTC-6: wlopm remount-rw retry after bootc fsfreeze.
- On-screen keyboard (wvkbd not in Fedora 43 repos).
- Screen magnifier for labwc.
