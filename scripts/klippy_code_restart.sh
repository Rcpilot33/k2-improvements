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

# The K2 service restart also begins controller initialization. The first
# firmware reset can still encounter key301; firmware_restart.sh retries once
# after its readiness timeout, matching the recovery validated on hardware.
echo "I: waiting 10 seconds before the protected K2 firmware reset"
sleep 10

if ! K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS=2 \
    sh "$SCRIPT_DIR/firmware_restart.sh"; then
    echo "E: Klippy code reload recovery failed" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    exit 1
fi

rm -f "$RESTART_MARKER"
echo "I: Klippy Python modules and K2 MCU state reloaded successfully"
