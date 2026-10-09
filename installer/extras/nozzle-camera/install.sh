#!/bin/sh
set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
REPO_ROOT="$(readlink -f "$SCRIPT_DIR/../../..")"
INSTALLER_BASE="${INSTALLER_DIR:-$REPO_ROOT}"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_ROOT="${KLIPPER_DIR:-/usr/share/klipper}"
KLIPPER_EXTRAS="$KLIPPER_ROOT/klippy/extras"
PYTHON="${K2_PYTHON:-python3}"
BIN_DIR="/mnt/UDISK/bin"
SHELL_EXTRA="$KLIPPER_EXTRAS/gcode_shell_command.py"

. "$REPO_ROOT/scripts/stock_nozzle_camera.sh"
stock_nozzle_camera_require_available

[ -x /usr/bin/nozzle_cam_power.sh ] || {
    echo "ERROR: Creality's stock nozzle-camera power control was not found." >&2
    echo "This extra supports only the factory K2 Plus nozzle camera." >&2
    exit 1
}
[ -x /opt/bin/opkg ] || {
    echo "ERROR: Entware is required; install the core setup first." >&2
    exit 1
}
[ -d "$KLIPPER_EXTRAS" ] || {
    echo "ERROR: Klipper extras directory not found: $KLIPPER_EXTRAS" >&2
    exit 1
}

if [ ! -x /opt/bin/ffmpeg ]; then
    echo "I: installing ffmpeg through Entware"
    /opt/bin/opkg update
    /opt/bin/opkg install ffmpeg
fi
[ -x /opt/bin/ffmpeg ] || {
    echo "ERROR: ffmpeg installation did not complete." >&2
    exit 1
}

mkdir -p "$BIN_DIR" "$CUSTOM"
chmod 755 "$SCRIPT_DIR/nozzle-camera.sh"
ln -sfn "$SCRIPT_DIR/nozzle-camera.sh" "$BIN_DIR/nozzle-camera.sh"

# Do not replace an unrelated implementation if another feature already
# supplied this common Klipper extra.
if [ -e "$SHELL_EXTRA" ] || [ -L "$SHELL_EXTRA" ]; then
    if ! grep -q 'class ShellCommand' "$SHELL_EXTRA" 2>/dev/null; then
        echo "ERROR: incompatible gcode_shell_command.py already exists:" >&2
        echo "  $SHELL_EXTRA" >&2
        exit 1
    fi
else
    ln -s "$SCRIPT_DIR/gcode_shell_command.py" "$SHELL_EXTRA"
fi

ln -sfn "$SCRIPT_DIR/nozzle_camera.cfg" "$CUSTOM/nozzle_camera.cfg"
rm -f "$KLIPPER_EXTRAS/gcode_shell_command.pyc" \
    "$KLIPPER_EXTRAS/__pycache__/gcode_shell_command."*.pyc

"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CFG_DIR/printer.cfg" custom/main.cfg
"$PYTHON" "$INSTALLER_BASE/scripts/ensure_included.py" \
    "$CUSTOM/main.cfg" nozzle_camera.cfg

echo "I: installed stock nozzle-camera streaming"
echo "I: commands: NOZZLE_CAM_ON, NOZZLE_CAM_OFF, NOZZLE_CAM_STATUS"
echo "I: stream: http://PRINTER_IP:8081/ (automatic shutoff after 10 minutes)"

sh "$INSTALLER_BASE/scripts/klippy_code_restart.sh"
