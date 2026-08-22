#!/bin/ash
set -e

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
KLIPPER_EXTRA="${HOME}/klipper/klippy/extras/prime_tower.py"
CUSTOM_CFG="${HOME}/printer_data/config/custom/prime_tower.cfg"

mkdir -p "${HOME}/printer_data/config/custom"
rm -f "${KLIPPER_EXTRA}c" \
    "${HOME}/klipper/klippy/extras/__pycache__/prime_tower."*.pyc
ln -sf "${SCRIPT_DIR}/prime_tower.py" "${KLIPPER_EXTRA}"
cp -f "${SCRIPT_DIR}/prime_tower.cfg" "${CUSTOM_CFG}"

python3 "${SCRIPT_DIR}/../../scripts/ensure_included.py" \
    "${HOME}/printer_data/config/printer.cfg" custom/main.cfg
python3 "${SCRIPT_DIR}/../../scripts/ensure_included.py" \
    "${HOME}/printer_data/config/custom/main.cfg" prime_tower.cfg

echo "I: installed automatic prime-tower footprint detection"
