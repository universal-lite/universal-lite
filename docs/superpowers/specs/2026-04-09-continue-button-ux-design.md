# Continue Button UX & Button Polish — Design Spec

## Problem

The current Continue button during `bootc install to-filesystem` has two issues:

1. **Disappearing button bug.** The button shows immediately when bootc starts,
   but if bootc exits on its own (`proc.poll() is not None`), the loop breaks
   and the button vanishes before the user can click it.  Ironically, process
   exit is the most reliable completion signal we have.

2. **No guidance on when to click.**  The button appears at the start of a
   multi-minute process with no indication of whether it's safe to click yet.

Additionally, the button CSS (and all wizard buttons) feel rough compared to
a production Adwaita dark app — missing pressed states, transitions, shadows,
and disabled styles.

## Solution

### Continue Button Behavior

Three states during the "Installing system" step:

| State | Trigger | Appearance | Label |
|-------|---------|------------|-------|
| **Disabled** | bootc process starts | Greyed out, visible | "Waiting for install..." |
| **Enabled** | bootc exits OR 10-minute timeout | Red destructive style, pop-in animation | "Continue" |
| **Hidden** | User clicks Continue and step proceeds (or step fails) | Removed | — |

**Happy path:** bootc exits cleanly → button pops from disabled to enabled →
user clicks → step proceeds to deployment directory check.

**Hang path:** bootc doesn't exit within 10 minutes → button enables via
timeout → user clicks → wizard kills the process group → step proceeds.

### Process Management

```
bootc starts → show disabled button → enter loop
  loop (every 5s):
    if proc.poll() is not None:
      enable button, continue looping (wait for user click)
    if 10-minute timeout expired and button still disabled:
      enable button, continue looping (wait for user click)
    if continue_event is set:
      if proc still running → SIGTERM process group, wait, SIGKILL fallback
      break
  1-hour hard deadline → kill proc, break (safety net)
```

Key differences from current code:

- **Button starts hidden→disabled, not hidden→visible.**  No premature click.
- **Process exit enables the button instead of breaking the loop.**  The most
  reliable signal drives the UX instead of being thrown away.
- **Kill only fires if proc is still alive when user clicks.**  On the happy
  path, nothing is killed.

### Pop-In Animation

When the button transitions from disabled to enabled, apply a CSS animation:
`@keyframes pop-in` — opacity 0→1, scale 0.95→1, over 300ms ease-out.
Add the `pop-in` class via `GLib.idle_add` when enabling.

### Button CSS Refinement

All three button classes (`create-button`, `destructive-button`, `back-button`)
get refined to match Adwaita dark theme with ChromeOS warmth:

**Shared properties (inherit from `window` or a base):**
- `font-family: "Roboto", sans-serif` (already set on window)
- `font-size: 16px` (down from 18 — Adwaita standard)
- `padding: 12px 32px` (generous, ChromeOS feel — keep)
- `border-radius: 10px` (ChromeOS rounds a touch more than Adwaita's 6px)
- `transition: background 200ms ease, opacity 200ms ease, box-shadow 200ms ease`
- `min-height: 36px`
- `border: none`

**`create-button` (suggested action / blue):**
- Normal: `background: #3584e4`, `box-shadow: 0 1px 2px rgba(0,0,0,0.3)`
- Hover: `background: #62a0ea`
- Active/pressed: `background: #1c71d8`, `box-shadow: none` (pressed in)
- Disabled: `background: #3d3d3d`, `color: #888888`, `box-shadow: none`

**`destructive-button` (red / cautionary):**
- Normal: `background: #c01c28`, `box-shadow: 0 1px 2px rgba(0,0,0,0.3)`
- Hover: `background: #e01b24`
- Active/pressed: `background: #a51d2d`, `box-shadow: none`
- Disabled: `background: #3d3d3d`, `color: #888888`, `box-shadow: none`

**`back-button` (ghost / flat):**
- Normal: `background: transparent`, `color: #aaaaaa`
- Hover: `background: rgba(255,255,255,0.08)`, `color: #dddddd`
- Active/pressed: `background: rgba(255,255,255,0.04)`, `color: #bbbbbb`
- No shadow in any state.

All button `label` selectors inherit color from the button state — no need
for separate `label` rules if we use `color` on the button itself.  Keep
explicit `label` rules only where GTK4 ignores the parent color (test and
remove if not needed).

### Translations

New string: `"Waiting for install..."` — add to all 22 `.po` files and
recompile `.mo` files.  The existing `"Continue"` string stays as-is.

## What Stays the Same

- The deployment directory safety check after bootc (catches premature clicks)
- The 1-hour hard deadline
- The log reader thread and "Show details" panel
- All other progress page buttons (Back, Skip, Retry, Reboot)
- The step runner architecture

## What Gets Removed

- The disk I/O monitoring code (already removed in prior commit)
- The immediate `set_visible(True)` on bootc start
