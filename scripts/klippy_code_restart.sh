#!/bin/ash
set -e

# Klippy caches imported Python modules across RESTART and FIRMWARE_RESTART.
# Installers that replace already-loaded files under klippy/ therefore need a
# true host-process restart before the K2 MCU reset and stabilization sequence.
# A host-only restart is not safe for subsequent homing, so this helper always
# follows it with the guarded firmware restart and permits one recovery retry.

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
RESTART_MARKER=/tmp/k2-klippy-code-restart-required

if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    touch "$RESTART_MARKER"
    echo "I: deferring Klippy code reload and FIRMWARE_RESTART until the full setup is complete"
    exit 0
fi

touch "$RESTART_MARKER"
echo "I: restarting the Klippy host process to load installed Python modules"
if ! /etc/init.d/klipper restart; then
    echo "E: Klippy host-process restart failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

# The K2 service restart also begins a comparatively slow configuration load
# and controller connection.  Let firmware_restart.sh observe Klippy leaving
# its startup state before issuing the first reset; interrupting startup while
# the primary MCU is only beginning to connect can produce key301.
if ! K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS=2 \
    K2_WAIT_FOR_KLIPPY_STARTUP=1 \
    sh "$SCRIPT_DIR/firmware_restart.sh"; then
    echo "E: Klippy code reload recovery failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

rm -f "$RESTART_MARKER"
echo "I: Klippy Python modules and K2 MCU state reloaded successfully"
