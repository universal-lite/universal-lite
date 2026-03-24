# Universal-Lite

A lightweight, auto-updating Linux desktop for old x86_64 Chromebooks and low-end laptops.
Built on [Universal Blue](https://universal-blue.org/) so it stays secure and up to date without any manual maintenance.

## Install

### What you need

- A Chromebook or laptop with UEFI firmware (Chromebooks need [MrChromebox](https://mrchromebox.tech) UEFI Full ROM)
- An SD card, USB drive, or other target storage
- A second Linux machine to flash the image

### Flash the image

Build the raw disk image (or download it from [GitHub Actions artifacts](../../actions/workflows/build-disk.yml)):

```bash
just build-raw
```

Find your target device (SD card, USB stick, etc.) — **double-check the device name with `lsblk` before flashing**:

```bash
lsblk
sudo dd if=output/disk/disk.raw of=/dev/sdX bs=4M status=progress conv=fsync
```

Insert the flashed media into the target machine and boot from it. The root partition automatically grows to fill all available space on first boot.

### Rebase from an existing Fedora Atomic system

If the machine is already running any Fedora Atomic desktop (Silverblue, Kinoite, Bazzite, Bluefin, Aurora, or another Universal Blue image), you can switch to Universal-Lite in place — no reflashing needed.

For systems using `bootc` (Fedora 42+, Universal Blue):

```bash
sudo bootc switch ghcr.io/universal-lite/universal-lite:latest
```

For older systems still using `rpm-ostree` (Fedora 41 and earlier):

```bash
rpm-ostree rebase ostree-unverified-registry:ghcr.io/universal-lite/universal-lite:latest
```

Reboot when prompted. The previous image stays available in the boot menu for rollback.

### After install

That's it. The system pulls image updates automatically from the daily builds. Rollback to the previous image is available through the boot menu if an update ever causes problems.

## First-boot setup

On first boot, a setup wizard appears asking you to create a user account (full name, username, and password). After account creation the system reboots into the normal login screen. No manual account creation is needed.

## What's included

| Component | Choice | Why |
|-----------|--------|-----|
| Base image | `ghcr.io/ublue-os/base-main:latest` | Lightest Universal Blue base — no bundled DE |
| Compositor | `labwc` | wlroots-based, minimal memory footprint |
| Panel | `waybar` | Chromebook-style shelf (bottom by default) |
| Launcher | `nwg-drawer` | Grid-based app drawer with search |
| Browser | `google-chrome-stable` | Familiar to Chromebook users |
| File manager | `Thunar` | Lightweight, thumbnail support |
| Greeter | `greetd` + `gtkgreet` | Minimal login screen via `cage` kiosk |
| Notifications | `mako` | Low-overhead notification daemon |
| Screen lock | `swayidle` + `swaylock` | Locks after 5 min idle, screen off at 10 min |
| Power | `power-profiles-daemon` | Battery management for laptops |
| Audio | `pipewire` + `wireplumber` | Modern audio stack with PulseAudio compat |
| Bluetooth | `bluez` | Pair devices via system tray |
| Printing | `CUPS` | Print to local and network printers |
| App store | `Bazaar` (via Flatpak, first-boot) | Install apps from Flathub (Zoom, Discord, etc.) |
| Settings | `universal-lite-settings` | Custom GTK4 app for panel, theme, wallpaper |
| Multimedia | RPM Fusion + GStreamer | Codec support out of the box |

### Low-RAM optimizations

- **zRAM swap**: compressed in-memory swap (zstd, 1.5x RAM, `vm.swappiness=180`)
- **systemd-repart**: auto-grows root partition to fill storage on first boot
- **Wayland-native throughout**: no Xwayland overhead
- **Weak deps disabled**: packages installed without optional dependencies

### Keyboard shortcuts

#### Media keys (Chromebook top row)

| Key | Action |
|-----|--------|
| Volume Up / Down / Mute | Adjust or mute audio |
| Brightness Up / Down | Adjust screen brightness |
| Fullscreen (F4) | Toggle fullscreen |

#### Search key (Super) shortcuts

| Shortcut | Action |
|----------|--------|
| `Super+Space` | App launcher |
| `Super+L` | Lock screen |
| `Super+E` | File manager (Thunar) |
| `Super+Escape` | Task manager (htop) |
| `Super+,` | Settings |
| `Super+Up` | Maximize window |
| `Super+Down` | Minimize window |

#### Window management

| Shortcut | Action |
|----------|--------|
| `Alt+Tab` / `Alt+Shift+Tab` | Switch windows |
| `Alt+[` | Snap window left |
| `Alt+]` | Snap window right |
| `Alt+F4` | Close window |
| `Ctrl+Alt+T` | Open terminal (`foot`) |

#### Screenshots

| Shortcut | Action |
|----------|--------|
| `Print Screen` | Full screenshot to clipboard |
| `Shift+Print Screen` | Area selection to clipboard |

### File associations

| File type | Opens with |
|-----------|------------|
| PDFs | Evince |
| Text files | Mousepad |
| Images | Ristretto |
| Videos | mpv |
| Web links | Chrome |

### Settings app

The built-in settings app (`universal-lite-settings`) exposes:

- Panel edge placement (top / bottom / left / right)
- Panel density (normal / compact)
- Theme (light / dark)
- Wallpaper selection (bundled or custom)

Changes apply immediately.

## Development

### Build locally

```bash
just build          # OCI container image
just build-raw      # Raw disk image (for dd)
just build-iso      # Anaconda ISO (needs 4+ GB RAM to install)
just build-qcow2    # QCOW2 for VM testing
```

### Test in a VM

```bash
just run-vm-qcow2
just run-vm-raw
```

### Lint and check

```bash
just lint           # shellcheck on all .sh files
just check          # Justfile syntax validation
```

### CI/CD

Pushes to `main` and a daily schedule automatically build and publish the OCI image to:

```
ghcr.io/universal-lite/universal-lite
```

Images are signed with [cosign](https://github.com/sigstore/cosign). To set up signing on a fresh fork:

```bash
COSIGN_PASSWORD='' cosign generate-key-pair
gh secret set SIGNING_SECRET < cosign.key
```

Disk images (raw, ISO) are built on manual dispatch via the [disk image workflow](../../actions/workflows/build-disk.yml). Dependencies are kept current by Dependabot and Renovate.

## Project layout

```
Containerfile                         # Image build definition
build_files/build.sh                  # Package installation and setup
files/
  etc/
    greetd/                           # Login greeter config
    systemd/repart.d/                 # Auto-grow root partition
    systemd/zram-generator.conf       # Compressed swap config
    sysctl.d/                         # Memory tuning
    xdg/labwc/                        # Compositor config + autostart
    xdg/swaylock/                     # Lock screen config
    yum.repos.d/google-chrome.repo    # Chrome package source
  usr/
    bin/universal-lite-settings       # Settings GUI (Python/GTK4)
    libexec/universal-lite-apply-settings  # Settings applier
    libexec/universal-lite-session-init    # Session startup script
    share/backgrounds/                # Bundled wallpapers
    share/universal-lite/             # Default settings + themes
    share/wayland-sessions/           # Session desktop entry
.github/workflows/
  build.yml                           # OCI image build + sign + push
  build-disk.yml                      # Raw and ISO artifact builds
```

## Notes

- On first boot, a setup wizard prompts you to create a user account.
- Targets x86_64 only.
- The Anaconda ISO requires 4+ GB RAM to run the installer — use the raw image + `dd` for 2 GB machines.
- Chromebooks need [MrChromebox UEFI firmware](https://mrchromebox.tech) and the write-protect screw removed to boot standard Linux images.
- Updates and rollback are handled by bootc automatically.
