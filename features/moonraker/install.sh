#!/bin/ash

set -e

SCRIPT_DIR=$(readlink -f $(dirname ${0}))

cd ${HOME}

export TMPDIR=/mnt/UDISK/tmp
mkdir -p "${TMPDIR}"

# MUST have Entware installed
if [ ! -f /opt/bin/opkg ]; then
    echo "E: you must have entware installed!"
    exit 1
fi

# handle entware being installed in the current login
if [ -f /etc/profile.d/entware.sh ]; then
    echo ${PATH} | grep -q /opt || . /etc/profile.d/entware.sh
fi

if [ "${1:-}" != --restore-service ] && ! command -v git > /dev/null; then
    opkg install git
fi

progress() {
    echo "#### ${1}"
}

install_virtualenv() {
    progress "Installing virtualenv ..."
    command -v virtualenv > /dev/null || pip install virtualenv

    # update pip to pull pre-built wheels
    if ! grep -qE '^extra-index-url=https://www.piwheels.org/simple$' /etc/pip.conf; then
        echo 'extra-index-url=https://www.piwheels.org/simple' >> /etc/pip.conf
    fi
}

remove_legacy_symlinks() {
    progress "Removing legacy symlinks ..."
    for ENTRY in moonraker moonraker-env; do
        if [ -L ${ENTRY} ]; then
            rm -f ${ENTRY}
        fi
    done
}

fetch_moonraker() {
    progress "Fetching maintained K2 Moonraker fork ..."
    python3 "$SCRIPT_DIR/source.py" "$HOME/moonraker"
}

create_moonraker_venv() {
    progress "Creating mooonraker venv..."
    # python 3.9.12
    test -d moonraker-env || virtualenv -p /usr/bin/python3 ~/moonraker-env

    ./moonraker-env/bin/pip \
        install \
        --prefer-binary \
        --upgrade \
        --find-links=${SCRIPT_DIR}/wheels \
        --requirement moonraker/scripts/moonraker-requirements.txt

    ./moonraker-env/bin/pip \
        install \
        --prefer-binary \
        lmdb==1.7.3

    python3 ${SCRIPT_DIR}/../../scripts/fix_venv.py ~/moonraker-env
}

install_libs() {
    progress "Installing mooonraker libs ..."
    for LIB in ${SCRIPT_DIR}/libs/*.so*; do
        ln -sf ${LIB} /lib/
    done
}

replace_moonraker() {
    progress "Stopping legacy mooonraker ..."
    if [ -x /etc/init.d/moonraker ]; then /etc/init.d/moonraker stop; fi

    progress "Replacing legacy mooonraker with mainline ..."

    # update init script location for new config file location
    rm -f /etc/rc.d/S*moonraker
    ln -sf ${SCRIPT_DIR}/moonraker.init /etc/init.d/moonraker
    ln -sf ${SCRIPT_DIR}/moonraker.init /opt/etc/init.d/S56moonraker

    # full copy not symlink here
    if [ "${1:-}" != --restore-service ] || [ ! -e /mnt/UDISK/printer_data/config/moonraker.conf ]; then
        cp "${SCRIPT_DIR}/moonraker.conf" /mnt/UDISK/printer_data/config/moonraker.conf
    fi

    progress "Starting mooonraker ..."
    /etc/init.d/moonraker start
}

modify_moonraker_asvc() {
    progress "Modifying moonraker.asvc ..."
    MOONRAKER_ASVC=/mnt/UDISK/printer_data/moonraker.asvc
    mkdir -p "$(dirname "$MOONRAKER_ASVC")"
    touch "$MOONRAKER_ASVC"

    SERVICES="webrtc klipper"
    if [ -e /etc/init.d/cartographer ]; then
        SERVICES="$SERVICES cartographer"
    fi

    for SERVICE in $SERVICES; do
        if ! grep -qxF "$SERVICE" "$MOONRAKER_ASVC"; then
            echo "$SERVICE" >> "$MOONRAKER_ASVC"
        fi
    done
}

wait_for_moonraker() {
    progress "Waiting for moonraker to start ..."
    count=0
    while :; do
        if nc -z 127.0.0.1 7125; then
            [ "${1:-}" = --restore-service ] || return 0
            pid=$(cat /var/run/moonraker.pid 2>/dev/null) || pid=
            if [ -n "$pid" ] && [ "$pid" != "$previous_pid" ] && [ -r "/proc/$pid/cmdline" ] &&
               tr '\000' '\n' < "/proc/$pid/cmdline" | grep -Fxq "$HOME/moonraker/moonraker/moonraker.py"; then
                return 0
            fi
        fi
        if [ $count -gt 60 ]; then
            echo "E: moonraker failed to start!"
            exit 1
        fi
        count=$((count + 1))
        sleep 1
    done
}

if [ "${1:-}" = --restore-service ]; then
    if [ ! -f "$HOME/moonraker/moonraker/moonraker.py" ] || [ ! -x "$HOME/moonraker-env/bin/python" ]; then
        echo "E: managed Moonraker source or Python environment is missing; review the core Moonraker installation." >&2
        exit 1
    fi
    for component in moonraker moonraker-env; do
        if [ -L "$HOME/$component" ] && [ "$(readlink -f "$HOME/$component")" = "$(readlink -f "/usr/share/$component")" ]; then
            echo "E: $HOME/$component points to the stock installation; review the core Moonraker installation." >&2
            exit 1
        fi
    done
    config=/mnt/UDISK/printer_data/config/moonraker.conf
    if { [ -e "$config" ] || [ -L "$config" ]; } && [ ! -s "$config" ]; then
        echo "E: review the empty or broken Moonraker configuration at $config before restarting." >&2
        exit 1
    fi
    install_libs
    modify_moonraker_asvc
    previous_pid=$(cat /var/run/moonraker.pid 2>/dev/null) || previous_pid=
    replace_moonraker --restore-service
    wait_for_moonraker --restore-service
    exit 0
fi

install_virtualenv
remove_legacy_symlinks
fetch_moonraker
create_moonraker_venv
install_libs
modify_moonraker_asvc
replace_moonraker
wait_for_moonraker
