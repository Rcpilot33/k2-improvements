#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))
CUSTOM=~/printer_data/config/custom
MAIN_CFG=${CUSTOM}/main.cfg

if [ -f "${MAIN_CFG}" ]; then
    sed -i '/^[[:space:]]*\[include k2_cartographer_touchscreen\.cfg\][[:space:]]*$/d' \
        "${MAIN_CFG}"
fi

rm -f ~/klipper/klippy/extras/k2_cartographer_touchscreen.py
rm -f ${CUSTOM}/k2_cartographer_touchscreen.cfg

sh "${SCRIPT_DIR}/../../scripts/firmware_restart.sh"
echo "I: removed Cartographer touchscreen Z-offset display compatibility"
