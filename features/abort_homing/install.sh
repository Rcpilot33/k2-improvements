#!/bin/ash
set -e

SCRIPT_DIR="$(readlink -f $(dirname $0))"

set +e
python3 ${SCRIPT_DIR}/patch_webhooks.py /mnt/UDISK/root/klipper/klippy/webhooks.py
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ] || [ "$EXIT_CODE" -eq 2 ]; then
    rm -f /mnt/UDISK/root/klipper/klippy/webhooks.pyc
    if ! sh ${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh; then
        echo "E: abort_homing was patched, but its required Klippy code reload failed" >&2
        exit 1
    fi
    STATE_DIR=/mnt/UDISK/root/.k2-improvements/installer-state
    mkdir -p ${STATE_DIR}
    touch ${STATE_DIR}/abort-homing-firmware-restart-v1
elif [ "$EXIT_CODE" -eq 1 ]; then
    exit 1
else
    echo "E: abort_homing patcher failed with unexpected exit code $EXIT_CODE" >&2
    exit "$EXIT_CODE"
fi
