#!/bin/ash
set -e

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

# these are replacing the default init scripts and MUST be copied
cp -f ${SCRIPT_DIR}/klipper_mcu.init /etc/init.d/klipper_mcu
/etc/init.d/klipper_mcu restart
cp -f ${SCRIPT_DIR}/klipper.init /etc/init.d/klipper
cp -f ${SCRIPT_DIR}/webrtc.init /etc/init.d/webrtc
/etc/init.d/webrtc restart

# need to link wrapper scripts in place
# linking so they get updates
test -d /mnt/UDISK/bin || mkdir -p /mnt/UDISK/bin

ln -sf ${SCRIPT_DIR}/bin/sudo /mnt/UDISK/bin/
ln -sf ${SCRIPT_DIR}/bin/supervisorctl /mnt/UDISK/bin/
ln -sf ${SCRIPT_DIR}/bin/systemctl /mnt/UDISK/bin/

# update the path
echo 'export PATH=/mnt/UDISK/bin:$PATH' > /etc/profile.d/better-init.sh

# Moonraker builds its recurring provider command from the first successful
# service discovery. Reload an installed mainline Moonraker after replacing
# supervisorctl so an older empty or stale command cannot survive a refresh.
# During a fresh setup only Creality's legacy Moonraker exists at this point;
# leave it alone because the mainline Moonraker installer runs later.
if [ "${1:-}" = --defer-moonraker-service ]; then
    echo "I: the queued Moonraker service repair will start and check Moonraker"
elif [ -f /mnt/UDISK/root/moonraker/moonraker/moonraker.py ] && \
   [ -x /etc/init.d/moonraker ]; then
    old_moonraker_pid=
    if [ -r /var/run/moonraker.pid ]; then
        IFS= read -r old_moonraker_pid < /var/run/moonraker.pid || old_moonraker_pid=
    fi
    /etc/init.d/moonraker restart

    # The init action returns before the replacement process binds its API.
    # Require a new live PID as well as port 7125 so a final restart cannot
    # accidentally observe the old process just before it exits.
    echo "I: waiting for replacement Moonraker process"
    count=0
    while :; do
        new_moonraker_pid=
        if [ -r /var/run/moonraker.pid ]; then
            IFS= read -r new_moonraker_pid < /var/run/moonraker.pid || new_moonraker_pid=
        fi
        if [ -n "$new_moonraker_pid" ] && \
           [ "$new_moonraker_pid" != "$old_moonraker_pid" ] && \
           [ -d "/proc/$new_moonraker_pid" ] && \
           nc -z 127.0.0.1 7125; then
            echo "I: replacement Moonraker is accepting connections"
            break
        fi
        if [ "$count" -ge 60 ]; then
            echo "E: replacement Moonraker did not become ready" >&2
            exit 1
        fi
        count=$((count + 1))
        sleep 1
    done
fi

if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" != 1 ]; then
    sh "${SCRIPT_DIR}/../../scripts/klippy_code_restart.sh"
fi
