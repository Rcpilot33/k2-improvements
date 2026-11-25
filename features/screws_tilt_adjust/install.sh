#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

model=$(get_sn_mac.sh model)
case "$model" in
    F008) screw_config=screws_tilt_adjust.cfg ;;
    F012) screw_config=screws_tilt_adjust_pro.cfg ;;
    *) echo "E: no bed screw profile for printer model '${model}'" >&2; exit 1 ;;
esac

ln -sf ${SCRIPT_DIR}/screws_tilt_adjust.py \
    ~/klipper/klippy/extras/screws_tilt_adjust.py

test -d ~/printer_data/config/custom || mkdir -p ~/printer_data/config/custom

ln -sf "$SCRIPT_DIR/$screw_config" \
    ~/printer_data/config/custom/screws_tilt_adjust.cfg
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg \
    screws_tilt_adjust.cfg
python "${SCRIPT_DIR}/../../scripts/ensure_included.py" \
    ~/printer_data/config/printer.cfg custom/main.cfg

if [ -f ~/printer_data/config/custom/overrides.cfg ]; then
    python3 "$SCRIPT_DIR/../macros/overrides/ensure_m191_settings.py" \
        ~/printer_data/config/custom/overrides.cfg --stc-only
fi

sh ${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh

STATE_DIR=/mnt/UDISK/root/.k2-improvements/installer-state
mkdir -p ${STATE_DIR}
touch ${STATE_DIR}/screws-tilt-firmware-restart-v1
