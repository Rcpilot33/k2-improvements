#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))
TARGET=~/klipper/klippy/configfile.py

# Remove cached bytecode so the next Klipper start must load the managed file.
rm -f ~/klipper/klippy/configfile.pyc \
    ~/klipper/klippy/__pycache__/configfile.*.pyc
ln -sfn ${SCRIPT_DIR}/configfile.py ${TARGET}

echo "I: installed K2 Plus SAVE_CONFIG firmware-restart protection"

if [ "${1:-}" != "--no-restart" ]; then
    sh ${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh
fi
