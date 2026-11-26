#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))
MAIN_CFG=~/printer_data/config/custom/main.cfg
COMPAT_CFG=~/printer_data/config/custom/k2_prtouch_version_compat.cfg

if [ "${1:-}" = "--remove" ]; then
    cp "$MAIN_CFG" "${MAIN_CFG}.before-prtouch-version-compat-remove-$(date +%s)"
    sed -i '/^[[:space:]]*\[include k2_prtouch_version_compat\.cfg\][[:space:]]*$/d' \
        "$MAIN_CFG"
    rm -f "$COMPAT_CFG" \
        ~/klipper/klippy/extras/k2_prtouch_version_compat.py \
        ~/klipper/klippy/extras/k2_prtouch_version_compat.pyc \
        ~/klipper/klippy/extras/__pycache__/k2_prtouch_version_compat.*.pyc
    echo "I: removed PR Touch version-reporting compatibility"
else
    if ! grep -q '^[[:space:]]*\[cartographer\][[:space:]]*$' \
        ~/printer_data/config/custom/cartographer.cfg 2>/dev/null; then
        echo "E: Cartographer configuration is not active; refusing compatibility install" >&2
        exit 1
    fi

    ln -sfn ${SCRIPT_DIR}/k2_prtouch_version_compat.py \
        ~/klipper/klippy/extras/k2_prtouch_version_compat.py
    ln -sfn ${SCRIPT_DIR}/k2_prtouch_version_compat.cfg "$COMPAT_CFG"
    python3 ${SCRIPT_DIR}/../../scripts/ensure_included.py \
        "$MAIN_CFG" k2_prtouch_version_compat.cfg
    rm -f ~/klipper/klippy/extras/k2_prtouch_version_compat.pyc \
        ~/klipper/klippy/extras/__pycache__/k2_prtouch_version_compat.*.pyc
    echo "I: installed Cartographer pre-file preparation compatibility"
fi

if [ "${2:-}" != "--no-restart" ] && [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh"
fi
