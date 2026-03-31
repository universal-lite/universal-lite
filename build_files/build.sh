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
    evince \
    fastfetch \
    ffmpegthumbnailer \
    file-roller \
    flatpak \
    foot \
    fuzzel \
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
    google-roboto-fonts \
    google-roboto-mono-fonts \
    greetd \
    grubby \
    grim \
    gvfs \
    gvfs-gphoto2 \
    gvfs-mtp \
    htop \
    labwc \
    libnotify \
    mako \
    mousepad \
    mpv \
    network-manager-applet \
    nm-connection-editor \
    pavucontrol \
    pipewire \
    power-profiles-daemon \
    pipewire-alsa \
    pipewire-pulseaudio \
    playerctl \
    python3-gobject \
    ristretto \
    slurp \
    swaybg \
    swayidle \
    swaylock \
    wlopm \
    Thunar \
    tumbler \
    udisks2 \
    unzip \
    waybar \
    wdisplays \
    wlr-randr \
    wireplumber \
    wl-clipboard \
    wtype \
    xfce-polkit \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk \
    xdg-desktop-portal-wlr \
    xdg-user-dirs \
    xdg-user-dirs-gtk

dnf5 install -y --setopt=install_weak_deps=False gstreamer1-plugins-ugly

cp -a /ctx/files/. /

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
    <item label="Terminal"><action name="Execute" command="foot"/></item>
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
    /usr/bin/universal-lite-settings \
    /usr/bin/universal-lite-setup-wizard \
    /usr/bin/universal-lite-greeter \
    /usr/libexec/universal-lite-apply-settings \
    /usr/libexec/universal-lite-encrypted-swap \
    /usr/libexec/universal-lite-flatpak-setup \
    /usr/libexec/universal-lite-swap-init \
    /usr/libexec/universal-lite-greeter-launch \
    /usr/libexec/universal-lite-greeter-setup \
    /usr/libexec/universal-lite-menu \
    /usr/libexec/universal-lite-session \
    /usr/libexec/universal-lite-volume \
    /usr/libexec/universal-lite-brightness \
    /usr/bin/universal-lite-power-menu

systemctl mask plymouth-quit-wait.service plymouth-quit.service
systemctl enable greetd.service
systemctl enable universal-lite-first-boot.service
systemctl enable power-profiles-daemon.service
systemctl enable accounts-daemon.service
systemctl enable cups.service
systemctl enable bluetooth.service

# Unified updater: bootc image + Flatpak in one pass with hardware safety checks.
# Replaces the separate rpm-ostree + flatpak timers from the base image.
systemctl enable uupd.timer
systemctl disable rpm-ostreed-automatic.timer
systemctl disable flatpak-system-update.timer
systemctl --global disable flatpak-user-update.timer

dnf5 clean all
rm -rf /var/lib/dnf /run/dnf /run/selinux-policy /var/lib/greetd/.config/systemd/user/xdg-desktop-portal.service
find /tmp /var/tmp -mindepth 1 -delete 2>/dev/null || true
find /run -mindepth 1 -not -path '/run/systemd*' -delete 2>/dev/null || true
