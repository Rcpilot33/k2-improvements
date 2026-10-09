#!/bin/sh
set -eu
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
. "$REPO_ROOT/scripts/stock_nozzle_camera.sh"
MODE="${1:-}"
case "$MODE" in
    --ai-only) MODE=ai-only ;;
    --power) MODE=power ;;
    --refresh) MODE=refresh ;;
    --remove) MODE=remove ;;
    '')
        echo 'JimmyV nozzle-camera replacement:'
        echo '  1. Disable nozzle-camera AI only (Cartographer uses other USB)'
        echo '  2. Disable nozzle-camera AI AND protect nozzle USB rail power'
        echo '  3. Remove protection (refit factory camera / rewire probe first)'
        echo '  0. Back'
        printf 'Select [0-3]: '
        read -r choice
        case "$choice" in
            1) MODE=ai-only ;;
            2)
                printf 'Cartographer is wired to the nozzle-camera USB connector? [y/N]: '
                read -r answer
                case "$answer" in y|Y|yes|YES) MODE=power ;; *) exit 2 ;; esac
                ;;
            3) MODE=remove ;;
            *) exit 2 ;;
        esac
        ;;
    *) echo 'ERROR: invalid nozzle-camera protection option' >&2; exit 1 ;;
esac
if [ "$MODE" != remove ]; then
    stock_nozzle_camera_is_jimmyv || {
        echo 'ERROR: select a JimmyV mount first' >&2; exit 1;
    }
fi
stock_nozzle_camera_require_idle || {
    echo 'ERROR: printer must be confirmed idle before changing camera protection' >&2; exit 1;
}
if [ "$MODE" != remove ] && stock_nozzle_camera_present; then
    sh "$REPO_ROOT/installer/extras/nozzle-camera/uninstall.sh" --no-restart
fi
"${K2_PYTHON:-python3}" "$SCRIPT_DIR/configure.py" "$MODE"
if [ "$MODE" = power ]; then
    "${K2_SYSTEM_ROOT:-}/usr/bin/nozzle_cam_power.sh" on
fi
echo 'I: nozzle-camera protection configured; enclosure-camera AI settings preserved'
echo 'I: USB power was not switched off; use manual flow and pressure-advance calibration'
if [ "$MODE" != remove ]; then
    echo 'I: power-cycle while idle after initial setup so the factory application reloads camera preferences'
fi
sh "$REPO_ROOT/scripts/klippy_code_restart.sh"
