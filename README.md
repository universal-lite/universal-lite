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

### Flash to storage (raw/dd path)

This is the recommended path for most installs. You need:

- A second Linux machine to prepare the media
- A USB drive (boot medium, any size)
- Your target storage — SD card, second USB, etc. — **64 GB minimum**

**Step 1 — Get the image.** Build locally or download the latest from
[GitHub Actions → build-disk → Artifacts](../../actions/workflows/build-disk.yml):

```bash
just build-raw
```

**Step 2 — Flash the image to a USB drive** (this becomes your boot medium, not your
final install target):

```bash
lsblk   # identify the USB drive device — double-check before writing
sudo dd if=output/raw/disk.raw of=/dev/sdX bs=4M status=progress conv=fsync
```

**Step 3 — Boot the Chromebook from the USB drive.** The first-boot wizard runs
from the USB environment.

**Step 4 — Install to your target storage.** With your SD card (or other target)
connected, identify it and write to it:

```bash
lsblk   # confirm device name of target storage
sudo dd if=/dev/sdUSB of=/dev/sdTARGET bs=4M status=progress conv=fsync
```

The root partition expands to fill the remaining space on first boot.

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

Once booted, the system manages itself. Daily image builds are pulled automatically.
If an update ever causes a problem, the previous image is always available in the boot
menu — select it to roll back.

## First-boot setup

A setup wizard runs on first boot. It walks through six steps:

1. **Network** — connect to WiFi if needed (skipped automatically if you're already online)
2. **Account** — your full name, username, and password
3. **System** — timezone, memory management, optional root password, partition expansion
4. **Apps** — choose which Flatpak apps to install (Bazaar app store is on by default)
5. **Confirm** — review everything before applying
6. **Progress** — live status as each step runs, with retry/skip on failures

After setup completes the system reboots into the normal login screen.

### Memory management options

The wizard offers two memory strategies:

| Option | How it works | Best for |
|--------|-------------|----------|
| **zRAM** (default) | Compresses swap in RAM using zstd. 1.5× RAM, `vm.swappiness=180`. | Most machines — fast, no disk wear |
| **zswap + encrypted disk swap** | Compressed RAM cache that spills to an encrypted swap file on disk when full. | Very low RAM (2 GB) — keeps more apps open at the cost of some disk I/O |

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
| Greeter | `greetd` + `gtkgreet` | Minimal login screen via `cage` kiosk |
| Notifications | `mako` | Low-overhead notification daemon |
| Screen lock | `swayidle` + `swaylock` | Locks after 5 min idle, screen off at 10 min |
| Power | `power-profiles-daemon` | Battery/performance profiles for laptops |
| Audio | `pipewire` + `wireplumber` | Modern audio stack with PulseAudio compatibility |
| Bluetooth | `bluez` | Pair devices via system tray |
| Printing | `CUPS` | Local and network printers |
| App store | `Bazaar` (Flatpak, first-boot) | Browse and install apps from Flathub |
| Settings | `universal-lite-settings` | Custom GTK4 app for panel, theme, wallpaper |
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
| Web links | Chrome |

### Settings app

`Super+,` or the panel tray opens `universal-lite-settings`:

- Panel edge (top / bottom / left / right)
- Panel density (normal / compact)
- Theme (light / dark)
- Wallpaper (bundled or custom)

Changes apply immediately without restarting anything.

## Development

### Prerequisites

- [just](https://just.systems) — task runner
- [podman](https://podman.io) — container runtime

### Build

```bash
just build          # OCI container image
just build-raw      # Raw disk image (flash with dd)
just build-iso      # ISO installer (requires 4+ GB RAM on the target machine)
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
files/
  etc/
    greetd/                                # Login greeter config (greetd + gtkgreet)
    sysctl.d/                              # Memory tuning (swappiness, etc.)
    systemd/
      repart.d/                            # Auto-expand root partition on first boot
      zram-generator.conf                  # zRAM swap config (default memory strategy)
      system/
        universal-lite-greeter-setup.service    # Switch greeter config after first-boot wizard
        universal-lite-zram-disable.service     # Mask zRAM when zswap is chosen instead
        universal-lite-zswap.service            # Configure zswap parameters at boot
        universal-lite-swap-init.service        # Create /var/swap on first boot (zswap path)
        universal-lite-encrypted-swap.service   # Activate encrypted swap via dm-crypt
    xdg/
      foot/                                # Terminal config
      fuzzel/                              # App launcher config
      labwc/                               # Compositor config, keybindings, autostart
      mako/                                # Notification daemon config
      swaylock/                            # Lock screen config
  usr/
    bin/
      universal-lite-settings              # Settings GUI (Python/GTK4)
      universal-lite-setup-wizard          # First-boot setup wizard (Python/GTK4)
    lib/bootc/install/
      00-universal-lite.toml               # bootc install config (forces ext4)
    libexec/
      universal-lite-apply-settings        # Applies settings changes to compositor/panel
      universal-lite-encrypted-swap        # dm-crypt swap setup script
      universal-lite-greeter-setup         # Greeter config switcher (first-boot vs normal)
      universal-lite-session-init          # Wayland session startup
      universal-lite-swap-init             # Creates /var/swap at configured size
    share/
      applications/                        # .desktop files + mimeapps.list
      backgrounds/universal-lite/          # Bundled wallpapers
      universal-lite/defaults/             # Default settings (JSON)
      wayland-sessions/                    # Session .desktop entry for greetd
.github/workflows/
  build.yml                                # OCI image build + sign + push
  build-disk.yml                           # Raw and ISO artifact builds
```
