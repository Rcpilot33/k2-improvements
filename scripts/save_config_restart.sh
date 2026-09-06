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
ERROR_LOG=/tmp/k2-save-config-restart.error.log
API_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
TRANSITION_TIMEOUT="${K2_SAVE_CONFIG_TRANSITION_TIMEOUT:-30}"
READY_TIMEOUT="${K2_SAVE_CONFIG_READY_TIMEOUT:-90}"
MOTOR_E_RECOVERY_DELAY="${K2_SAVE_CONFIG_MOTOR_E_RECOVERY_DELAY:-10}"
KLIPPY_LOG="${K2_KLIPPY_LOG:-/mnt/UDISK/printer_data/logs/klippy.log}"

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

case "$MOTOR_E_RECOVERY_DELAY" in
    ''|*[!0-9]*)
        echo "E: K2_SAVE_CONFIG_MOTOR_E_RECOVERY_DELAY must be a non-negative integer" >&2
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

printer_failed() {
    printf '%s' "$INFO" | \
        grep -qE '"state"[[:space:]]*:[[:space:]]*"(error|shutdown)"'
}

capture_restart_error() {
    printf '%s\n' "$INFO" > "$ERROR_LOG"
    if [ -r "$KLIPPY_LOG" ]; then
        tail -n +"$KLIPPY_LOG_START" "$KLIPPY_LOG" >> "$ERROR_LOG" \
            2>/dev/null || true
    fi
}

is_recoverable_motor_e_error() {
    awk '
        /"code"[[:space:]]*:[[:space:]]*"key798"/ &&
        /Motor connection failed, exceeding maximum retry count/ &&
        /"values"[[:space:]]*:[[:space:]]*\[[[:space:]]*["\047]e["\047][[:space:]]*\]/ {
            found = 1
        }
        END { exit !found }
    ' "$ERROR_LOG" || return 1

    ERROR_CODES=$(sed -n \
        's/.*"code"[[:space:]]*:[[:space:]]*"\(key[0-9][0-9]*\)".*/\1/p' \
        "$ERROR_LOG" | sort -u)
    [ -n "$ERROR_CODES" ] || return 1
    for ERROR_CODE in $ERROR_CODES; do
        case "$ERROR_CODE" in
            key1|key798) ;;
            *) return 1 ;;
        esac
    done
    return 0
}

printf 'scheduled %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
rm -f "$ERROR_LOG"
if [ -r "$KLIPPY_LOG" ]; then
    KLIPPY_LOG_START=$(($(wc -l < "$KLIPPY_LOG") + 1))
else
    KLIPPY_LOG_START=1
fi

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
RECOVER_MOTOR_E=0
COUNT=0
while [ "$COUNT" -lt "$READY_TIMEOUT" ]; do
    if printer_ready && motor_ready; then
        break
    fi
    if printer_failed; then
        capture_restart_error
        if is_recoverable_motor_e_error; then
            RECOVER_MOTOR_E=1
            break
        fi
        echo "E: stock SAVE_CONFIG restart entered an unrecognized error state" >&2
        echo "E: no automatic recovery was attempted; power-cycle before homing" >&2
        printf 'failed(stock-error) %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
        exit 1
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
if [ "$RECOVER_MOTOR_E" -eq 1 ]; then
    printf 'recovering-motor-e %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    echo "W: recognized exact key798 extruder-motor startup failure"
    echo "I: waiting ${MOTOR_E_RECOVERY_DELAY} seconds for shutdown to settle"
    sleep "$MOTOR_E_RECOVERY_DELAY"
    echo "I: requesting one firmware restart for the validated key798 motor-e recovery"
else
    echo "I: stock Klipper restart and K2 motor initialization completed"
    echo "I: requesting one protected firmware restart"
fi
FIRMWARE_HELPER="${K2_FIRMWARE_RESTART_HELPER:-$SCRIPT_DIR/firmware_restart.sh}"
if K2_DEFER_FIRMWARE_RESTART=0 K2_FIRMWARE_RESTART_ATTEMPTS=1 \
    sh "$FIRMWARE_HELPER"; then
    if [ "$RECOVER_MOTOR_E" -eq 1 ]; then
        printf 'complete(recovered-motor-e) %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    else
        printf 'complete %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    fi
else
    rc=$?
    printf 'failed(%s) %s\n' "$rc" "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit "$rc"
fi
