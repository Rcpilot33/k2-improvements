#!/bin/ash
set -e

# Klippy caches imported Python modules across RESTART and FIRMWARE_RESTART.
# Installers that replace already-loaded files under klippy/ therefore need a
# true host-process restart before the K2 MCU reset and stabilization sequence.
# A host-only restart is not safe for subsequent homing, so this helper follows
# it with one guarded firmware restart. It normally waits for every K2 motor to
# report ready first; if the known initialization fault occurs, the same reset
# is issued as a one-shot recovery.

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
RESTART_MARKER=/tmp/k2-klippy-code-restart-required
KLIPPER_SERVICE="${K2_KLIPPER_SERVICE:-/etc/init.d/klipper}"

if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    touch "$RESTART_MARKER"
    echo "I: deferring Klippy code reload and FIRMWARE_RESTART until the full setup is complete"
    exit 0
fi

. "$SCRIPT_DIR/stock_nozzle_camera.sh"
k2_require_no_active_job || exit 1
touch "$RESTART_MARKER"
echo "I: restarting the Klippy host process to load installed Python modules"
if ! "$KLIPPER_SERVICE" restart; then
    echo "E: Klippy host-process restart failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

# The K2 service restart also begins a comparatively slow configuration load
# and controller connection. Let firmware_restart.sh require the new Klippy
# session and its motor controller to settle before issuing the reset. A
# startup shutdown or readiness timeout is recovered by that same reset.
if ! K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    K2_WAIT_FOR_KLIPPY_STARTUP=1 \
    sh "$SCRIPT_DIR/firmware_restart.sh"; then
    echo "E: Klippy code reload recovery failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

rm -f "$RESTART_MARKER"
echo "I: Klippy Python modules and K2 MCU state reloaded successfully"
