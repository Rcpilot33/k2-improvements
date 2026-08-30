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

case "$ATTEMPTS" in
    ''|*[!0-9]*|0)
        echo "E: K2_FIRMWARE_RESTART_ATTEMPTS must be a positive integer" >&2
        exit 1
        ;;
esac

if [ -x /opt/bin/curl ]; then
    CURL=/opt/bin/curl
elif command -v curl >/dev/null 2>&1; then
    CURL=$(command -v curl)
else
    echo "E: curl is required to request FIRMWARE_RESTART through Moonraker" >&2
    echo "E: changes were installed, but a full printer power cycle is required" >&2
    exit 1
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
echo "I: Klipper API is ready; waiting 25 seconds for K2 motor initialization"
sleep 25

INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
if ! printf '%s' "$INFO" | \
    grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
    echo "E: Klipper was not ready after the K2 stabilization interval" >&2
    echo "E: check Fluidd before continuing; power-cycle before any homing test" >&2
    exit 1
fi

echo "I: Klipper ready and K2 motor initialization interval complete"
