#!/bin/ash

set -e

SCRIPT_DIR="$(readlink -f $(dirname $0))"
INSTALLER_BASE="${INSTALLER_DIR:-/mnt/UDISK/root/k2-improvements}"
CFG_DIR="${PRINTER_CFG_DIR:-${HOME}/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_EXTRAS="${KLIPPER_DIR:-${HOME}/klipper}/klippy/extras"
PYTHON="${K2_PYTHON:-python3}"

test -d "$CUSTOM" || mkdir -p "$CUSTOM"
[ -d "$KLIPPER_EXTRAS" ] || { echo "ERROR: Klipper extras directory not found: $KLIPPER_EXTRAS"; exit 1; }

# add the main.cfg to printer.cfg
"$PYTHON" ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    "$CFG_DIR/printer.cfg" custom/main.cfg
# add the m191.cfg
ln -sf ${SCRIPT_DIR}/m191.cfg \
    "$CUSTOM/m191.cfg"
"$PYTHON" ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    "$CUSTOM/main.cfg" m191.cfg

# Install the live Bed_Assist settings editor and its shared Fluidd dialog.
sh "$INSTALLER_BASE/installer/extras/fluidd-ui-overlay/install.sh"
ln -sfn "$SCRIPT_DIR/m191_settings.cfg" "$CUSTOM/m191_settings.cfg"
ln -sfn "$SCRIPT_DIR/k2_m191_settings_editor.py" \
    "$KLIPPER_EXTRAS/k2_m191_settings_editor.py"
ln -sfn "$SCRIPT_DIR/k2_m191_circulation.py" \
    "$KLIPPER_EXTRAS/k2_m191_circulation.py"
rm -f "$KLIPPER_EXTRAS/k2_m191_circulation.pyc" \
    "$KLIPPER_EXTRAS"/__pycache__/k2_m191_circulation.*.pyc
"$PYTHON" ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    "$CUSTOM/main.cfg" m191_settings.cfg

# Creality's M141 and M106 are themselves gcode_macros, so Klipper cannot wrap
# them with another macro's rename_existing option. Install a small command
# interceptor that retains and delegates to both original handlers instead.
ln -sfn "$SCRIPT_DIR/k2_m141_guard.py" \
    "$KLIPPER_EXTRAS/k2_m141_guard.py"
ln -sfn "$SCRIPT_DIR/k2_m141_guard.cfg" "$CUSTOM/k2_m141_guard.cfg"
rm -f "$KLIPPER_EXTRAS/k2_m141_guard.pyc" \
    "$KLIPPER_EXTRAS"/__pycache__/k2_m141_guard.*.pyc
"$PYTHON" ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    "$CUSTOM/main.cfg" k2_m141_guard.cfg
touch /tmp/k2-klippy-code-restart-required

if ! "$PYTHON" "$SCRIPT_DIR/configure_fluidd_layout.py"; then
    echo "W: Bed_Assist installed, but its Fluidd category metadata could not be configured"
fi

if [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../../scripts/klippy_code_restart.sh"
fi
