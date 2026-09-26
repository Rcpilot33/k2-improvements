#!/bin/sh
set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
REPO_ROOT="$(readlink -f "$SCRIPT_DIR/../..")"
INSTALLER_BASE="${INSTALLER_DIR:-$REPO_ROOT}"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_ROOT="${KLIPPER_DIR:-${HOME}/klipper}"
KLIPPER_EXTRAS="$KLIPPER_ROOT/klippy/extras"
PYTHON="${K2_PYTHON:-python3}"

[ -d "$KLIPPER_EXTRAS" ] || {
    echo "ERROR: Klipper extras directory not found: $KLIPPER_EXTRAS" >&2
    exit 1
}

mkdir -p "$CUSTOM"
ln -sfn "$SCRIPT_DIR/memory_diagnostics.py" \
    "$KLIPPER_EXTRAS/memory_diagnostics.py"
ln -sfn "$SCRIPT_DIR/memory_diagnostics.cfg" \
    "$CUSTOM/memory_diagnostics.cfg"
rm -f "$KLIPPER_EXTRAS/memory_diagnostics.pyc" \
    "$KLIPPER_EXTRAS/__pycache__/memory_diagnostics."*.pyc

"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CFG_DIR/printer.cfg" custom/main.cfg
"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CUSTOM/main.cfg" memory_diagnostics.cfg

echo "I: installed bounded memory and fragmentation diagnostics"
echo "I: log: /mnt/UDISK/printer_data/logs/memory-diagnostics.log"
if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    touch /tmp/k2-klippy-code-restart-required
    echo "I: deferring Klippy code reload until the full update is complete"
else
    sh "$INSTALLER_BASE/scripts/klippy_code_restart.sh"
fi
