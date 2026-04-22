# Universal-Lite

A lightweight, auto-updating Linux desktop for old x86_64 Chromebooks and
low-end laptops. Built on [Universal Blue](https://universal-blue.org/) —
the image updates itself daily and rolls back automatically if anything
goes wrong. No package manager, no manual maintenance, no surprises.

Designed for the handful of real-world cases where this combination
actually matters:

- **2 GB Chromebooks** that ChromeOS has dropped from updates
- **Vision-impaired or non-technical users** who need a simple, stable
  desktop that looks and feels like ChromeOS (bottom panel, rounded
  windows, big clear labels, familiar keyboard shortcuts)
- **Handing a laptop to a relative** without also signing up to maintain it

## Is this for you?

You're a good fit if you have:

- An old Chromebook or low-end x86_64 laptop sitting around
- At least 2 GB of RAM
- Either UEFI firmware already, or a Chromebook you're willing to flash
  with [MrChromebox](https://mrchromebox.tech) UEFI Full ROM

The desktop runs labwc (wlroots compositor) + waybar + our own Adwaita-
styled settings app. Chrome runs from Flathub so every user gets the
same browser they're used to. Apps beyond the built-ins install from
Flathub via Bazaar.

> **Chromebook note:** Flashing UEFI firmware requires removing the
> write-protect screw. See [MrChromebox](https://mrchromebox.tech) for
> device-specific instructions. x86_64 only — ARM Chromebooks are not
> supported.

## Install

### .raw USB installer (recommended for Chromebooks under 4GB of ram)

You need:

- A second Linux machine (or VM) to prepare the USB
- A USB drive, **16 GB minimum** (holds the live environment and
  pre-downloaded Flatpaks)
- A target drive in the machine, **16 GB minimum** (32+ GB recommended)

**Step 1 — Download the image.** Open
[GitHub Actions → Build disk images](../../actions/workflows/build-disk.yml),
click the most recent successful run, and download the
**universal-lite-raw** artifact from the Artifacts section at the
bottom of the page. Unzip it — you'll get a `disk.raw` file a few GB
in size.

**Step 2 — Flash the image to a USB drive:**

```bash
lsblk   # identify the USB drive — double-check before writing
sudo dd if=disk.raw of=/dev/sdX bs=4M status=progress conv=fsync
```

Or use [Impression](https://flathub.org/apps/io.gitlab.adhami3310.Impression)
if you'd rather not stare at `dd`.

**Step 3 — Boot from USB.** The installer wizard launches automatically.
It walks through network, target disk, account, timezone, apps, and a
final confirmation before `bootc install to-disk` writes the system.

**Step 4 — Reboot.** Remove the USB when prompted. The login screen comes
up with your chosen username pre-filled.

### ISO installer (Anaconda)

For machines with 4+ GB of RAM or anything where the raw USB path is
inconvenient, grab the **universal-lite-anaconda-iso** artifact from
the most recent successful run of
[Build disk images](../../actions/workflows/build-disk.yml), unzip it,
and flash the `.iso` file inside to a USB drive the same way as the
raw image.

Anaconda handles partitioning, user creation, and timezone setup on
boot. A kickstart `%post` rebases the installed system to the published
Universal-Lite image, seeds `/var/lib/universal-lite/install-config.json`
with sensible defaults (zram memory strategy, anaconda-created UID 1000
as the primary user), and triggers the same first-boot flow the USB
path uses.

After first login the flatpak-install service pulls Chrome and Bazaar
from Flathub.

### Switch from an existing Fedora Atomic system

If the machine already runs Silverblue, Kinoite, Bazzite, Bluefin, Aurora,
or any other Fedora Atomic / Universal Blue image, you can rebase without
reflashing.

**On Fedora 42+ / Universal Blue (bootc):**

```bash
sudo bootc switch ghcr.io/universal-lite/universal-lite:latest
sudo systemctl reboot
```

**On older systems using rpm-ostree:**

```bash
# Unsigned rebase (works everywhere)
rpm-ostree rebase ostree-unverified-registry:ghcr.io/universal-lite/universal-lite:latest
systemctl reboot

# Then, for signature verification on subsequent updates:
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/universal-lite/universal-lite:latest
systemctl reboot
```

### After install

The system manages itself. Daily image builds publish to
`ghcr.io/universal-lite/universal-lite:latest` and the unified updater
(`uupd`) pulls them on a timer, handling both the bootc image and
Flatpak apps. If an update ever causes a problem, the previous image is
always available in the boot menu — select it to roll back.

## Installer wizard

The USB installer boots into a labwc session running the setup wizard
fullscreen. It walks through:

1. **Network** — connect to WiFi if needed (skipped if already online)
2. **Disk** — target drive, filesystem (ext4/xfs/btrfs), and memory
   management strategy
3. **Account** — full name, username, password
4. **System** — timezone, sudo-capable flag, optional root password
5. **Apps** — Flatpaks to install (pre-downloaded on the USB, copied
   to the target via `rsync`)
6. **Confirm** — review every choice before anything is written
7. **Progress** — live status through `bootc install to-disk`, account
   creation, network carryover, Flatpak install, memory setup

Errors are handled per step: fatal errors (partitioning failures) return
you to change settings, retryable errors show a retry button, and
skippable errors (a single app failing to install) let you continue.

### Memory management

Two strategies; the wizard asks at install time and you can switch later
without reinstalling.

| Option | How it works | Best for |
|--------|-------------|----------|
| **zram** (default) | Compressed in-RAM swap via `zram-generator`. Sized at 1.25× RAM, capped at 16 GB. | Most machines — fast, no disk wear |
| **zswap + encrypted disk swap** | Compressed RAM cache that spills to a `dm-crypt`-encrypted swap file when RAM + zram fill. Configurable swap file size. `vm.swappiness=100` to favor page-out. | 2 GB Chromebooks running heavy apps |

The encrypted disk swap uses `aes-xts-plain64` with a 512-bit key read
from `/dev/urandom` at each boot. The key lives only in kernel memory —
swap contents are unrecoverable across a power cycle.

### Switching strategy after install

If you picked wrong at install time, the `ujust` recipes let you swap
without reinstalling:

```bash
ujust swap-status    # show the configured strategy and active swap devices
ujust toggle-swap    # switch between zram and zswap; prompts for swap
                     # file size when moving to zswap, then asks about
                     # rebooting to activate
```

The toggle is functionally equivalent to reinstalling with the other
option selected — writes the same config files, enables/disables the
same services, installs the same `vm.swappiness` tuning. Kernel-level
changes take effect on the next reboot.

## What's included

| Component | Choice | Why |
|-----------|--------|-----|
| Base image | `ghcr.io/ublue-os/base-main:latest` | Lightest Universal Blue base — no bundled DE |
| Compositor | `labwc` | wlroots-based, minimal memory footprint |
| Panel | `waybar` | Chromebook-style shelf (bottom by default) |
| App menu | `universal-lite-app-menu` (in-process GTK4) | Token-aware search, categorized launcher, triggered by Super+Space or the panel launcher |
| Browser | Google Chrome (flatpak), Firefox (rpm) | Familiar to Chromebook users, installed via Flatpak on first boot |
| File manager | `Thunar` | Lightweight, thumbnail support |
| Terminal | `ptyxis` | libadwaita-native; inherits the system theme + accent automatically |
| Greeter | `greetd` + custom GTK4 greeter | Login screen via `cage` kiosk, palette-synced to the user's theme + accent |
| Notifications | `mako` | Low-overhead notification daemon |
| Screen lock | `swayidle` + `swaylock` | Configurable timeouts from the Settings app |
| Power | `power-profiles-daemon` | Battery/performance profiles for laptops |
| Audio | `pipewire` + `wireplumber` | Modern audio stack with PulseAudio compatibility |
| Bluetooth | `bluez` | Pair devices via Settings app or system tray |
| Printing | `CUPS` | Local and network printers |
| App store | `Bazaar` (Flatpak, first-boot) | Browse and install apps from Flathub |
| Settings | `universal-lite-settings` | Full libadwaita settings app — 15 pages, responsive layout, 22 languages |
| Night light | `gammastep` + per-user systemd timer | Reconciles every 15 min during a configured schedule |
| Multimedia | RPM Fusion + GStreamer + JPEG-XL/WebP loaders | Codec + image-format support out of the box |

### Keyboard shortcuts

#### Chromebook top-row keys

| Key | Action |
|-----|--------|
| Volume Up / Down / Mute | Adjust or mute audio |
| Brightness Up / Down | Adjust screen brightness |
| Fullscreen (F4) | Toggle fullscreen |

#### Search key (Super)

| Shortcut | Action |
|----------|--------|
| `Super+Space` | App menu (search / browse apps) |
| `Super+L` | Lock screen |
| `Super+E` | File manager |
| `Super+Escape` | Task manager (xfce4-taskmanager) |
| `Super+,` | Settings |
| `Super+Up` | Maximize window |
| `Super+Down` | Minimize window |

#### Window management

| Shortcut | Action |
|----------|--------|
| `Alt+Tab` / `Alt+Shift+Tab` | Cycle windows |
| `Alt+[` | Snap window left |
| `Alt+]` | Snap window right |
| `Alt+F4` | Close window |
| `Ctrl+Alt+T` | Terminal |

#### Screenshots

| Shortcut | Action |
|----------|--------|
| `Print Screen` | Full screenshot to clipboard |
| `Shift+Print Screen` | Area selection to clipboard |

### Default app associations

| File type | Opens with |
|-----------|------------|
| PDFs | Evince |
| Text files | Mousepad |
| Images (JPEG/PNG/GIF/SVG/WebP/BMP/TIFF/JXL/ICO/…) | Ristretto |
| Videos | mpv |
| Audio | mpv |
| Web links | Chrome |

Defaults ship at `/etc/xdg/mimeapps.list`. Change any of them from the
Settings app's Default Apps page.

### Settings app

`Super+,` or the panel tray opens `universal-lite-settings`, a full
libadwaita settings app with an adaptive sidebar+content layout (sidebar
collapses to push-navigation below 700sp for narrow windows or Large Text
accessibility scaling).

| Page | What it configures |
|------|--------------------|
| Appearance | Light/dark theme, accent color (9 options), font size, wallpaper picker with bundled + custom wallpapers |
| Display | Scale (0.75×–2.5×), resolution, refresh rate, night light (temperature + schedule) |
| Network | WiFi scanning/connection, hidden networks, wired status |
| Bluetooth | Device discovery, pairing, connect/disconnect |
| Panel | Position, density, module layout, pinned apps |
| Mouse & Touchpad | Pointer speed, natural scrolling, tap to click, acceleration profile |
| Keyboard | Layout + variant, repeat delay/rate, Caps Lock behavior, custom shortcuts |
| Sound | Output/input device, volume, mute |
| Power & Lock | Lock/display-off/suspend timeouts, power profile, lid close action |
| Accessibility | Large text, cursor size, high contrast, reduce motion |
| Date & Time | Timezone picker, NTP toggle, 12/24-hour clock |
| Users | Display name, password, automatic login |
| Language & Region | System locale, regional formats |
| Default Apps | Browser, file manager, terminal, editor, image/PDF/media/email |
| About | System info, hardware, disk usage, update check, restore-defaults |

Changes apply immediately — no restart — and are applied consistently
across labwc (SSD titlebars), waybar (panel), mako (notifications),
swaylock, every CSD GTK app, and ptyxis (terminal, which picks up accent
and monospace-font changes through libadwaita + gsettings).

Translated to 22 languages (am, ar, de, es, fa, fr, ha, hi, it, ja, ko,
nl, pl, pt-BR, ru, sv, sw, th, tr, vi, yo, zh-Hans). Human translator
pass recommended before shipping widely — machine translation used to
seed every entry, but native speakers will spot register mismatches.

### Debug utilities

Shipped in `/usr/bin/`:

- `ul-debug-nm` — one-command diagnostic snapshot when NetworkManager
  fails to start (writes `~/nm-diag.txt` with unit state, symlink
  presence, journal breadcrumbs, dependency chain, boot timing)

## Development

### Prerequisites

- [just](https://just.systems) — task runner
- [podman](https://podman.io) — container runtime

### Build

```bash
just build          # OCI container image
just build-raw      # Raw disk image (USB installer — flash with dd)
just build-iso      # ISO installer (Anaconda — requires 4+ GB RAM)
just build-qcow2    # QCOW2 for VM testing
just convert-raw    # Convert raw → QCOW2 (for GNOME Boxes import)
```

### Test in a VM

```bash
just run-vm-qcow2   # Run QCOW2 in a browser-accessible VM (qemux/qemu)
just run-vm-raw     # Run raw image the same way
just spawn-vm       # Run with systemd-vmspawn (GUI)
```

> **GNOME Boxes:** Don't import `disk.raw` directly — Boxes may truncate it.
> Run `just convert-raw` first and import the resulting QCOW2.

### Lint

```bash
just lint           # shellcheck on all shell scripts
just check          # Justfile syntax check
```

### CI/CD

Every push to `main` and a daily schedule build and publish the OCI image
to `ghcr.io/universal-lite/universal-lite`. Images are signed with
[cosign](https://github.com/sigstore/cosign).

To set up signing on a fresh fork:

```bash
COSIGN_PASSWORD='' cosign generate-key-pair
gh secret set SIGNING_SECRET < cosign.key
```

Disk images (raw + anaconda-iso) build on manual dispatch via the
[disk image workflow](../../actions/workflows/build-disk.yml). Dependencies
are kept current by Dependabot and Renovate.

## Project layout

```
Containerfile                              # Image build definition
build_files/build.sh                       # Package install + configuration
disk_config/
  disk.toml                                # Raw disk image config (10 GiB root)
  iso.toml                                 # ISO config (Anaconda + kickstart bootc-switch)
po/                                        # Translation sources
  settings/*.po                            # 22 languages for settings + greeter
tests/                                     # Unit tests (settings store, event bus)
files/
  etc/
    gtk-3.0/, gtk-4.0/                     # Decoration-layout defaults (min/max/close)
    xdg/
      fuzzel/, labwc/, mako/,
      swaylock/, gtk-3.0/, gtk-4.0/        # App defaults
      mimeapps.list                        # Default app associations (pdf, image, etc.)
    sysctl.d/                              # Memory tuning (swappiness for zswap)
    systemd/
      zram-generator.conf                  # Default 125%-of-RAM zram config
  usr/
    bin/
      universal-lite-app-menu              # In-process GTK4 start menu
      universal-lite-greeter               # Custom GTK4 login greeter
      universal-lite-settings              # Settings app entry point
      universal-lite-setup-wizard          # Installer wizard (GTK4)
      ul-debug-nm                          # NetworkManager diagnostic snapshot
    lib/
      bootc/install/00-universal-lite.toml # bootc install config
      systemd/
        system/                            # Canonical location for our systemd units
          universal-lite-first-boot.service
          universal-lite-flatpak-install.service
          universal-lite-flatpak-update.service
          universal-lite-swap-init.service
          universal-lite-encrypted-swap.service
          universal-lite-zswap.service
          greetd.service.d/                # Drop-ins on the greetd unit
        user/                              # Per-user systemd units
          universal-lite-nightlight.{service,timer}
      universal-lite/settings/             # Settings app Python package
        pages/                             # 15 settings pages (all libadwaita)
        app.py, window.py, base.py         # App shell, sidebar, base page
        settings_store.py, events.py       # Persistent store + event bus
    libexec/
      universal-lite-apply-settings        # Reconciles settings → compositor/panel/etc.
      universal-lite-encrypted-swap        # dm-crypt swap setup
      universal-lite-first-boot            # Post-install reconciliation
      universal-lite-flatpak-setup         # Flatpak app installer
      universal-lite-greeter-launch        # Cage kiosk wrapper for greeter
      universal-lite-greeter-setup         # Detects users, sets greetd initial session
      universal-lite-lid-action            # Lid close action helper
      universal-lite-menu                  # labwc pipemenu generator
      universal-lite-nightlight            # Reconcile gammastep with night-light state
      universal-lite-session               # Wayland session startup
      universal-lite-set-memory-strategy   # zram ↔ zswap toggle helper (called by ujust)
      universal-lite-swap-init             # Creates /var/swap at configured size
      universal-lite-volume, -brightness   # Media-key helpers
      universal-lite-wizard-session        # Wizard-mode labwc session
    share/
      applications/                        # .desktop files
      backgrounds/universal-lite/          # Bundled wallpapers
      glib-2.0/schemas/
        zz-universal-lite.gschema.override # Window button layout (min/max/close)
      locale/<lang>/LC_MESSAGES/           # Compiled .mo files per language
      polkit-1/actions/                    # Polkit policy for lid action
      themes/Universal-Lite/               # labwc theme (openbox-3 compat)
      ublue-os/just/90-universal-lite.just # ujust recipes (swap toggle, etc.)
      universal-lite/
        defaults/                          # Default settings (JSON)
        palette.json                       # Single source of truth for theme colors
.github/workflows/
  build.yml                                # OCI image build + sign + push
  build-disk.yml                           # Raw + anaconda-iso artifact builds
```
