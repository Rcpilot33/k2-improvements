#!/bin/ash
set -e

# SAVE_CONFIG launches this worker in a detached session after its atomic file
# replacement completes. A short delay lets the G-code response reach clients
# before this worker restarts the Klippy service. klippy_code_restart.sh then
# owns the full guarded host restart, firmware reset, retry, and stabilization
# sequence.

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
DELAY="${K2_SAVE_CONFIG_RESTART_DELAY:-2}"
STATUS_FILE=/tmp/k2-save-config-restart.status

case "$DELAY" in
    ''|*[!0-9]*)
        echo "E: K2_SAVE_CONFIG_RESTART_DELAY must be a non-negative integer" >&2
        exit 1
        ;;
esac

printf 'scheduled %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
sleep "$DELAY"
printf 'running %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"

if K2_DEFER_FIRMWARE_RESTART=0 sh "$SCRIPT_DIR/klippy_code_restart.sh"; then
    printf 'complete %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
else
    rc=$?
    printf 'failed(%s) %s\n' "$rc" "$(date '+%Y-%m-%d %H:%M:%S')" > "$STATUS_FILE"
    exit "$rc"
fi
