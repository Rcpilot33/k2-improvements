#!/bin/sh
# Opt-in temporary native PR Touch diagnostics. Does not restart the printer.
set -eu
SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
KLIPPER_BASE="${KLIPPER_DIR:-${HOME}/klipper}"
PYTHON="${K2_PYTHON:-python3}"
"$PYTHON" "$SCRIPT_DIR/configure.py" "$@" \
    --config-dir "$CFG_DIR" --klipper-dir "$KLIPPER_BASE" \
    --moonraker-url "${MOONRAKER_URL:-http://127.0.0.1:7125}"
