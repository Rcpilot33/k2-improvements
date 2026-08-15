#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

test -f ~/printer_data/config/custom/main.cfg || touch ~/printer_data/config/custom/main.cfg

# This file is intended to be user modified. Seed it only on first install;
# rerunning the macro installer must not erase mount selections or user edits.
if [ ! -f ~/printer_data/config/custom/overrides.cfg ]; then
    cp ${SCRIPT_DIR}/overrides.cfg ~/printer_data/config/custom/overrides.cfg
else
    echo "I: preserving existing custom/overrides.cfg"
fi

sh "${SCRIPT_DIR}/ensure_bed_mesh_soak.sh" \
    ~/printer_data/config/custom/overrides.cfg

# The same overrides seed is used by both setup paths. Activate the
# Cartographer-only defaults only when Cartographer is actually configured.
if [ -f ~/printer_data/config/custom/cartographer.cfg ]; then
    sh "${SCRIPT_DIR}/enable_cartographer_touch.sh" \
        ~/printer_data/config/custom/overrides.cfg
fi

if ! grep -qE 'include overrides.cfg' ~/printer_data/config/custom/main.cfg; then
    echo '[include overrides.cfg]' >> ~/printer_data/config/custom/main.cfg
fi

if [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../../scripts/firmware_restart.sh"
fi
