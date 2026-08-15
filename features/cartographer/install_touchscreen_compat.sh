#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

ln -sfn ${SCRIPT_DIR}/k2_cartographer_touchscreen.py \
    ~/klipper/klippy/extras/k2_cartographer_touchscreen.py
ln -sfn ${SCRIPT_DIR}/k2_cartographer_touchscreen.cfg \
    ~/printer_data/config/custom/k2_cartographer_touchscreen.cfg
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg k2_cartographer_touchscreen.cfg

echo "I: installed Cartographer touchscreen Z-offset display compatibility"

if [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../scripts/firmware_restart.sh"
fi
