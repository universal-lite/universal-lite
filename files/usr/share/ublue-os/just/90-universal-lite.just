# Universal-Lite ujust recipes.
#
# Loaded automatically by the base image's ujust wrapper — any *.just
# under /usr/share/ublue-os/just/ is merged into the single `ujust`
# command. Recipes below can be invoked as `ujust <name>`.

# Show the currently-configured memory strategy + active swap devices.
swap-status:
    #!/usr/bin/env bash
    set -eu
    strategy=$(python3 -c "import json; print(json.load(open('/var/lib/universal-lite/install-config.json')).get('memory_strategy', 'zram'))" 2>/dev/null || echo 'zram (default)')
    echo "Configured strategy: $strategy"
    echo ""
    echo "Active swap devices:"
    swapon --show || echo "  (none)"

# Switch memory strategy between zram (in-memory compression) and zswap
# (zram + encrypted disk swap for overflow). The target user's wizard
# picks one at install; this lets you change your mind later. Requires

# a reboot to take effect.
toggle-swap:
    #!/usr/bin/env bash
    set -eu
    current=$(python3 -c "import json; print(json.load(open('/var/lib/universal-lite/install-config.json')).get('memory_strategy', 'zram'))" 2>/dev/null || echo "zram")
    if [ "$current" = "zram" ]; then
        next="zswap"
        desc="zswap-backed (adds a 4 GB encrypted disk swap for overflow when RAM + zram fills)"
    else
        next="zram"
        desc="zram-only (no disk swap; lighter on storage wear)"
    fi
    echo "Current memory strategy: $current"
    echo "Will switch to:          $next"
    echo "   $desc"
    echo ""
    read -rp "Proceed? [y/N] " yn
    case "$yn" in
        [Yy]*) ;;
        *) echo "Cancelled."; exit 0;;
    esac

    if [ "$next" = "zswap" ]; then
        read -rp "Swap file size in GB [4]: " size
        size=${size:-4}
        sudo /usr/libexec/universal-lite-set-memory-strategy zswap "$size"
    else
        sudo /usr/libexec/universal-lite-set-memory-strategy zram
    fi

    echo ""
    echo "A reboot is required for the change to take effect."
    read -rp "Reboot now? [y/N] " yn
    case "$yn" in
        [Yy]*) sudo systemctl reboot;;
        *) echo "Reboot later with: sudo systemctl reboot";;
    esac
