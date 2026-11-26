#!/bin/ash
case "${1:-}" in
    enable)
        echo "Use Install or change setup > Cartographer setup in the installer menu." >&2
        exit 1
        ;;
    disable)
        echo "Return to stock PR Touch requires a known-good stock backup or factory reset. See Maintenance and recovery." >&2
        exit 1
        ;;
    restart)
        bridge_dir=$(dirname "$(readlink -f "$0")")
        . "$bridge_dir/../../scripts/stock_nozzle_camera.sh"
        k2_require_no_active_job || exit 1
        exec /etc/init.d/cartographer restart
        ;;
    *)
        echo "Usage: $0 restart" >&2
        exit 2
        ;;
esac
