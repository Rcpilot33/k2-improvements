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

# Render a camera-only namespace if another add-on owns RUN_SHELL_COMMAND.
stock_camera_private_config() {
    sed -e 's/^\[gcode_shell_command /[k2_camera_command /' \
        -e 's/^    RUN_SHELL_COMMAND /    K2_RUN_CAMERA_COMMAND /' "$1"
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

k2_print_activity_state() {
    local activity
    activity=$(stock_nozzle_camera_curl -fsS --max-time 3 \
        "${MOONRAKER_URL:-http://127.0.0.1:7125}/printer/objects/query?print_stats=state" 2>/dev/null) || { echo unknown; return; }
    printf '%s' "$activity" | python3 -c '
import json, sys
state = json.load(sys.stdin)["result"]["status"]["print_stats"]["state"]
print(state if state in ("printing", "paused", "standby", "complete", "cancelled", "error") else "unknown")
' 2>/dev/null || echo unknown
}

# Menus confirm unknown state before installing. During OTA recovery the
# API can be offline, so only veto a known active job at the restart itself.
k2_require_no_active_job() {
    local state
    state=$(k2_print_activity_state)
    case "$state" in
        printing|paused) echo "E: cannot restart Klipper while the printer is $state" >&2; return 1 ;;
    esac
    return 0
}

stock_nozzle_camera_require_idle() {
    local state answer
    state=$(k2_print_activity_state)
    case "$state" in
        standby|complete|cancelled|error) return 0 ;;
        printing|paused) echo "E: printer is $state" >&2; return 1 ;;
    esac
    [ "${K2_OTA_ACTIVITY_CONFIRM:-0}" = 1 ] && [ -n "${1:-}" ] || return 1
    printf 'Print status unavailable. Confirm on the printer that it is idle before %s. Continue? [y/N]: ' "$1"
    IFS= read -r answer || return 1
    case "$answer" in y|Y|yes|YES) ;; *) return 1 ;; esac
    case "$(k2_print_activity_state)" in
        printing|paused) echo 'E: printer became active during confirmation' >&2; return 1 ;;
    esac
    return 0
}
