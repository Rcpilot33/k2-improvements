#!/bin/ash
set -e

# Request Moonraker's complete Klipper restart. Unlike restarting the Klipper
# init service, this resets both the Klippy host process and connected MCUs.
API_URL="${MOONRAKER_URL:-http://127.0.0.1:7125}"

if [ -x /opt/bin/curl ]; then
    CURL=/opt/bin/curl
elif command -v curl >/dev/null 2>&1; then
    CURL=$(command -v curl)
else
    echo "E: curl is required to request FIRMWARE_RESTART through Moonraker" >&2
    echo "E: changes were installed, but a full printer power cycle is required" >&2
    exit 1
fi

echo "I: requesting FIRMWARE_RESTART through Moonraker"
if ! "$CURL" -fsS --max-time 10 -X POST \
    "$API_URL/printer/firmware_restart" >/dev/null; then
    echo "E: Moonraker did not accept the firmware restart request" >&2
    echo "E: changes were installed, but a full printer power cycle is required" >&2
    exit 1
fi

# Give Klipper time to enter its restart before checking for the ready state.
sleep 3
COUNT=0
READY=0
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

if [ "$READY" -ne 1 ]; then
    echo "E: Klipper did not return ready within 60 seconds" >&2
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
