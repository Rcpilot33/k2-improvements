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

python3 "${SCRIPT_DIR}/cleanup_managed_overrides.py" \
    ~/printer_data/config/custom/overrides.cfg

sh "${SCRIPT_DIR}/ensure_bed_mesh_soak.sh" \
    ~/printer_data/config/custom/overrides.cfg

python3 "${SCRIPT_DIR}/ensure_m191_settings.py" \
    ~/printer_data/config/custom/overrides.cfg

. "${SCRIPT_DIR}/../../../installer/detect/printer_fw.sh"
PRINTER_FW="$(detect_printer_fw)"

# Firmware 1.1.3.13 references SET_TEMPERATURE_FAN_SWITCH from its stock
# macros but does not register the command. Enable the compatibility shim only
# on that confirmed firmware so newer implementations cannot conflict with it.
ln -sf "${SCRIPT_DIR}/firmware_11313.cfg" \
    ~/printer_data/config/custom/firmware_11313.cfg
if [ "$PRINTER_FW" = "1.1.3.13" ]; then
    python "${SCRIPT_DIR}/../../../scripts/ensure_included.py" \
        ~/printer_data/config/custom/main.cfg firmware_11313.cfg
else
    python "${SCRIPT_DIR}/../../../scripts/ensure_included.py" \
        ~/printer_data/config/custom/main.cfg firmware_11313.cfg True
fi

# The case-fan release is now guarded by live fan state on every firmware.
# Remove the former 1.1.5.2-only include and its installed link. The tracked
# placeholder remains harmless while an older checkout is being updated.
python "${SCRIPT_DIR}/../../../scripts/ensure_included.py" \
    ~/printer_data/config/custom/main.cfg firmware_1152.cfg True
rm -f ~/printer_data/config/custom/firmware_1152.cfg

# The same overrides seed is used by both setup paths. Activate the
# Cartographer-only defaults only when Cartographer is actually configured.
if [ -f ~/printer_data/config/custom/cartographer.cfg ]; then
    python3 "${SCRIPT_DIR}/ensure_cartographer_overrides.py" \
        ~/printer_data/config/custom/overrides.cfg
fi

if ! grep -qE 'include overrides.cfg' ~/printer_data/config/custom/main.cfg; then
    echo '[include overrides.cfg]' >> ~/printer_data/config/custom/main.cfg
fi

if [ "${1:-}" != "--no-restart" ]; then
    sh "${SCRIPT_DIR}/../../../scripts/firmware_restart.sh"
fi
