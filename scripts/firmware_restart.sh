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
STABILIZATION_SECONDS="${K2_STABILIZATION_SECONDS:-25}"

case "$ATTEMPTS" in
    ''|*[!0-9]*|0)
        echo "E: K2_FIRMWARE_RESTART_ATTEMPTS must be a positive integer" >&2
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
    echo "E: curl is required to request FIRMWARE_RESTART through Moonraker" >&2
    echo "E: changes were installed, but a full printer power cycle is required" >&2
    exit 1
fi

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
    while [ "$COUNT" -lt 60 ]; do
        INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
        if printf '%s' "$INFO" | \
            grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
            break
        fi
        if printf '%s' "$INFO" | \
            grep -qE '"state"[[:space:]]*:[[:space:]]*"(error|shutdown)"'; then
            echo "W: fresh Klippy host entered shutdown during MCU startup; beginning firmware-reset recovery" >&2
            break
        fi
        COUNT=$((COUNT + 1))
        sleep 1
    done

    if [ "$COUNT" -ge 60 ]; then
        echo "W: fresh Klippy host startup did not settle within 60 seconds" >&2
    else
        if printf '%s' "$INFO" | \
            grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
            echo "I: fresh Klippy host is ready; waiting ${STABILIZATION_SECONDS} seconds for K2 controller startup before firmware reset"
            # Hardware testing on 1.1.3.13 showed that five seconds still
            # lands inside Creality's controller initialization.  Allow the
            # observed 15-20 second activity window to finish, then confirm
            # Klippy stayed ready before asking it to reset the MCUs.
            sleep "$STABILIZATION_SECONDS"
            INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
            if printf '%s' "$INFO" | \
                grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
                echo "I: fresh Klippy host and K2 controllers are stable; continuing with the protected firmware reset"
            else
                echo "W: Klippy left ready state during the pre-reset stabilization interval; beginning recovery" >&2
            fi
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
        # Give Klipper time to enter its restart before checking readiness.
        sleep 3
        COUNT=0
        while [ "$COUNT" -lt 60 ]; do
            INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
            if printf '%s' "$INFO" | \
                grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
                READY=1
                break
            fi
            COUNT=$((COUNT + 1))
            sleep 1
        done
    fi

    if [ "$READY" -eq 1 ]; then
        break
    fi

    if [ "$ATTEMPT" -lt "$ATTEMPTS" ]; then
        echo "W: Klipper did not return ready; waiting 5 seconds before one recovery attempt" >&2
        sleep 5
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [ "$READY" -ne 1 ]; then
    echo "E: Klipper did not return ready after ${ATTEMPTS} firmware restart attempt(s)" >&2
    echo "E: check Fluidd before continuing; power-cycle before any homing test" >&2
    exit 1
fi

# On the K2 Plus, Moonraker can report Klipper ready while Creality's motor
# controller initialization is still producing startup traffic. Do not return
# control to an installer until that observed 15-20 second window has passed.
echo "I: Klipper API is ready; waiting ${STABILIZATION_SECONDS} seconds for K2 motor initialization"
sleep "$STABILIZATION_SECONDS"

INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
if ! printf '%s' "$INFO" | \
    grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
    echo "E: Klipper was not ready after the K2 stabilization interval" >&2
    echo "E: check Fluidd before continuing; power-cycle before any homing test" >&2
    exit 1
fi

echo "I: Klipper ready and K2 motor initialization interval complete"
