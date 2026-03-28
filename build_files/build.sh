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
    nwg-drawer \
    "f${FEDORA_MAJOR}-backgrounds-base" \
    "f${FEDORA_MAJOR}-backgrounds-gnome" \
    gnome-backgrounds \
    google-roboto-fonts \
    google-roboto-mono-fonts \
    greetd \
    grubby \
    grim \
    gtkgreet \
    gvfs \
    gvfs-gphoto2 \
    gvfs-mtp \
    htop \
    labwc \
    mako \
    mousepad \
    mpv \
    network-manager-applet \
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

install -d /etc/xdg/labwc
labwc-menu-generator > /etc/xdg/labwc/menu.xml

# Append desktop right-click menu
sed -i '/<\/openbox_menu>/i \
  <menu id="desktop-menu" label="Desktop">\
    <item label="Settings"><action name="Execute" command="universal-lite-settings"\/><\/item>\
    <item label="File Manager"><action name="Execute" command="Thunar"\/><\/item>\
    <item label="Terminal"><action name="Execute" command="foot"\/><\/item>\
    <separator\/>\
    <item label="Lock Screen"><action name="Execute" command="swaylock -f"\/><\/item>\
    <item label="Log Out"><action name="Exit"\/><\/item>\
  <\/menu>' /etc/xdg/labwc/menu.xml

chmod 0755 \
    /etc/xdg/labwc/autostart \
    /usr/bin/universal-lite-settings \
    /usr/bin/universal-lite-setup-wizard \
    /usr/libexec/universal-lite-apply-settings \
    /usr/libexec/universal-lite-encrypted-swap \
    /usr/libexec/universal-lite-flatpak-setup \
    /usr/libexec/universal-lite-swap-init \
    /usr/libexec/universal-lite-greeter-setup \
    /usr/libexec/universal-lite-session

systemctl mask plymouth-quit-wait.service plymouth-quit.service
systemctl enable greetd.service
systemctl enable power-profiles-daemon.service
systemctl enable universal-lite-greeter-setup.service
systemctl enable accounts-daemon.service
systemctl enable cups.service
systemctl enable bluetooth.service

dnf5 clean all
rm -rf /var/lib/dnf /run/dnf /run/selinux-policy /var/lib/greetd/.config/systemd/user/xdg-desktop-portal.service
find /tmp /var/tmp -mindepth 1 -delete 2>/dev/null || true
find /run -mindepth 1 -not -path '/run/systemd*' -delete 2>/dev/null || true
