#!/bin/ash

set -xe

SCRIPT_DIR=$(readlink -f $(dirname ${0}))
RUN_MARKERS=$(mktemp -d /tmp/k2-no-carto.XXXXXX)
trap 'rm -rf "$RUN_MARKERS"' EXIT INT TERM

install_feature() {
    FEATURE=${1}
    if [ ! -f "$RUN_MARKERS/${FEATURE}" ]; then
        K2_DEFER_FIRMWARE_RESTART=1 ${SCRIPT_DIR}/features/${FEATURE}/install.sh
        touch "$RUN_MARKERS/${FEATURE}"
    fi
}

install_feature better-init
install_feature skip-setup
install_feature moonraker
install_feature fluidd
install_feature screws_tilt_adjust
#install_feature cartographer
install_feature abort_homing
install_feature save-config-restart
install_feature macros

if [ -f /tmp/k2-klippy-code-restart-required ]; then
    K2_DEFER_FIRMWARE_RESTART=0 sh ${SCRIPT_DIR}/scripts/klippy_code_restart.sh
else
    K2_DEFER_FIRMWARE_RESTART=0 sh ${SCRIPT_DIR}/scripts/firmware_restart.sh
fi
