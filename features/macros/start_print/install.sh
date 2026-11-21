#!/bin/ash

set -e

SCRIPT_DIR="$(readlink -f $(dirname $0))"
. "$SCRIPT_DIR/../model.sh"

test -d ~/printer_data/config/custom || mkdir -p ~/printer_data/config/custom

# add the main.cfg to printer.cfg
python ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/printer.cfg custom/main.cfg
# add the start_print.cfg
ln -sf ${SCRIPT_DIR}/start_print.cfg \
    ~/printer_data/config/custom/start_print.cfg
python ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg start_print.cfg

if [ "$macro_model" = F012 ]; then
    echo "I: selecting K2 Pro (F012) stock-probe START_PRINT"
    ln -sf "$SCRIPT_DIR/start_print_pro.cfg" ~/printer_data/config/custom/start_print_pro.cfg
    python "$SCRIPT_DIR/../../../scripts/ensure_included.py" \
        ~/printer_data/config/custom/main.cfg start_print_pro.cfg
fi

# Stock PR Touch may stop Creality's artificial-Z approach at the nozzle and
# then enter _HOME_Z at an artificial coordinate near Z=20. Install a
# no-Cartographer-only command wrapper that retreats to Z=30 before _HOME_Z
# performs its first XY move.
ln -sf ${SCRIPT_DIR}/k2_prtouch_safe_xy.py \
    /usr/share/klipper/klippy/extras/k2_prtouch_safe_xy.py
ln -sf ${SCRIPT_DIR}/k2_prtouch_safe_xy.cfg \
    ~/printer_data/config/custom/k2_prtouch_safe_xy.cfg
rm -f /usr/share/klipper/klippy/extras/k2_prtouch_safe_xy.pyc \
    /usr/share/klipper/klippy/extras/__pycache__/k2_prtouch_safe_xy.*.pyc
if [ -f ~/printer_data/config/custom/cartographer.cfg ]; then
    python ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
        ~/printer_data/config/custom/main.cfg k2_prtouch_safe_xy.cfg True
else
    python ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
        ~/printer_data/config/custom/main.cfg k2_prtouch_safe_xy.cfg
fi

# Creality firmware 1.1.5.5 introduced a cancel-aware command loop, but macro
# templates still bypass it. Enable the narrowly scoped START_PRINT bridge only
# when that firmware API is available.
sh "$SCRIPT_DIR/install_fast_stop.sh" --no-restart
touch /tmp/k2-klippy-code-restart-required

if [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../../scripts/klippy_code_restart.sh"
fi
