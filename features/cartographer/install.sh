#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))
. "$SCRIPT_DIR/mesh_limits.sh"

# Preserve tuned Cartographer offsets on a reinstall. If Cartographer was not
# configured when this run began, any material offsets belong to the stock
# probe and must not carry into the new probe setup.
CARTOGRAPHER_WAS_CONFIGURED=0
if [ -f ~/printer_data/config/custom/cartographer.cfg ] || [ "${K2_KEEP_CARTOGRAPHER_CONFIG:-0}" = 1 ]; then
    CARTOGRAPHER_WAS_CONFIGURED=1
fi

cd ${HOME}

# Install or safely migrate the plugin to the update-manager source.
sh "${SCRIPT_DIR}/install_plugin.sh" "${HOME}/cartographer3d-plugin"

echo "I: installing python dependencies"
~/klippy-env/bin/pip install --disable-pip-version-check typing_extensions==4.16.0

# A partial conversion may already have cartographer.cfg and the core links.
# Retain the original probe state so a retry completes the same conversion.
mkdir -p ~/printer_data/config/custom
pending=~/printer_data/config/custom/.cartographer-install-pending
if [ -f "$pending" ]; then
    read -r CARTOGRAPHER_WAS_CONFIGURED < "$pending"
else
    printf '%s\n' "$CARTOGRAPHER_WAS_CONFIGURED" > "$pending"
fi

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
python3 ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg prtouch_v3.cfg True
python3 ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/printer.cfg custom/main.cfg
if [ "${K2_KEEP_CARTOGRAPHER_CONFIG:-0}" = 1 ]; then
    if ! grep -Eq '^[[:space:]]*\[cartographer\][[:space:]]*$' ~/printer_data/config/printer.cfg; then
        [ -s ~/printer_data/config/custom/cartographer.cfg ] || { echo 'E: restore the saved Cartographer configuration first' >&2; exit 1; }
        python3 "${SCRIPT_DIR}/../../scripts/ensure_included.py" ~/printer_data/config/custom/main.cfg cartographer.cfg
    fi
    echo 'I: retained existing Cartographer configuration during firmware repair'
else
    CARTO_CFG=~/printer_data/config/custom/cartographer.cfg
    CARTO_NEW=$(mktemp "${CARTO_CFG}.new.XXXXXX")
    trap 'rm -f "$CARTO_NEW"' EXIT
    render_cartographer_config "${SCRIPT_DIR}/cartographer.cfg" "$CARTO_SERIAL" > "$CARTO_NEW"
    if [ -f "$CARTO_CFG" ] && ! cmp -s "$CARTO_NEW" "$CARTO_CFG"; then
        CARTO_CFG_BACKUP=~/printer_data/config/custom/cartographer.cfg.before-managed-update.$(date +%Y%m%d-%H%M%S)
        cp -p ~/printer_data/config/custom/cartographer.cfg "$CARTO_CFG_BACKUP"
        echo "I: preserved previous Cartographer config at $CARTO_CFG_BACKUP"
    fi
    chmod 644 "$CARTO_NEW"
    mv "$CARTO_NEW" "$CARTO_CFG"
    trap - EXIT
    python3 ${SCRIPT_DIR}/../../scripts/ensure_included.py \
        ~/printer_data/config/custom/main.cfg cartographer.cfg
fi

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
rm -f ~/klipper/klippy/extras/k2_cartographer_probe_wait.pyc \
    ~/klipper/klippy/extras/__pycache__/k2_cartographer_probe_wait.*.pyc
ln -sf ${SCRIPT_DIR}/k2_cartographer_probe_wait.py \
    ~/klipper/klippy/extras/k2_cartographer_probe_wait.py
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

sh "${SCRIPT_DIR}/register.sh" --refresh-updater

sh "${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh"
rm -f "$pending"
