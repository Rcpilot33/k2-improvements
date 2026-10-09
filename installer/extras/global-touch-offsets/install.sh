#!/bin/sh
# Install the optional live editor for saved Cartographer Scan/Touch Z offsets.

set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
INSTALLER_BASE="${INSTALLER_DIR:-/mnt/UDISK/root/k2-improvements}"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_EXTRAS="${KLIPPER_DIR:-${HOME}/klipper}/klippy/extras"
PYTHON="${K2_PYTHON:-python3}"

[ -d "$CUSTOM" ] || { echo "ERROR: $CUSTOM not found — install macros first"; exit 1; }
[ -d "$KLIPPER_EXTRAS" ] || { echo "ERROR: $KLIPPER_EXTRAS not found — Klipper is required"; exit 1; }
grep -q '^\[cartographer\]' "$CFG_DIR/printer.cfg" "$CUSTOM"/*.cfg 2>/dev/null || {
    echo "ERROR: no [cartographer] section found — install Cartographer first"
    exit 1
}

sh "$INSTALLER_BASE/installer/extras/fluidd-ui-overlay/install.sh"
ln -sfn "$SCRIPT_DIR/global_touch_offsets.cfg" "$CUSTOM/global_touch_offsets.cfg"
ln -sfn "$SCRIPT_DIR/k2_cartographer_offset_editor.py" \
    "$KLIPPER_EXTRAS/k2_cartographer_offset_editor.py"
"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CUSTOM/main.cfg" global_touch_offsets.cfg

if ! "$PYTHON" "$SCRIPT_DIR/configure_fluidd_layout.py"; then
    echo "W: editor installed, but its Fluidd category metadata could not be configured"
fi

echo "I: optional Global Carto Z Offsets editor installed"
if [ "${K2_SKIP_KLIPPY_RESTART:-0}" != "1" ]; then
    sh "$INSTALLER_BASE/scripts/klippy_code_restart.sh"
fi
