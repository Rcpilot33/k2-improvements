#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

# Preserve tuned Cartographer offsets on a reinstall. If Cartographer was not
# configured when this run began, any material offsets belong to the stock
# probe and must not carry into the new probe setup.
CARTOGRAPHER_WAS_CONFIGURED=0
if [ -f ~/printer_data/config/custom/cartographer.cfg ]; then
    CARTOGRAPHER_WAS_CONFIGURED=1
fi

cd ${HOME}

# Install or safely migrate the plugin to the update-manager source.
sh "${SCRIPT_DIR}/install_plugin.sh" "${HOME}/cartographer3d-plugin"

echo "I: installing python dependencies"
~/klippy-env/bin/pip install --disable-pip-version-check typing_extensions

# create shim to import cartographer into klipper
cat > ~/klipper/klippy/extras/cartographer.py << 'EOF'
import sys
sys.path.insert(0, '/mnt/UDISK/root/cartographer3d-plugin/src')
from cartographer.extra import *
EOF

# The stock c440x touchscreen expects probe.z_offset, a Creality extension
# that Cartographer's standard probe status does not publish.
sh ${SCRIPT_DIR}/install_touchscreen_compat.sh --no-restart

# check if native USB ACM support is built into kernel
# skip all usb handling (bridge, service) if so
if ! zcat /proc/config.gz 2>/dev/null | grep -q "CONFIG_USB_ACM=y"; then
    # install usb bridge binary
    mkdir -p /mnt/UDISK/bin
    ln -sf ${SCRIPT_DIR}/usb_bridge_new /mnt/UDISK/bin/usb_bridge_new
    chmod +x /mnt/UDISK/bin/usb_bridge_new
    rm -f /mnt/UDISK/bin/cartographer_wrapper.sh /mnt/UDISK/bin/usb_bridge

    # install service
    ln -sf ${SCRIPT_DIR}/cartographer.init /etc/init.d/cartographer
    ln -sf ${SCRIPT_DIR}/cartographer.init /opt/etc/init.d/S50cartographer
    /etc/init.d/cartographer start
    CARTO_SERIAL="/dev/cartographer"
else
    echo "I: native USB ACM support detected, skipping usb bridge"
    CARTO_SERIAL="/dev/ttyACM0"
fi


# update printer config. A reinstall normally has no live PR Touch section;
# when one is present, require the migration to complete successfully.
if grep -q '^[[:space:]]*\[prtouch_v3\][[:space:]]*$' \
    ~/printer_data/config/printer.cfg; then
    python3 "${SCRIPT_DIR}/alter_config.py"
else
    echo "I: stock [prtouch_v3] section is already removed"
fi
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg prtouch_v3.cfg True
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/printer.cfg custom/main.cfg
if [ -f ~/printer_data/config/custom/cartographer.cfg ] && \
    ! cmp -s "${SCRIPT_DIR}/cartographer.cfg" \
        ~/printer_data/config/custom/cartographer.cfg; then
    CARTO_CFG_BACKUP=~/printer_data/config/custom/cartographer.cfg.before-managed-update.$(date +%Y%m%d-%H%M%S)
    cp -p ~/printer_data/config/custom/cartographer.cfg "$CARTO_CFG_BACKUP"
    echo "I: preserved previous Cartographer config at $CARTO_CFG_BACKUP"
fi
cp ${SCRIPT_DIR}/cartographer.cfg ~/printer_data/config/custom
# update serial port based on kernel ACM support
sed -i "s|serial: /dev/cartographer|serial: ${CARTO_SERIAL}|g" ~/printer_data/config/custom/cartographer.cfg
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg cartographer.cfg

# Keep Creality's complete pre-file preparation path available after the real
# PR Touch driver is removed. This only changes reported configuration status.
sh "${SCRIPT_DIR}/install_prtouch_version_compat.sh" --no-restart

# A conversion from the no-Cartographer path already has the shared
# overrides.cfg. Add and organize the Cartographer-only settings without
# replacing existing user values. On a direct install, the macros installer
# repeats this after it creates overrides.cfg.
python3 "${SCRIPT_DIR}/../macros/overrides/cleanup_managed_overrides.py" \
    ~/printer_data/config/custom/overrides.cfg
python3 "${SCRIPT_DIR}/../macros/overrides/ensure_cartographer_overrides.py" \
    ~/printer_data/config/custom/overrides.cfg

if [ "$CARTOGRAPHER_WAS_CONFIGURED" -eq 0 ]; then
    python3 "${SCRIPT_DIR}/../macros/overrides/reset_probe_offsets.py" \
        ~/printer_data/config/custom/overrides.cfg
else
    echo "I: preserving existing Cartographer material offsets"
fi

# install klipper patches
sh "${SCRIPT_DIR}/../prime_tower/install.sh"
K2_DEFER_FIRMWARE_RESTART=1 \
    sh "${SCRIPT_DIR}/../virtual-sdcard-guard/install.sh"
rm -f ~/klipper/klippy/mcu.pyc \
    ~/klipper/klippy/serialhdl.pyc \
    ~/klipper/klippy/clocksync.pyc \
    ~/klipper/klippy/__pycache__/mcu.*.pyc \
    ~/klipper/klippy/__pycache__/serialhdl.*.pyc \
    ~/klipper/klippy/__pycache__/clocksync.*.pyc \
    ~/klipper/klippy/extras/homing.pyc \
    ~/klipper/klippy/extras/temperature_mcu.pyc \
    ~/klipper/klippy/extras/__pycache__/homing.*.pyc \
    ~/klipper/klippy/extras/__pycache__/temperature_mcu.*.pyc
ln -sf ${SCRIPT_DIR}/patches/mcu.py ~/klipper/klippy/mcu.py
ln -sf ${SCRIPT_DIR}/patches/serialhdl.py ~/klipper/klippy/serialhdl.py
ln -sf ${SCRIPT_DIR}/patches/clocksync.py ~/klipper/klippy/clocksync.py
sh ${SCRIPT_DIR}/../save-config-restart/install.sh --no-restart
ln -sf ${SCRIPT_DIR}/patches/homing.py ~/klipper/klippy/extras/homing.py
ln -sf ${SCRIPT_DIR}/patches/temperature_mcu.py ~/klipper/klippy/extras/temperature_mcu.py
rm -f ~/klipper/klippy/extras/k2_cartographer_scan_guard.pyc \
    ~/klipper/klippy/extras/__pycache__/k2_cartographer_scan_guard.*.pyc
ln -sf ${SCRIPT_DIR}/k2_cartographer_scan_guard.py \
    ~/klipper/klippy/extras/k2_cartographer_scan_guard.py
rm -f ~/klipper/klippy/extras/k2_safe_move_z.pyc \
    ~/klipper/klippy/extras/__pycache__/k2_safe_move_z.*.pyc
ln -sf ${SCRIPT_DIR}/patches/k2_safe_move_z.py \
    ~/klipper/klippy/extras/k2_safe_move_z.py
rm -f ~/klipper/klippy/extras/bed_mesh.py*
ln -sf ${SCRIPT_DIR}/patches/bed_mesh.py ~/klipper/klippy/extras/bed_mesh.py
python3 "${SCRIPT_DIR}/patch_probe_offsets.py" \
    ~/klipper/klippy/extras/probe.py

# install toggle script
mkdir -p /mnt/UDISK/bin
ln -sf ${SCRIPT_DIR}/cartographer.sh /mnt/UDISK/bin/cartographer.sh

# register for updates
if [ -f ~/printer_data/config/moonraker.conf ]; then
    echo "I: registering cartographer update manager"
    mkdir -p ~/printer_data/config/updates
    cp ${SCRIPT_DIR}/update-manager.cfg ~/printer_data/config/updates/cartographer.cfg
    python3 "${SCRIPT_DIR}/../../scripts/moonraker_include.py" updates/cartographer.cfg

    # Permit Moonraker's machine service API to manage Cartographer. A prior
    # no-Cartographer install intentionally omits this service until now.
    MOONRAKER_ASVC=/mnt/UDISK/printer_data/moonraker.asvc
    touch "$MOONRAKER_ASVC"
    grep -qxF cartographer "$MOONRAKER_ASVC" || echo cartographer >> "$MOONRAKER_ASVC"
else
    echo "W: moonraker not found, skipping update manager registration"
fi

# Install the complete calibration macro engine as part of Cartographer.
# Fluidd shows the default selector and shared actions; named plate selectors
# remain hidden until the optional plate workflow is enabled.
sh "${SCRIPT_DIR}/../../installer/extras/cartographer-macros/install.sh"

sh "${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh"
