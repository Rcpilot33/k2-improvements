#!/bin/sh
set -eu
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/../../../scripts/stock_nozzle_camera.sh"
stock_nozzle_camera_require_idle || { echo 'E: confirmed idle printer required for resume macro changes' >&2; exit 1; }
python3 "$SCRIPT_DIR/patch_resume_fans.py" "${PRINTER_CFG_DIR:-${HOME}/printer_data/config}/gcode_macro.cfg"
if [ "${1:-}" != --no-restart ]; then
    sh "$SCRIPT_DIR/../../../scripts/firmware_restart.sh"
fi
