#!/bin/sh
# Opt-in no-Carto global editor. Installation never changes calibration or moves.
set -eu
SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
KLIPPER_BASE="${KLIPPER_DIR:-${HOME}/klipper}"
PYTHON="${K2_PYTHON:-python3}"
"$PYTHON" "$SCRIPT_DIR/configure.py" "$@" \
    --config-dir "$CFG_DIR" --klipper-dir "$KLIPPER_BASE" \
    --moonraker-url "${MOONRAKER_URL:-http://127.0.0.1:7125}"
if [ "${1:-}" != "--remove" ]; then
    "$PYTHON" "$SCRIPT_DIR/configure_fluidd_layout.py" || \
        echo 'W: feature installed; refresh Fluidd or run Global_Z_Offsets_No_Carto from its console'
fi
