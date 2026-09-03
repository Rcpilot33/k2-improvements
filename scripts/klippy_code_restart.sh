#!/bin/ash
set -e

# Klippy caches imported Python modules across RESTART and FIRMWARE_RESTART.
# Installers that replace already-loaded files under klippy/ therefore need a
# true host-process restart before the K2 MCU reset and stabilization sequence.
# A host-only restart is not safe for subsequent homing, so this helper always
# follows it with the guarded firmware restart and permits one recovery retry.

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
RESTART_MARKER=/tmp/k2-klippy-code-restart-required
KLIPPER_SERVICE="${K2_KLIPPER_SERVICE:-/etc/init.d/klipper}"

if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    touch "$RESTART_MARKER"
    echo "I: deferring Klippy code reload and FIRMWARE_RESTART until the full setup is complete"
    exit 0
fi

touch "$RESTART_MARKER"

# Firmware 1.1.3.13 occasionally leaves either the primary or Linux MCU just
# beyond Klippy's startup window.  Its normal FIRMWARE_RESTART recovery often
# succeeds on the following attempt, but hardware testing caught two misses in
# a row. Give that firmware one additional attempt; other validated firmware
# retains the established two-attempt sequence.
if [ -n "${K2_PRINTER_FW_OVERRIDE:-}" ]; then
    PRINTER_FW=$K2_PRINTER_FW_OVERRIDE
elif [ -r "$SCRIPT_DIR/../installer/detect/printer_fw.sh" ]; then
    . "$SCRIPT_DIR/../installer/detect/printer_fw.sh"
    PRINTER_FW=$(detect_printer_fw)
else
    PRINTER_FW=unknown
fi

if [ "$PRINTER_FW" = "1.1.3.13" ]; then
    RESTART_ATTEMPTS=3
else
    RESTART_ATTEMPTS=2
fi

echo "I: restarting the Klippy host process to load installed Python modules"
if ! "$KLIPPER_SERVICE" restart; then
    echo "E: Klippy host-process restart failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

# The K2 service restart also begins a comparatively slow configuration load
# and controller connection.  Let firmware_restart.sh observe Klippy leaving
# its startup state before issuing the first reset; interrupting startup while
# the primary MCU is only beginning to connect can produce key301.
if ! K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS="$RESTART_ATTEMPTS" \
    K2_WAIT_FOR_KLIPPY_STARTUP=1 \
    sh "$SCRIPT_DIR/firmware_restart.sh"; then
    echo "E: Klippy code reload recovery failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

rm -f "$RESTART_MARKER"
echo "I: Klippy Python modules and K2 MCU state reloaded successfully"
