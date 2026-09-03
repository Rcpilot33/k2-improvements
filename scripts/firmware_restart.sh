#!/bin/ash
set -e

# Request Klipper's firmware restart through Moonraker. This reloads printer
# configuration and resets connected MCUs, but it does not start a fresh
# Python process or reload modules that are already present in sys.modules.
# Full setup workflows set K2_DEFER_FIRMWARE_RESTART while installing their
# individual components, then invoke this script once without that flag after
# every component and setup prompt has completed.
if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    echo "I: deferring FIRMWARE_RESTART until the full setup is complete"
    exit 0
fi

API_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"
ATTEMPTS="${K2_FIRMWARE_RESTART_ATTEMPTS:-1}"
WAIT_FOR_STARTUP="${K2_WAIT_FOR_KLIPPY_STARTUP:-0}"
STARTUP_TIMEOUT="${K2_STARTUP_TIMEOUT:-60}"
RESTART_TIMEOUT="${K2_RESTART_TIMEOUT:-60}"
FAILURE_GRACE_SECONDS="${K2_FAILURE_GRACE_SECONDS:-8}"
READY_STABLE_SECONDS="${K2_READY_STABLE_SECONDS:-5}"

require_positive_integer() {
    case "$1" in
        ''|*[!0-9]*|0)
            echo "E: $2 must be a positive integer" >&2
            exit 1
            ;;
    esac
}

require_positive_integer "$ATTEMPTS" K2_FIRMWARE_RESTART_ATTEMPTS
require_positive_integer "$STARTUP_TIMEOUT" K2_STARTUP_TIMEOUT
require_positive_integer "$RESTART_TIMEOUT" K2_RESTART_TIMEOUT
require_positive_integer "$FAILURE_GRACE_SECONDS" K2_FAILURE_GRACE_SECONDS
require_positive_integer "$READY_STABLE_SECONDS" K2_READY_STABLE_SECONDS

if [ -n "${K2_CURL:-}" ]; then
    CURL=$K2_CURL
elif [ -x /opt/bin/curl ]; then
    CURL=/opt/bin/curl
elif command -v curl >/dev/null 2>&1; then
    CURL=$(command -v curl)
else
    echo "E: curl is required to request FIRMWARE_RESTART through Moonraker" >&2
    echo "E: changes were installed, but a full printer power cycle is required" >&2
    exit 1
fi

printer_info() {
    "$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true
}

printer_is_ready() {
    printf '%s' "$1" | \
        grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'
}

printer_is_failed() {
    printf '%s' "$1" | \
        grep -qE '"state"[[:space:]]*:[[:space:]]*"(error|shutdown)"'
}

# The K2's Serial-485 console traffic continues during normal operation, so
# console silence cannot identify the end of controller startup.  Use the
# vendor motor_control state when it is available.  Older configurations that
# do not expose motor_ready fall back to Klippy's ready state.
motor_controller_is_ready() {
    MOTOR_INFO=$("$CURL" -fsS --max-time 2 \
        "$API_URL/printer/objects/query?motor_control" 2>/dev/null || true)
    if printf '%s' "$MOTOR_INFO" | \
        grep -qE '"motor_ready"[[:space:]]*:[[:space:]]*false'; then
        return 1
    fi
    return 0
}

# A fresh Klippy host process may need substantially longer than the service
# command itself to parse the K2 configuration and begin connecting its MCUs.
# Do not interrupt that startup with FIRMWARE_RESTART.  In particular, the
# Cartographer configuration adds enough startup work that a fixed ten-second
# delay can land exactly as the primary MCU begins its serial connection.
if [ "$WAIT_FOR_STARTUP" = "1" ]; then
    echo "I: waiting for the fresh Klippy host process to finish startup"
    # Allow Moonraker to observe the service replacement before accepting a
    # state value; otherwise its first response may still describe the old
    # Klippy process.
    sleep 3
    COUNT=0
    while [ "$COUNT" -lt "$STARTUP_TIMEOUT" ]; do
        INFO=$(printer_info)
        if printer_is_ready "$INFO" && motor_controller_is_ready; then
            break
        fi
        if printer_is_failed "$INFO"; then
            echo "W: fresh Klippy host entered shutdown during MCU startup; beginning firmware-reset recovery" >&2
            break
        fi
        COUNT=$((COUNT + 1))
        sleep 1
    done

    if [ "$COUNT" -ge "$STARTUP_TIMEOUT" ]; then
        echo "W: fresh Klippy host startup did not settle within ${STARTUP_TIMEOUT} seconds" >&2
    else
        if printer_is_ready "$INFO" && motor_controller_is_ready; then
            echo "I: fresh Klippy host and K2 motor controller are ready; continuing with the protected firmware reset"
        fi
    fi
fi

ATTEMPT=1
while [ "$ATTEMPT" -le "$ATTEMPTS" ]; do
    if [ "$ATTEMPTS" -gt 1 ]; then
        echo "I: requesting FIRMWARE_RESTART through Moonraker (attempt ${ATTEMPT}/${ATTEMPTS})"
    else
        echo "I: requesting FIRMWARE_RESTART through Moonraker"
    fi

    ACCEPTED=0
    if "$CURL" -fsS --max-time 10 -X POST \
        "$API_URL/printer/firmware_restart" >/dev/null; then
        ACCEPTED=1
    else
        echo "W: Moonraker did not accept firmware restart attempt ${ATTEMPT}" >&2
    fi

    READY=0
    if [ "$ACCEPTED" -eq 1 ]; then
        # A normal K2 firmware restart passes through disconnect, unknown, and
        # key3/startup states.  Ignore those transient states.  A key1-style
        # error/shutdown only fails the attempt after it persists long enough
        # to distinguish it from the normal transition.
        sleep 3
        COUNT=0
        FAILURE_COUNT=0
        STABLE_COUNT=0
        while [ "$COUNT" -lt "$RESTART_TIMEOUT" ]; do
            INFO=$(printer_info)
            if printer_is_ready "$INFO"; then
                FAILURE_COUNT=0
                if motor_controller_is_ready; then
                    STABLE_COUNT=$((STABLE_COUNT + 1))
                    if [ "$STABLE_COUNT" -ge "$READY_STABLE_SECONDS" ]; then
                        READY=1
                        break
                    fi
                else
                    STABLE_COUNT=0
                fi
            elif printer_is_failed "$INFO"; then
                STABLE_COUNT=0
                FAILURE_COUNT=$((FAILURE_COUNT + 1))
                if [ "$FAILURE_COUNT" -ge "$FAILURE_GRACE_SECONDS" ]; then
                    echo "W: Klipper remained in error/shutdown for ${FAILURE_GRACE_SECONDS} seconds after attempt ${ATTEMPT}" >&2
                    break
                fi
            else
                # Empty, unknown, disconnected, and key3/startup responses are
                # expected while Fluidd and Moonraker reconnect.
                FAILURE_COUNT=0
                STABLE_COUNT=0
            fi
            COUNT=$((COUNT + 1))
            sleep 1
        done
    fi

    if [ "$READY" -eq 1 ]; then
        break
    fi

    if [ "$ATTEMPT" -lt "$ATTEMPTS" ]; then
        RECOVERY_DELAY=$((ATTEMPT * 5))
        echo "W: Klipper did not return ready; waiting ${RECOVERY_DELAY} seconds before recovery attempt $((ATTEMPT + 1))" >&2
        sleep "$RECOVERY_DELAY"
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [ "$READY" -ne 1 ]; then
    echo "E: Klipper did not return ready after ${ATTEMPTS} firmware restart attempt(s)" >&2
    echo "E: check Fluidd before continuing; power-cycle before any homing test" >&2
    exit 1
fi

echo "I: Klipper and the K2 motor controller remained ready for ${READY_STABLE_SECONDS} seconds"
