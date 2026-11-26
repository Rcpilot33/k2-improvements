#!/bin/sh
# Install the optional material Z-offset editor.

set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
INSTALLER_BASE="${INSTALLER_DIR:-/mnt/UDISK/root/k2-improvements}"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_EXTRAS="${KLIPPER_DIR:-${HOME}/klipper}/klippy/extras"
PYTHON="${K2_PYTHON:-python3}"
START_PRINT_SOURCE="$INSTALLER_BASE/features/macros/start_print/start_print.cfg"
HAD_SURFACE_WRAPPER=0
. "$INSTALLER_BASE/installer/lib/start_print_backups.sh"

[ -f "$CUSTOM/overrides.cfg" ] || { echo "ERROR: install macros before Material Z Offsets"; exit 1; }
[ -e "$CUSTOM/start_print.cfg" ] || { echo "ERROR: install macros before Material Z Offsets"; exit 1; }
[ -d "$KLIPPER_EXTRAS" ] || { echo "ERROR: Klipper extras directory not found: $KLIPPER_EXTRAS"; exit 1; }
[ -f "$START_PRINT_SOURCE" ] || { echo "ERROR: managed START_PRINT source not found: $START_PRINT_SOURCE"; exit 1; }

if grep -q 'surface-selection wrapper' "$CUSTOM/start_print.cfg" 2>/dev/null; then
    HAD_SURFACE_WRAPPER=1
fi

sh "$INSTALLER_BASE/installer/extras/fluidd-ui-overlay/install.sh"
"$PYTHON" "$SCRIPT_DIR/k2_material_z_offset_editor.py" \
    --normalize "$CUSTOM/overrides.cfg"
# Refresh this managed link so installing the optional editor cannot leave an
# older START_PRINT in place with a working UI but no apply/register handoff.
cleanup_managed_start_print_backups \
    "$CUSTOM/start_print.cfg" "$START_PRINT_SOURCE"
backup_unmanaged_start_print \
    "$CUSTOM/start_print.cfg" "$START_PRINT_SOURCE" \
    "before-material-z-offsets.$(date +%Y%m%d-%H%M%S)"
ln -sfn "$START_PRINT_SOURCE" "$CUSTOM/start_print.cfg"
if [ "$HAD_SURFACE_WRAPPER" -eq 1 ]; then
    sh "$INSTALLER_BASE/installer/extras/surface-selection-wrapper/install.sh"
fi
ln -sfn "$SCRIPT_DIR/material_z_offsets.cfg" "$CUSTOM/material_z_offsets.cfg"
"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CUSTOM/main.cfg" material_z_offsets.cfg
sh "$INSTALLER_BASE/features/macros/start_print/install_material_registration.sh" \
    "$CUSTOM" "$KLIPPER_EXTRAS"

if ! "$PYTHON" "$SCRIPT_DIR/configure_fluidd_layout.py"; then
    echo "W: editor installed, but its Fluidd category metadata could not be configured"
fi

echo "I: optional Material Z Offsets editor installed"
if [ "${K2_SKIP_KLIPPY_RESTART:-0}" != "1" ]; then
    sh "$INSTALLER_BASE/scripts/klippy_code_restart.sh"
fi
