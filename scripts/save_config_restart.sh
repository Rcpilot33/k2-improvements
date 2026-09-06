#!/bin/ash
set -e

# SAVE_CONFIG launches this worker in a detached session immediately before it
# requests Klipper's stock in-process restart.  This worker survives that
# restart, observes Moonraker lose the old ready state, waits for both the new
# Klipper session and the K2 motor controller to become ready, and then requests
# exactly one protected firmware restart.  A normal SAVE_CONFIG does not replace
# Python code and therefore must not restart the Linux Klippy service.

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
STATUS_FILE=/tmp/k2-save-config-restart.status
API_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
TRANSITION_TIMEOUT="${K2_SAVE_CONFIG_TRANSITION_TIMEOUT:-30}"
READY_TIMEOUT="${K2_SAVE_CONFIG_READY_TIMEOUT:-90}"

case "$TRANSITION_TIMEOUT" in
    ''|*[!0-9]*|0)
        echo "E: K2_SAVE_CONFIG_TRANSITION_TIMEOUT must be a positive integer" >&2
        exit 1
        ;;
esac

case "$READY_TIMEOUT" in
    ''|*[!0-9]*|0)
        echo "E: K2_SAVE_CONFIG_READY_TIMEOUT must be a positive integer" >&2
        exit 1
        ;;
esac

if [ -n "${K2_CURL:-}" ]; then
    CURL=$K2_CURL
elif [ -x /opt/bin/curl ]; then
    CURL=/opt/bin/curl
elif command -v curl >/dev/null 2>&1; then
    CURL=$(command -v curl)
else
    echo "E: curl is required to monitor the stock SAVE_CONFIG restart" >&2
    exit 1
fi

printer_ready() {
    INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
    printf '%s' "$INFO" | \
        grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'
}

motor_ready() {
    MOTOR=$("$CURL" -fsS --max-time 2 \
        "$API_URL/printer/objects/query?motor_control=motor_ready" \
        2>/dev/null || true)
    printf '%s' "$MOTOR" | \
        grep -qE '"motor_ready"[[:space:]]*:[[:space:]]*true'
}

printf 'scheduled %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"

echo "I: waiting for the stock SAVE_CONFIG Klipper restart to begin"
COUNT=0
while [ "$COUNT" -lt "$TRANSITION_TIMEOUT" ]; do
    if ! printer_ready; then
        break
    fi
    COUNT=$((COUNT + 1))
    sleep 1
done
if [ "$COUNT" -ge "$TRANSITION_TIMEOUT" ]; then
    echo "E: did not observe the stock SAVE_CONFIG restart begin" >&2
    printf 'failed(no-transition) %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit 1
fi

printf 'waiting-stock-restart %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
echo "I: stock Klipper restart observed; waiting for Klipper and K2 motors"
COUNT=0
while [ "$COUNT" -lt "$READY_TIMEOUT" ]; do
    if printer_ready && motor_ready; then
        break
    fi
    COUNT=$((COUNT + 1))
    sleep 1
done
if [ "$COUNT" -ge "$READY_TIMEOUT" ]; then
    echo "E: stock SAVE_CONFIG restart did not reach Klipper-ready and motor-ready" >&2
    echo "E: power-cycle the printer before any homing test" >&2
    printf 'failed(stock-not-ready) %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit 1
fi

printf 'firmware-restart %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
echo "I: stock Klipper restart and K2 motor initialization completed"
echo "I: requesting one protected firmware restart"
FIRMWARE_HELPER="${K2_FIRMWARE_RESTART_HELPER:-$SCRIPT_DIR/firmware_restart.sh}"
if K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$FIRMWARE_HELPER"; then
    printf 'complete %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
else
    rc=$?
    printf 'failed(%s) %s\n' "$rc" "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit "$rc"
fi
