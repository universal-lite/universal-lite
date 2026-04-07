# Universal-Lite

A lightweight, auto-updating Linux desktop for old x86_64 Chromebooks and low-end laptops.
Built on [Universal Blue](https://universal-blue.org/) — the image updates itself daily and
rolls back automatically if anything goes wrong. No package manager, no manual maintenance.

## Is this for you?

Universal-Lite is a good fit if you have:

- An old Chromebook or low-end x86_64 laptop sitting around
- At least 2 GB of RAM
- Either UEFI firmware already, or a Chromebook you're willing to flash with [MrChromebox](https://mrchromebox.tech) UEFI Full ROM

It runs a minimal Wayland desktop (labwc + waybar) that's designed to feel familiar to
Chromebook users — bottom panel, Chrome browser, Chromebook keyboard shortcuts all work.
Apps beyond what's built in install from Flathub.

> **Chromebook note:** Flashing UEFI firmware requires removing the write-protect screw.
> See [MrChromebox](https://mrchromebox.tech) for device-specific instructions.
> x86_64 only — ARM Chromebooks are not supported.

## Install

### USB installer (recommended)

The recommended path for Chromebooks and low-end laptops. You need:

- A second Linux machine to prepare the USB
- A USB drive — **16 GB minimum** (holds the live environment and pre-downloaded apps)
- A target drive in the machine — eMMC, SD card, second USB, etc. — **16 GB minimum** (32+ GB recommended)

**Step 1 — Get the image.** Build locally or download the latest from
[GitHub Actions → build-disk → Artifacts](../../actions/workflows/build-disk.yml):

```bash
just build-raw
```

**Step 2 — Flash the image to a USB drive:**

```bash
lsblk   # identify the USB drive — double-check before writing
sudo dd if=output/raw/disk.raw of=/dev/sdX bs=4M status=progress conv=fsync
```

**Step 3 — Boot from USB.** The installer wizard launches automatically.
It walks through selecting a target drive, creating your user account,
choosing apps, and writing the system to disk via `bootc install to-disk`.

**Step 4 — Reboot.** Remove the USB when prompted. The system boots into
the login screen ready to use.

### ISO installer (Anaconda)

For machines with 4+ GB of RAM, you can use the standard Anaconda installer:

```bash
just build-iso
```

Flash the ISO to a USB drive and boot from it. Anaconda handles partitioning,
user creation, and timezone setup. A kickstart script automatically rebases the
installed system to the Universal-Lite image.

### Switch from an existing Fedora Atomic system

If the machine already runs Silverblue, Kinoite, Bazzite, Bluefin, Aurora, or any other
Fedora Atomic / Universal Blue image, you can switch without reflashing.

**On Fedora 42+ / Universal Blue (bootc):**

```bash
sudo bootc switch ghcr.io/universal-lite/universal-lite:latest
```

**On older systems using rpm-ostree:**

```bash
# Step 1 — rebase to the unsigned image and reboot
rpm-ostree rebase ostree-unverified-registry:ghcr.io/universal-lite/universal-lite:latest
systemctl reboot

# Step 2 — after reboot, move to the signed image
rpm-ostree rebase ostree-image-signed:docker://ghcr.io/universal-lite/universal-lite:latest
systemctl reboot
```

Step 1 alone works fine if you don't need signature verification. The signed image
verifies the container signature on every update.

### After install

Once booted, the system manages itself. Daily image builds are pulled automatically
via the unified updater (uupd), which handles both system images and Flatpak apps.
If an update ever causes a problem, the previous image is always available in the boot
menu — select it to roll back.

## Installer wizard

The USB installer boots into a full labwc desktop session running the setup wizard.
It walks through seven steps:

1. **Network** — connect to WiFi if needed (skipped automatically if already online)
2. **Disk** — choose target drive, filesystem (ext4/xfs/btrfs), and memory management strategy
3. **Account** — full name, username, and password
4. **System** — timezone, administrator (sudo), optional root password
5. **Apps** — choose which Flatpak apps to install (pre-downloaded on the USB, copied via rsync)
6. **Confirm** — review everything before applying
7. **Progress** — live status as `bootc install to-disk` writes the system, then configures the user account, copies network settings, installs apps, and sets up memory management

Errors during installation are handled per-step: fatal errors (partitioning failure) send
you back to change settings, retryable errors offer a retry button, and skippable errors
(e.g. a single app) let you continue without blocking the install.

After setup completes the system reboots into the login screen.

### Memory management options

The wizard offers two memory strategies on the Disk page:

| Option | How it works | Best for |
|--------|-------------|----------|
| **zRAM** (default) | Compresses swap in RAM using zstd. 1.25x RAM, `vm.swappiness=180`. | Most machines — fast, no disk wear |
| **zswap + encrypted disk swap** | Compressed RAM cache that spills to an encrypted swap file on disk when full. Configurable swap file size (2/4/8 GB). | Very low RAM (2 GB) — keeps more apps open at the cost of some disk I/O |

The encrypted disk swap uses a random key generated at each boot — the swap contents
don't survive a reboot and aren't readable offline.

## What's included

| Component | Choice | Why |
|-----------|--------|-----|
| Base image | `ghcr.io/ublue-os/base-main:latest` | Lightest Universal Blue base — no bundled DE |
| Compositor | `labwc` | wlroots-based, minimal memory footprint |
| Panel | `waybar` | Chromebook-style shelf (bottom by default) |
| App launcher | `fuzzel` | Searchable launcher via Super+Space |
| App menu | `labwc` built-in | Categorized menu from waybar "Apps" button |
| Browser | Google Chrome | Familiar to Chromebook users, installed via Flatpak on first boot |
| File manager | `Thunar` | Lightweight, thumbnail support |
| Terminal | `foot` | GPU-accelerated, minimal |
| Greeter | `greetd` + custom GTK4 greeter | Login screen via `cage` kiosk |
| Notifications | `mako` | Low-overhead notification daemon |
| Screen lock | `swayidle` + `swaylock` | Locks after 5 min idle, screen off at 10 min |
| Power | `power-profiles-daemon` | Battery/performance profiles for laptops |
| Audio | `pipewire` + `wireplumber` | Modern audio stack with PulseAudio compatibility |
| Bluetooth | `bluez` | Pair devices via system tray |
| Printing | `CUPS` | Local and network printers |
| App store | `Bazaar` (Flatpak, first-boot) | Browse and install apps from Flathub |
| Settings | `universal-lite-settings` | Full system settings app (GTK4) — 15 pages covering display, network, input, power, accessibility, and more |
| Multimedia | RPM Fusion + GStreamer | Codec support out of the box |

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
| `Super+Space` | Search for apps |
| `Super+L` | Lock screen |
| `Super+E` | File manager |
| `Super+Escape` | Task manager (htop) |
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
| Images | Ristretto |
| Videos | mpv |
| Audio | mpv |
| Web links | Chrome |

### Settings app

`Super+,` or the panel tray opens `universal-lite-settings`, a full system settings
app built with GTK4:

| Page | What it configures |
|------|--------------------|
| Appearance | Theme (light/dark), accent color, font size, wallpaper |
| Display | Scale, resolution, refresh rate, night light |
| Network | WiFi scanning/connection, hidden networks, wired status |
| Bluetooth | Device discovery, pairing, connect/disconnect |
| Panel | Position, density, module layout (drag-and-drop), pinned apps |
| Mouse & Touchpad | Pointer speed, natural scrolling, tap to click, acceleration |
| Keyboard | Layout, repeat rate/delay, caps lock behavior, custom shortcuts |
| Sound | Output/input device, volume, mute |
| Power & Lock | Lock/display-off/suspend timeouts, power profile, lid close action |
| Accessibility | Large text, cursor size, high contrast, reduce motion |
| Date & Time | Timezone, NTP toggle, 12/24-hour clock |
| Users | Display name, password, automatic login |
| Language & Region | System locale, regional formats |
| Default Apps | Browser, file manager, terminal, editor, image/PDF/media/email |
| About | System info, hardware, disk usage, update check |

Changes apply immediately without restarting anything.

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

Every push to `main` and a daily schedule build and publish the OCI image to
`ghcr.io/universal-lite/universal-lite`. Images are signed with
[cosign](https://github.com/sigstore/cosign).

To set up signing on a fresh fork:

```bash
COSIGN_PASSWORD='' cosign generate-key-pair
gh secret set SIGNING_SECRET < cosign.key
```

Raw and ISO disk images are built on manual dispatch via the
[disk image workflow](../../actions/workflows/build-disk.yml).
Dependencies are kept current by Dependabot and Renovate.

## Project layout

```
Containerfile                              # Image build definition
build_files/build.sh                       # Package installation and configuration
disk_config/
  disk.toml                                # Raw disk image config (10 GiB root)
  iso.toml                                 # ISO config (Anaconda + bootc switch kickstart)
tests/                                     # Unit tests for settings store, event bus
files/
  etc/
    greetd/                                # Login greeter config (greetd)
    sysctl.d/                              # Memory tuning (swappiness, etc.)
    systemd/
      zram-generator.conf                  # zRAM swap config (default memory strategy)
      system/
        universal-lite-first-boot.service  # Post-install setup (runs once on first boot)
        universal-lite-flatpak-setup.service    # Fallback Flatpak install from network
        universal-lite-zswap.service            # Configure zswap parameters at boot
        universal-lite-swap-init.service        # Create /var/swap on first boot (zswap path)
        universal-lite-encrypted-swap.service   # Activate encrypted swap via dm-crypt
    xdg/
      foot/                                # Terminal config
      fuzzel/                              # App launcher config
      gtk-3.0/, gtk-4.0/                   # GTK theme defaults
      labwc/                               # Compositor config, keybindings, autostart
      mako/                                # Notification daemon config
      swaylock/                            # Lock screen config
  usr/
    bin/
      universal-lite-greeter               # Custom GTK4 login greeter (Python)
      universal-lite-power-menu            # Power menu (logout/reboot/shutdown)
      universal-lite-settings              # Settings app launcher
      universal-lite-setup-wizard          # Installer wizard (Python/GTK4)
    lib/
      bootc/install/
        00-universal-lite.toml             # bootc install config
      universal-lite/settings/             # Settings app Python package
        pages/                             # 15 settings pages (appearance, display, etc.)
        app.py, window.py, base.py         # App shell, sidebar, base page class
        settings_store.py, events.py       # Persistent store + event bus
    libexec/
      universal-lite-apply-settings        # Applies settings changes to compositor/panel
      universal-lite-brightness            # Brightness control helper
      universal-lite-encrypted-swap        # dm-crypt swap setup script
      universal-lite-first-boot            # First-boot config (swap, greeter prefill)
      universal-lite-flatpak-setup         # Flatpak app installer (runs at boot)
      universal-lite-greeter-launch        # Cage kiosk wrapper for greeter
      universal-lite-greeter-setup         # Detects users, sets greetd initial session
      universal-lite-lid-action            # Lid close action helper
      universal-lite-menu                  # labwc pipemenu generator
      universal-lite-session               # Wayland session startup
      universal-lite-swap-init             # Creates /var/swap at configured size
      universal-lite-volume                # Volume control helper
      universal-lite-wizard-session        # Wizard-mode labwc session script
    share/
      applications/                        # .desktop files + mimeapps.list
      backgrounds/universal-lite/          # Bundled wallpapers
      polkit-1/actions/                    # Polkit policy for lid action
      themes/Universal-Lite/               # Custom GTK theme (labwc openbox-3 compat)
      universal-lite/defaults/             # Default settings (JSON)
      wayland-sessions/                    # Session .desktop entries for greetd
.github/workflows/
  build.yml                                # OCI image build + sign + push
  build-disk.yml                           # Raw and ISO artifact builds
```
