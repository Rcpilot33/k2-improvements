#!/bin/ash
set -e

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
KLIPPER_ROOT="${KLIPPER_DIR:-${HOME}/klipper}"
TARGET="${KLIPPER_ROOT}/klippy/extras/virtual_sdcard.py"
. "$SCRIPT_DIR/../../scripts/stock_nozzle_camera.sh"
stock_nozzle_camera_require_idle || { echo 'E: confirmed idle printer required for virtual-SD changes' >&2; exit 1; }

if [ ! -f "$TARGET" ]; then
    echo "E: virtual_sdcard.py not found at $TARGET" >&2
    exit 1
fi

set +e
python3 "$SCRIPT_DIR/patch_virtual_sdcard.py" "$TARGET"
PATCH_STATUS=$?
set -e

if [ "$PATCH_STATUS" -ne 0 ] && [ "$PATCH_STATUS" -ne 2 ]; then
    exit "$PATCH_STATUS"
fi

rm -f "${TARGET}c" \
    "${KLIPPER_ROOT}/klippy/extras/__pycache__/virtual_sdcard."*.pyc

sh "$SCRIPT_DIR/../../scripts/klippy_code_restart.sh"
