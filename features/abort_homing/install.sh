#!/bin/ash

SCRIPT_DIR="$(readlink -f $(dirname $0))"

python ${SCRIPT_DIR}/patch_webhooks.py /mnt/UDISK/root/klipper/klippy/webhooks.py
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 2 ]; then
    rm -f /mnt/UDISK/root/klipper/klippy/webhooks.pyc
    sh ${SCRIPT_DIR}/../../scripts/firmware_restart.sh
elif [ $EXIT_CODE -eq 1 ]; then
    exit 1
fi
