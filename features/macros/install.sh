#!/bin/sh
# Top-level macros installer — runs all four macros sub-feature installers
# (start_print, m191, bed_mesh, overrides) in order.
#
# Without this wrapper, the "macros" feature has no top-level install.sh
# and any caller that dispatches to features/macros/install.sh fails.

set -eu

SCRIPT_DIR="$(readlink -f $(dirname $0))"
CUSTOM="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}/custom"
HAD_SURFACE_WRAPPER=0

# The optional Cartographer plate workflow turns start_print.cfg into a
# managed regular file containing its surface-selection block. Remember that
# state before the base macros installer refreshes start_print.cfg.
if grep -q 'surface-selection wrapper' "$CUSTOM/start_print.cfg" 2>/dev/null; then
    HAD_SURFACE_WRAPPER=1
fi

for sub in resume start_print m191 bed_mesh overrides; do
    if [ -f "$SCRIPT_DIR/$sub/install.sh" ]; then
        echo "--- macros/$sub ---"
        sh "$SCRIPT_DIR/$sub/install.sh" --no-restart
    else
        echo "W: $SCRIPT_DIR/$sub/install.sh not found — skipping"
    fi
done

if [ "$HAD_SURFACE_WRAPPER" -eq 1 ]; then
    echo "--- restoring Cartographer surface-selection wrapper ---"
    sh "$SCRIPT_DIR/../../installer/extras/surface-selection-wrapper/install.sh"
fi

if [ -f /tmp/k2-klippy-code-restart-required ]; then
    sh "${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh"
else
    sh "${SCRIPT_DIR}/../../scripts/firmware_restart.sh"
fi

echo "I: macros (start_print, m191, bed_mesh, overrides) installed"
