#!/bin/sh
# k2-improvements: Cartographer nozzle USB power guard
# Installed only after the user explicitly confirms this USB wiring.
set -eu
FACTORY="${K2_FACTORY_NOZZLE_POWER:-/usr/bin/nozzle_cam_power.sh.k2-factory}"
case "${1:-}" in
    on|off)
        # Both requests keep the probe powered. No periodic GPIO writes needed.
        exec "$FACTORY" on
        ;;
    *) echo 'Usage: nozzle_cam_power.sh {on|off}' >&2; exit 1 ;;
esac
