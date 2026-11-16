#!/bin/ash
set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

# Parse arguments
SKIP_CAM=0
ARCHIVE=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --nocam) SKIP_CAM=1 ;;
        --archive)
            [ "$#" -ge 2 ] || { echo 'E: --archive requires a local fluidd.zip path'; exit 1; }
            ARCHIVE=$(readlink -f "$2")
            [ -f "$ARCHIVE" ] || { echo 'E: test archive does not exist'; exit 1; }
            shift
            ;;
        *) echo "E: unknown Fluidd option: $1"; exit 1 ;;
    esac
    shift
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

if [ -e /usr/share/fluidd ] && [ ! -L /usr/share/fluidd ] &&
   [ -e /usr/share/fluidd.before-k2-cards ]; then
    echo 'E: existing /usr/share/fluidd backup requires review'
    exit 1
fi

STAGING=$(mktemp -d "$HOME/fluidd-stage.XXXXXX")
DOWNLOAD=$(mktemp -d "$HOME/fluidd-download.XXXXXX")
trap 'rm -rf "$STAGING" "$DOWNLOAD"' EXIT
if [ -z "$ARCHIVE" ]; then
    cd "$DOWNLOAD"
    python3 "$SCRIPT_DIR/download_build.py" "$DOWNLOAD/fluidd.zip"
    ARCHIVE="$DOWNLOAD/fluidd.zip"
fi
python3 "$SCRIPT_DIR/prepare_bundle.py" "$ARCHIVE" "$STAGING"
python3 "$SCRIPT_DIR/configure_device.py"
cd "$HOME"
# Keep the first known UI for rollback; activate only a fully validated build.
if [ -e "$HOME/fluidd" ]; then
    if [ ! -e "$HOME/fluidd.before-k2-cards" ]; then
        cp -a "$HOME/fluidd" "$HOME/fluidd.before-k2-cards"
    fi
    mv "$HOME/fluidd" "$DOWNLOAD/previous"
fi
if ! mv "$STAGING" "$HOME/fluidd"; then
    [ ! -e "$DOWNLOAD/previous" ] || mv "$DOWNLOAD/previous" "$HOME/fluidd"
    exit 1
fi

# replace the existing Fluidd
if [ -L /usr/share/fluidd ]; then
    rm -f /usr/share/fluidd
elif [ -e /usr/share/fluidd ]; then
    [ ! -e /usr/share/fluidd.before-k2-cards ] || {
        echo 'E: existing /usr/share/fluidd backup requires review'; exit 1;
    }
    mv /usr/share/fluidd /usr/share/fluidd.before-k2-cards
fi
ln -s "$HOME/fluidd" /usr/share/fluidd

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
python3 "$SCRIPT_DIR/configure_device.py" --check --live
