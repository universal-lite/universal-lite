#!/bin/bash

set -ouex pipefail

FEDORA_MAJOR="$(rpm -E %fedora)"

install -d /etc/yum.repos.d /usr/share/wayland-sessions
install -Dm644 /ctx/files/etc/yum.repos.d/google-chrome.repo /etc/yum.repos.d/google-chrome.repo
install -Dm644 /ctx/files/usr/share/wayland-sessions/universal-lite.desktop /usr/share/wayland-sessions/universal-lite.desktop

rpm --import https://dl.google.com/linux/linux_signing_key.pub

dnf5 install -y \
    "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_MAJOR}.noarch.rpm" \
    "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_MAJOR}.noarch.rpm"

dnf5 install -y --setopt=install_weak_deps=False \
    adw-gtk3-theme \
    alsa-utils \
    brightnessctl \
    cage \
    ffmpegthumbnailer \
    file-roller \
    foot \
    fuzzel \
    google-chrome-stable \
    greetd \
    grim \
    gtkgreet \
    gvfs \
    gvfs-gphoto2 \
    gvfs-mtp \
    labwc \
    mako \
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
    wireplumber \
    wl-clipboard \
    xfce-polkit \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk \
    xdg-desktop-portal-wlr \
    xdg-user-dirs \
    xdg-user-dirs-gtk

dnf5 install -y --setopt=install_weak_deps=False gstreamer1-plugins-ugly

cp -a /ctx/files/. /

chmod 0755 \
    /usr/bin/universal-lite-settings \
    /usr/libexec/universal-lite-apply-settings \
    /usr/libexec/universal-lite-session-init

systemctl enable greetd.service
systemctl enable power-profiles-daemon.service
systemctl enable systemd-repart.service

dnf5 clean all
rm -rf /var/lib/dnf /run/dnf /run/selinux-policy /var/lib/greetd/.config/systemd/user/xdg-desktop-portal.service
rm -rf /tmp/* /run/* /var/tmp/*
