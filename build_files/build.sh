#!/bin/bash

set -ouex pipefail

FEDORA_MAJOR="$(rpm -E %fedora)"

install -d /usr/share/wayland-sessions
install -Dm644 /ctx/files/usr/share/wayland-sessions/universal-lite.desktop /usr/share/wayland-sessions/universal-lite.desktop
install -Dm644 /ctx/files/usr/share/wayland-sessions/vanilla-labwc.desktop /usr/share/wayland-sessions/vanilla-labwc.desktop

dnf5 install -y \
    "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_MAJOR}.noarch.rpm" \
    "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_MAJOR}.noarch.rpm"

dnf5 install -y --setopt=install_weak_deps=False \
    NetworkManager-libnm \
    accountsservice \
    adw-gtk3-theme \
    alsa-utils \
    bash-completion \
    blueman \
    bluez \
    bluez-tools \
    brightnessctl \
    cage \
    cups \
    cryptsetup \
    dosfstools \
    evince \
    fastfetch \
    fedora-logos \
    material-icons-fonts \
    ffmpegthumbnailer \
    file-roller \
    flatpak \
    ptyxis \
    labwc-menu-generator \
    "f${FEDORA_MAJOR}-backgrounds-base" \
    "f${FEDORA_MAJOR}-backgrounds-gnome" \
    gammastep \
    glibc-langpack-am \
    glibc-langpack-ar \
    glibc-langpack-de \
    glibc-langpack-es \
    glibc-langpack-fa \
    glibc-langpack-fr \
    glibc-langpack-ha \
    glibc-langpack-hi \
    glibc-langpack-it \
    glibc-langpack-ja \
    glibc-langpack-ko \
    glibc-langpack-nl \
    glibc-langpack-pl \
    glibc-langpack-pt \
    glibc-langpack-ru \
    glibc-langpack-sv \
    glibc-langpack-sw \
    glibc-langpack-th \
    glibc-langpack-tr \
    glibc-langpack-vi \
    glibc-langpack-yo \
    glibc-langpack-zh \
    gnome-backgrounds \
    fedora-workstation-backgrounds \
    libjxl \
    webp-pixbuf-loader \
    google-roboto-fonts \
    google-roboto-mono-fonts \
    greetd \
    grubby \
    grim \
    gtk4-layer-shell \
    libadwaita \
    gvfs \
    gvfs-gphoto2 \
    gvfs-mtp \
    labwc \
    libnotify \
    mako \
    mousepad \
    mpv \
    network-manager-applet \
    nm-connection-editor \
    parted \
    pavucontrol \
    pipewire \
    power-profiles-daemon \
    pipewire-alsa \
    pipewire-pulseaudio \
    playerctl \
    python3-gobject \
    rsync \
    ristretto \
    slurp \
    swaybg \
    swayidle \
    swaylock \
    systemd-oomd-defaults \
    wlopm \
    Thunar \
    tumbler \
    udisks2 \
    unzip \
    waybar \
    wdisplays \
    wlr-randr \
    wireplumber \
    xfce4-taskmanager \
    wl-clipboard \
    xfce-polkit \
    xorg-x11-server-Xwayland \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk \
    xdg-desktop-portal-wlr \
    xdg-user-dirs \
    xdg-user-dirs-gtk \
    xfsprogs \
    btrfs-progs

dnf5 install -y --setopt=install_weak_deps=False gstreamer1-plugins-ugly

# Build a GdkPixbuf loader for JPEG-XL so swaybg and the settings
# picker can display vendor .jxl wallpapers directly. Fedora 43
# doesn't package the loader, but libjxl upstream ships the plugin
# source alongside the library. Compile it against the already-
# installed libjxl, drop the .so into the system loader dir, and
# refresh the cache so every gdk-pixbuf consumer picks it up.
# Pinned to v0.11.1 to match libjxl-0.11.1-*.fc43 and avoid ABI drift.
dnf5 install -y --setopt=install_weak_deps=False \
    gcc libjxl-devel gdk-pixbuf2-devel git-core
_jxl_src=/tmp/libjxl-src
git clone --depth 1 --branch v0.11.1 \
    https://github.com/libjxl/libjxl.git "$_jxl_src"
# Upstream plugins/gdk-pixbuf/CMakeLists.txt assumes it's included from
# the full libjxl tree (references in-tree `jxl`/`jxl_threads` targets),
# so we compile the single source file directly against the system libs.
_gdk_moddir=$(pkg-config --variable=gdk_pixbuf_moduledir gdk-pixbuf-2.0)
install -d "$_gdk_moddir"
gcc -shared -fPIC -O2 -Wl,--as-needed \
    -o "$_gdk_moddir/libpixbufloader-jxl.so" \
    "$_jxl_src/plugins/gdk-pixbuf/pixbufloader-jxl.c" \
    $(pkg-config --cflags --libs gdk-pixbuf-2.0 libjxl libjxl_threads)
install -Dm644 "$_jxl_src/plugins/gdk-pixbuf/jxl.thumbnailer" \
    /usr/share/thumbnailers/jxl.thumbnailer
# Refresh the system loader cache so swaybg and gdk-pixbuf-based
# thumbnailers see the new .jxl loader immediately at first boot.
# Fedora ships the tool name-mangled by word size (-64 on x86_64).
gdk-pixbuf-query-loaders-64 --update-cache
rm -rf "$_jxl_src"
dnf5 remove -y gcc libjxl-devel gdk-pixbuf2-devel git-core

cp -a /ctx/files/. /

# Language name matrix and all MO files (wizard + settings) are
# pre-compiled and shipped in files/, installed by the cp above.

# Recompile the GSettings schema cache so our zz-universal-lite
# override (button-layout: minimize/maximize/close) wins over
# Fedora's 'appmenu:close' default. Chrome/Chromium, Firefox,
# Electron apps, and Flatpak apps via xdg-desktop-portal's Settings
# namespace all read this.
glib-compile-schemas /usr/share/glib-2.0/schemas/

# Add signature verification for our container registry.
# Merge into existing policy.json rather than replacing it so
# the base image's ublue-os verification entries are preserved.
python3 -c "
import json
p = json.load(open('/etc/containers/policy.json'))
p.setdefault('transports', {}).setdefault('docker', {})['ghcr.io/universal-lite'] = [{
    'type': 'sigstoreSigned',
    'keyPath': '/etc/pki/containers/universal-lite.pub',
    'signedIdentity': {'type': 'matchRepository'},
}]
json.dump(p, open('/etc/containers/policy.json', 'w'), indent=2)
"

# Ensure video group exists for brightnessctl backlight access
groupadd -f video

install -d /etc/xdg/labwc

# Root menu: dynamic pipemenu (regenerated each time the menu opens).
# Desktop menu: static (right-click on desktop, no pipemenu support for named menus).
cat > /etc/xdg/labwc/menu.xml <<'MENU_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_menu>
  <menu id="root-menu" label="" execute="/usr/libexec/universal-lite-menu"/>
  <menu id="desktop-menu" label="Desktop">
    <item label="Settings"><action name="Execute" command="universal-lite-settings"/></item>
    <item label="File Manager"><action name="Execute" command="Thunar"/></item>
    <item label="Terminal"><action name="Execute" command="ptyxis"/></item>
    <separator/>
    <item label="Lock Screen"><action name="Execute" command="swaylock -f"/></item>
    <item label="Log Out"><action name="Exit"/></item>
    <item label="Restart"><action name="Execute" command="systemctl reboot"/></item>
    <item label="Shut Down"><action name="Execute" command="systemctl poweroff"/></item>
  </menu>
</openbox_menu>
MENU_EOF

chmod 0755 \
    /etc/xdg/labwc/autostart \
    /usr/bin/ul-debug-nm \
    /usr/bin/universal-lite-settings \
    /usr/bin/universal-lite-setup-wizard \
    /usr/bin/universal-lite-greeter \
    /usr/libexec/universal-lite-apply-settings \
    /usr/libexec/universal-lite-encrypted-swap \
    /usr/libexec/universal-lite-first-boot \
    /usr/libexec/universal-lite-flatpak-setup \
    /usr/libexec/universal-lite-nightlight \
    /usr/libexec/universal-lite-set-memory-strategy \
    /usr/libexec/universal-lite-swap-init \
    /usr/libexec/universal-lite-greeter-launch \
    /usr/libexec/universal-lite-greeter-setup \
    /usr/libexec/universal-lite-wizard-session \
    /usr/libexec/universal-lite-menu \
    /usr/bin/universal-lite-app-menu \
    /usr/libexec/universal-lite-session \
    /usr/libexec/universal-lite-volume \
    /usr/libexec/universal-lite-brightness

# Disable Plymouth entirely by masking the unit that starts it.
#
# An earlier version of this file masked plymouth-quit.service and
# plymouth-quit-wait.service instead, which is the WRONG end of the
# lifecycle to cut: plymouth-start would still run, Plymouth would
# grab DRM master on the primary display, and then there was no
# plymouth-quit-wait for downstream services to order against — so
# the DRM handoff to cage (the greeter's compositor) was a naked race.
# Sometimes cage won DRM master, sometimes Plymouth held it and cage
# hung silently on VT acquisition. That matched the intermittent
# "stuck at Started greetd.service" boot the user kept hitting.
#
# Masking plymouth-start.service prevents Plymouth from ever running,
# so the quit services have nothing to do and can stay at their
# defaults (greetd's stock After=plymouth-quit.service is satisfied
# instantly because plymouth-start never activated). Boot is pure text
# since we don't pass rhgb/splash kargs, which matches the current UX.
systemctl mask plymouth-start.service
systemctl enable greetd.service
systemctl enable power-profiles-daemon.service
systemctl enable accounts-daemon.service
systemctl enable cups.service
systemctl enable bluetooth.service
# Explicit: NM is enabled by the base image, but re-enabling is a cheap
# safeguard against any preset drift. NetworkManager-wait-online stays
# at its preset default (enabled) to match bluefin exactly - nothing
# on this image actually orders against network-online.target on the
# critical boot path (greetd doesn't, our first-boot service doesn't,
# flatpak-setup polls DNS itself), so the unit being enabled costs
# nothing on the common case and keeps us aligned with the base image.
systemctl enable NetworkManager.service
systemctl enable universal-lite-first-boot.service
systemctl enable universal-lite-flatpak-install.service
systemctl enable universal-lite-flatpak-update.service
# OOM protection on 2 GB hardware — oomd kills the heaviest cgroup under
# memory/swap pressure before the kernel OOM killer engages and freezes
# the whole machine.
systemctl enable systemd-oomd.service

# Add ublue-os COPR for uupd (unified updater with hardware safety checks).
dnf5 copr enable -y ublue-os/packages fedora-"${FEDORA_MAJOR}"-x86_64
dnf5 install -y --setopt=install_weak_deps=False uupd

# Unified updater: bootc image + Flatpak in one pass with hardware safety checks.
# Replaces the separate rpm-ostree + flatpak timers from the base image.
systemctl enable uupd.timer
systemctl disable rpm-ostreed-automatic.timer
systemctl disable flatpak-system-update.timer
systemctl --global disable flatpak-user-update.timer

# Hide launchers for packages that show up in the start menu but
# don't belong in this distro's UX.
#
# xfce4-panel can't be uninstalled: Fedora 43's Thunar package Requires
# xfce4-panel directly (verified: `dnf5 repoquery --whatrequires
# xfce4-panel` lists Thunar-4.20.*). An earlier version of this file
# did `dnf5 remove -y xfce4-panel`, which dnf5 honored by cascade-
# removing Thunar as well — so Super+E, File Manager menu entries,
# and inode/directory MIME defaults all dead-ended into "command
# not found". We now just remove the .desktop file so the launcher
# never surfaces; the ~5 MB of binaries stay on disk but never run
# under labwc + waybar.
#
# nvtop is a real leaf (no reverse deps), so we uninstall it outright.
dnf5 remove -y nvtop || true
rm -f /usr/share/applications/xfce4-panel.desktop \
      /usr/share/applications/nvtop.desktop

# Flatpak apps are installed by the first-boot service from Flathub —
# not pre-installed in the image.  This keeps the raw image small for
# constrained target hardware (16 GB eMMC).

# fedora-logos already installs fedora-logo-icon.png into hicolor at
# all standard sizes.  Add the SVG as a scalable icon for HiDPI.
install -Dm644 /usr/share/fedora-logos/fedora_logo.svg \
    /usr/share/icons/hicolor/scalable/apps/fedora-logo-icon.svg

# Rebuild icon caches so waybar/GTK can find symbolic icons
gtk-update-icon-cache -f /usr/share/icons/Adwaita 2>/dev/null || true
gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true

# Regenerate initramfs so /usr/lib/modprobe.d/universal-lite-i915.conf
# reaches the early-KMS load of i915. Without this step the options only
# take effect after the first kernel update triggers its own regen.
if command -v dracut >/dev/null 2>&1; then
    KVER=$(rpm -q --qf '%{version}-%{release}.%{arch}' kernel-core | head -1)
    [ -n "$KVER" ] && dracut --force --kver "$KVER" || true
fi

dnf5 clean all
rm -rf /var/lib/dnf /run/dnf /run/selinux-policy /var/lib/greetd/.config/systemd/user/xdg-desktop-portal.service
find /tmp /var/tmp -mindepth 1 -delete 2>/dev/null || true
find /run -mindepth 1 -not -path '/run/systemd*' -delete 2>/dev/null || true
