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

# clone cartographer plugin
if [ ! -d cartographer3d-plugin/.git ]; then
    echo "I: cloning cartographer plugin"
    if [ -d cartographer3d-plugin ]; then
        rm -rf cartographer3d-plugin
    fi
    git clone https://github.com/Jacob10383/cartographer3d-plugin.git
fi

echo "I: installing python dependencies"
~/klippy-env/bin/pip install --disable-pip-version-check typing_extensions

# create shim to import cartographer into klipper
cat > ~/klipper/klippy/extras/cartographer.py << 'EOF'
import sys
sys.path.insert(0, '/mnt/UDISK/root/cartographer3d-plugin/src')
from cartographer.extra import *
EOF

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


# update printer config
python ${SCRIPT_DIR}/alter_config.py
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg prtouch_v3.cfg True
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/printer.cfg custom/main.cfg
cp ${SCRIPT_DIR}/cartographer.cfg ~/printer_data/config/custom
# update serial port based on kernel ACM support
sed -i "s|serial: /dev/cartographer|serial: ${CARTO_SERIAL}|g" ~/printer_data/config/custom/cartographer.cfg
python ${SCRIPT_DIR}/../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg cartographer.cfg

# A conversion from the no-Cartographer path already has the shared
# overrides.cfg. Add the Cartographer-only touch default without replacing
# any existing user value. On a direct install, the macros installer repeats
# this after it creates overrides.cfg.
sh "${SCRIPT_DIR}/../macros/overrides/enable_cartographer_touch.sh" \
    ~/printer_data/config/custom/overrides.cfg

if [ "$CARTOGRAPHER_WAS_CONFIGURED" -eq 0 ]; then
    python3 "${SCRIPT_DIR}/../macros/overrides/reset_probe_offsets.py" \
        ~/printer_data/config/custom/overrides.cfg
else
    echo "I: preserving existing Cartographer material offsets"
fi

# install klipper patches
ln -sf ${SCRIPT_DIR}/patches/mcu.py ~/klipper/klippy/mcu.py
ln -sf ${SCRIPT_DIR}/patches/serialhdl.py ~/klipper/klippy/serialhdl.py
ln -sf ${SCRIPT_DIR}/patches/clocksync.py ~/klipper/klippy/clocksync.py
ln -sf ${SCRIPT_DIR}/patches/configfile.py ~/klipper/klippy/configfile.py
ln -sf ${SCRIPT_DIR}/patches/homing.py ~/klipper/klippy/extras/homing.py
ln -sf ${SCRIPT_DIR}/patches/temperature_mcu.py ~/klipper/klippy/extras/temperature_mcu.py
rm -f ~/klipper/klippy/extras/bed_mesh.py*
ln -sf ${SCRIPT_DIR}/patches/bed_mesh.py ~/klipper/klippy/extras/bed_mesh.py
sed -i 's/self\.use_offsets = False/self.use_offsets = True/g' ~/klipper/klippy/extras/probe.py || true

# install toggle script
mkdir -p /mnt/UDISK/bin
ln -sf ${SCRIPT_DIR}/cartographer.sh /mnt/UDISK/bin/cartographer.sh

# register for updates
if [ -f ~/printer_data/config/moonraker.conf ]; then
    echo "I: registering cartographer update manager"
    mkdir -p ~/printer_data/config/updates
    cp ${SCRIPT_DIR}/update-manager.cfg ~/printer_data/config/updates/cartographer.cfg
    python3 ~/k2-improvements/scripts/moonraker_include.py updates/cartographer.cfg

    # Permit Moonraker's machine service API to manage Cartographer. A prior
    # no-Cartographer install intentionally omits this service until now.
    MOONRAKER_ASVC=/mnt/UDISK/printer_data/moonraker.asvc
    touch "$MOONRAKER_ASVC"
    grep -qxF cartographer "$MOONRAKER_ASVC" || echo cartographer >> "$MOONRAKER_ASVC"
else
    echo "W: moonraker not found, skipping update manager registration"
fi

echo "I: restarting klipper"
/etc/init.d/klipper restart
