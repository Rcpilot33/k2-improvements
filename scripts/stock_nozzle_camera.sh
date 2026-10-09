#!/bin/sh
# Shared stock-camera compatibility checks. Sourcing this file changes nothing.

_stock_camera_cfg_value() {
    [ -f "$1" ] || return 0
    awk -v wanted="$2" -v key="$3" '
        /^\[/ { section = $0 }
        section == "[" wanted "]" && $0 ~ "^[ \t]*" key "[ \t]*:" {
            sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]*#.*$/, "")
            sub(/[ \t]*$/, ""); print; exit
        }
    ' "$1"
}

stock_nozzle_camera_is_jimmyv() {
    local cfg_root baseline overrides x y value
    cfg_root="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
    baseline="$cfg_root/custom/cartographer.cfg"
    overrides="$cfg_root/custom/overrides.cfg"
    [ -f "$baseline" ] || return 1
    if grep -q '^[[:space:]]*#[[:space:]]*cartographer-offset-setup: JimmyV' "$overrides" 2>/dev/null; then
        return 0
    fi
    # An explicitly selected custom mount must not be guessed from its offsets.
    grep -q '^[[:space:]]*#[[:space:]]*cartographer-offset-setup: custom mount' "$overrides" 2>/dev/null && return 1
    x=$(_stock_camera_cfg_value "$baseline" cartographer x_offset)
    y=$(_stock_camera_cfg_value "$baseline" cartographer y_offset)
    value=$(_stock_camera_cfg_value "$overrides" cartographer x_offset)
    [ -z "$value" ] || x=$value
    value=$(_stock_camera_cfg_value "$overrides" cartographer y_offset)
    [ -z "$value" ] || y=$value
    # Recognize earlier installations without picker comments too.
    awk -v x="$x" -v y="$y" 'BEGIN {
        number = "^[-+]?[0-9]+([.][0-9]+)?$"
        exit !(x ~ number && y ~ number && x == 0 && (y == 12 || y == 17 || y == 36))
    }'
}

stock_nozzle_camera_available() {
    # An explicit camera-removal/wiring option stays active until removed,
    # even if the user changes mount profiles before physically rewiring.
    [ ! -e "${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}/custom/k2_nozzle_camera_guard.cfg" ] &&
        ! stock_nozzle_camera_is_jimmyv
}

stock_nozzle_camera_present() {
    local custom bin
    custom="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}/custom"
    bin="${K2_BIN_DIR:-/mnt/UDISK/bin}/nozzle-camera.sh"
    if [ -e "$custom/nozzle_camera.cfg" ] || [ -L "$custom/nozzle_camera.cfg" ] ||
        [ -e "$bin" ] || [ -L "$bin" ] ||
        grep -qE '^\[include[[:space:]]+nozzle_camera\.cfg\]' "$custom/main.cfg" 2>/dev/null; then
        return 0
    fi
    return 1
}

stock_nozzle_camera_mount_compatible() {
    stock_nozzle_camera_available || ! stock_nozzle_camera_present
}

stock_nozzle_camera_require_available() {
    if ! stock_nozzle_camera_available; then
        echo "ERROR: JimmyV mounts replace the factory nozzle camera; stock-camera streaming is unavailable." >&2
        return 1
    fi
}

stock_nozzle_camera_curl() {
    if [ -n "${K2_CURL:-}" ]; then
        "$K2_CURL" "$@"
    elif [ -x /opt/bin/curl ]; then
        /opt/bin/curl "$@"
    else
        curl "$@"
    fi
}

stock_nozzle_camera_require_idle() {
    local activity
    activity=$(stock_nozzle_camera_curl -fsS --max-time 3 \
        "${MOONRAKER_URL:-http://127.0.0.1:7125}/printer/objects/query?print_stats=state") || return 1
    printf '%s' "$activity" | grep -q '"print_stats"' &&
        ! printf '%s' "$activity" | grep -qE '"state"[[:space:]]*:[[:space:]]*"(printing|paused)"' &&
        printf '%s' "$activity" | grep -qE '"state"[[:space:]]*:[[:space:]]*"(standby|complete|cancelled|error)"'
}
