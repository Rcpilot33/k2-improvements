#!/bin/sh
# Restore registrations independently of installing the Klipper driver.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
INSTALLER_DIR=$(cd "$HERE/../.." && pwd)
. "$INSTALLER_DIR/installer/lib/common.sh"
. "$INSTALLER_DIR/installer/detect/features.sh"

cfg=$PRINTER_CFG_DIR
custom="$cfg/custom"
updater="$cfg/updates/cartographer.cfg"
pending="$custom/.cartographer-registration-pending"
cartographer_core_ready || {
    warn "Cartographer driver or printer configuration is incomplete. Repair the core installation first."
    exit 1
}
[ -f "$cfg/moonraker.conf" ] || { warn "Missing $cfg/moonraker.conf"; exit 1; }
mkdir -p "$custom" "$cfg/updates"
restart=0
if [ -e "$pending" ]; then restart=1; fi
touch "$pending"

# Restore the updater file before enabling the include. Keep an installed
# updater with a valid section, including locally configured branch choices.
if [ "${1:-}" = --refresh-updater ] && ! cmp -s "$HERE/update-manager.cfg" "$updater"; then
    cp "$HERE/update-manager.cfg" "$updater"
    restart=1
elif ! grep -Fxq '[update_manager cartographer]' "$updater" 2>/dev/null; then
    if [ -s "$updater" ]; then
        warn "Unrecognized updater in $updater. Review this file before retrying."
        exit 1
    fi
    cp "$HERE/update-manager.cfg" "$updater"
    restart=1
fi
if ! grep -Fxq '[include updates/cartographer.cfg]' "$cfg/moonraker.conf"; then
    python3 "$INSTALLER_DIR/scripts/ensure_included.py" "$cfg/moonraker.conf" updates/cartographer.cfg
    restart=1
fi
asvc="${cfg%/*}/moonraker.asvc"
if ! grep -Fxq cartographer "$asvc" 2>/dev/null; then
    printf '%s\n' cartographer >> "$asvc"
    restart=1
fi
if [ "$restart" -eq 1 ]; then restart_moonraker_and_wait; fi

python3 "$INSTALLER_DIR/scripts/ensure_included.py" "$cfg/printer.cfg" custom/main.cfg
if ! grep -q '^\[cartographer\]' "$cfg/printer.cfg"; then
    python3 "$INSTALLER_DIR/scripts/ensure_included.py" "$custom/main.cfg" cartographer.cfg
fi
sh "$HERE/install_touchscreen_compat.sh" --no-restart
sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh"
rm -f "$pending"
