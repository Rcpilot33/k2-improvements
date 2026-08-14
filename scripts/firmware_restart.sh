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
while [ "$COUNT" -lt 60 ]; do
    INFO=$("$CURL" -fsS --max-time 2 "$API_URL/printer/info" 2>/dev/null || true)
    if printf '%s' "$INFO" | \
        grep -qE '"state"[[:space:]]*:[[:space:]]*"ready"'; then
        echo "I: Klipper returned ready after FIRMWARE_RESTART"
        exit 0
    fi
    COUNT=$((COUNT + 1))
    sleep 1
done

echo "E: Klipper did not return ready within 60 seconds" >&2
echo "E: check Fluidd before continuing; power-cycle before any homing test" >&2
exit 1
