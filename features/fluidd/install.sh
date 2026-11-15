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
    echo ${PATH} | grep -q /opt || . /etc/profile.d/entware.sh
fi

if ! command -v unzip > /dev/null; then
    opkg install unzip
fi

# Download and validate before replacing the working UI. No bridge is installed
# on this compatibility test branch: existing settings backends stay unchanged.
STAGING=$(mktemp -d "$HOME/fluidd-stage.XXXXXX")
DOWNLOAD=$(mktemp -d "$HOME/fluidd-download.XXXXXX")
trap 'rm -rf "$STAGING" "$DOWNLOAD"' EXIT
cd "$DOWNLOAD"
python3 "$SCRIPT_DIR/download_build.py" "$DOWNLOAD/fluidd.zip"
python3 "$SCRIPT_DIR/prepare_bundle.py" "$DOWNLOAD/fluidd.zip" "$STAGING"
cd "$HOME"
if [ -e "$HOME/fluidd" ]; then
    if [ ! -e "$HOME/fluidd.before-upgrade-compatibility" ]; then
        cp -a "$HOME/fluidd" "$HOME/fluidd.before-upgrade-compatibility"
    fi
    mv "$HOME/fluidd" "$DOWNLOAD/previous"
fi
if ! mv "$STAGING" "$HOME/fluidd"; then
    [ ! -e "$DOWNLOAD/previous" ] || mv "$DOWNLOAD/previous" "$HOME/fluidd"
    exit 1
fi

# replace the existing Fluidd
rm -fr /usr/share/fluidd
ln -sf ~/fluidd /usr/share/fluidd

# restart nginx
/etc/init.d/nginx restart
# register for updates
mkdir -p ~/printer_data/config/updates
python3 "$SCRIPT_DIR/configure_update_manager.py"
python3 ${SCRIPT_DIR}/../../scripts/moonraker_include.py updates/fluidd.cfg

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
