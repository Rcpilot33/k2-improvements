#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

# Parse arguments
SKIP_CAM=0
for arg in "$@"; do
    case "$arg" in
        --nocam) SKIP_CAM=1 ;;
    esac
done

# DEPENDS: moonraker
if [ ! -f /mnt/UDISK/root/printer_data/config/moonraker.conf ]; then
    echo "E: you must have updated moonraker first!"
    exit 1
fi

cd ${HOME}

# MUST have Entware installed
if [ ! -f /opt/bin/opkg ]; then
    echo "E: you must have entware installed!"
    exit 1
fi

# handle entware being installed in the current login
if [ -f /etc/profile.d/entware.sh ]; then
    echo ${PATH} | grep -q /opt || source /etc/profile.d/entware.sh
fi

if ! type -p unzip > /dev/null; then
    opkg install unzip
fi

rm -fr fluidd

mkdir -p fluidd
cd fluidd
python3 ${SCRIPT_DIR}/get_latest_release.py Jacob10383/fluidd
unzip fluidd.zip
rm -f fluidd.zip
cd ..

# replace the existing Fluidd
rm -fr /usr/share/fluidd
ln -sf ~/fluidd /usr/share/fluidd

# restart nginx
/etc/init.d/nginx restart
# register for updates
mkdir -p ~/printer_data/config/updates
cp ${SCRIPT_DIR}/update-manager.cfg ~/printer_data/config/updates/fluidd.cfg
python3 ~/k2-improvements/scripts/moonraker_include.py updates/fluidd.cfg

# TODO: should this should be gated on a port check?
# wait for everything to be ready
sleep 5
if [ "${SKIP_CAM}" -eq 0 ]; then
    python3 ${SCRIPT_DIR}/create_camera.py
fi

/etc/init.d/moonraker restart

# Do not return to a parent installer until Moonraker is accepting requests
# again.  The stock-probe and Cartographer workflows install additional
# components immediately after Fluidd, and those components request a
# FIRMWARE_RESTART through Moonraker.
echo "I: waiting for Moonraker after Fluidd restart"
count=0
while ! nc -z 127.0.0.1 7125; do
    if [ "$count" -ge 60 ]; then
        echo "E: Moonraker did not return after Fluidd restart" >&2
        exit 1
    fi
    count=$((count + 1))
    sleep 1
done
echo "I: Moonraker is accepting connections"
