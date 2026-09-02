#!/bin/sh
# Per-feature install detection. Each function returns 0 if installed, 1 if not.

is_entware()       { [ -x /opt/bin/opkg ]; }
is_better_root()   { grep -q '^root:.*:/mnt/UDISK/root:' /etc/passwd 2>/dev/null; }
is_cartographer()  { [ -f "$PRINTER_CFG_DIR/custom/cartographer.cfg" ] || \
                     grep -q '^\[cartographer\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null; }
is_moonraker()     { [ -d /mnt/UDISK/printer_data/moonraker ] || [ -f /mnt/UDISK/printer_data/config/moonraker.conf ]; }
is_fluidd()        { grep -lq 'crealityk2' /usr/share/fluidd/assets/*.js 2>/dev/null; }
is_macros() {
    local custom="$PRINTER_CFG_DIR/custom"
    local main="$custom/main.cfg"
    [ -e "$custom/start_print.cfg" ] &&
    [ -e "$custom/m191.cfg" ] &&
    [ -e "$custom/bed_mesh.cfg" ] &&
    [ -f "$custom/overrides.cfg" ] &&
    [ -f "$main" ] &&
    grep -q '^\[include start_print\.cfg\]$' "$main" 2>/dev/null &&
    grep -q '^\[include m191\.cfg\]$' "$main" 2>/dev/null &&
    grep -q '^\[include bed_mesh\.cfg\]$' "$main" 2>/dev/null &&
    grep -q '^\[include overrides\.cfg\]$' "$main" 2>/dev/null
}
is_kamp() {
    local custom="$PRINTER_CFG_DIR/custom"
    local main="$custom/main.cfg"
    [ -f "$custom/Line_Purge.cfg" ] &&
    grep -q 'k2-improvements: balance LINE_PURGE retraction before slicer travel' \
        "$custom/Line_Purge.cfg" 2>/dev/null &&
    [ -f "$custom/kamp_settings.cfg" ] &&
    [ -f "$main" ] &&
    grep -q '^\[include kamp_settings\.cfg\]$' "$main" 2>/dev/null &&
    grep -q '^\[include Line_Purge\.cfg\]$' "$main" 2>/dev/null &&
    grep -rEhq '^\[exclude_object\]' "$PRINTER_CFG_DIR" 2>/dev/null
}
is_screws_tilt()   { [ -L "$PRINTER_CFG_DIR/custom/screws_tilt_adjust.cfg" ]; }
is_screws_tilt_firmware_restart() {
    is_screws_tilt &&
    [ -f /mnt/UDISK/root/.k2-improvements/installer-state/screws-tilt-firmware-restart-v1 ]
}
is_r3men_bed() {
    grep -qE '^\[thermistor R3men_bed\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null &&
    grep -qE '^[[:space:]]*sensor_type:[[:space:]]*R3men_bed' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null
}
is_obico()         { [ -d /mnt/UDISK/moonraker-obico ]; }
is_secure_auth()   { grep -Fq '# k2-improvements: secure-auth installed' /etc/init.d/dropbear 2>/dev/null; }
is_skip_setup()    {
    command -v jq >/dev/null 2>&1 &&
        jq -e '.user_info.self_test_sw == 0' \
            /mnt/UDISK/creality/userdata/config/system_config.json \
            >/dev/null 2>&1
}
is_axis_twist() {
    local custom="$PRINTER_CFG_DIR/custom"
    local cfg="$custom/axis_twist_compensation.cfg"
    local main="$custom/main.cfg"
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    [ -e "$cfg" ] &&
    grep -q '^\[axis_twist_compensation\]$' "$cfg" 2>/dev/null &&
    [ -f "$main" ] &&
    grep -q '^\[include axis_twist_compensation\.cfg\]$' "$main" 2>/dev/null &&
    [ -e "$klipper_dir/klippy/extras/axis_twist_compensation.py" ]
}
is_stock_probe() { ! is_cartographer; }
is_plate_aware_mesh() {
    local custom="$PRINTER_CFG_DIR/custom"
    local cfg="$custom/plate_aware_mesh.cfg"
    local main="$custom/main.cfg"
    [ -e "$cfg" ] &&
    grep -q '^\[gcode_macro _PLATE_AWARE_MESH\]$' "$cfg" 2>/dev/null &&
    [ -f "$main" ] &&
    grep -q '^\[include plate_aware_mesh\.cfg\]$' "$main" 2>/dev/null
}
is_abort_homing() {
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    grep -q '_handle_force_stop_homing' "$klipper_dir/klippy/webhooks.py" 2>/dev/null &&
    grep -q 'can_force_stop_homing' "$klipper_dir/klippy/webhooks.py" 2>/dev/null
}
is_abort_homing_firmware_restart() {
    is_abort_homing &&
    [ -f /mnt/UDISK/root/.k2-improvements/installer-state/abort-homing-firmware-restart-v1 ]
}
is_save_config_restart() {
    local root_configfile="${HOME:-/mnt/UDISK/root}/klipper/klippy/configfile.py"
    local system_configfile="${KLIPPER_DIR:-/usr/share/klipper}/klippy/configfile.py"
    grep -q "gcode.request_restart('firmware_restart')" \
        "$root_configfile" "$system_configfile" 2>/dev/null
}
is_better_init()   { [ -f /etc/profile.d/better-init.sh ]; }

is_surface_wrap()  { grep -q 'surface-selection wrapper' "$PRINTER_CFG_DIR/custom/start_print.cfg" 2>/dev/null; }
is_carto_macros()  { [ -L "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ] || \
                     [ -f "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ]; }
is_carto_plate_workflow() { is_carto_macros && is_surface_wrap; }
is_carto_offset_set() { is_cartographer; }  # always "set" if cartographer is installed (some value is always there)
is_motor_guard()   { grep -q 'motor-state-guard' "$PRINTER_CFG_DIR/custom/start_print.cfg" 2>/dev/null; }

# Returns a human label for the currently-installed cartographer offset preset.
# Echoes one of: "Jamin", "JimmyV", "custom (x=N y=N)", "(no cartographer)"
detect_carto_offset_label() {
    local cfg="$PRINTER_CFG_DIR/custom/cartographer.cfg"
    local overrides="$PRINTER_CFG_DIR/custom/overrides.cfg"
    [ -f "$cfg" ] || { echo "(no cartographer)"; return; }

    # cartographer.cfg supplies the baseline; matching keys in overrides.cfg
    # are included later and therefore represent the effective values.
    local x=$(awk '/^\[cartographer\]/{f=1; next} f && /^\[/ {f=0} f && /^[ \t]*x_offset[ \t]*:/ {sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]*#.*$/, ""); print; exit}' "$cfg")
    local y=$(awk '/^\[cartographer\]/{f=1; next} f && /^\[/ {f=0} f && /^[ \t]*y_offset[ \t]*:/ {sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]*#.*$/, ""); print; exit}' "$cfg")
    if [ -f "$overrides" ]; then
        local override_x=$(awk '/^\[cartographer\]/{f=1; next} f && /^\[/ {f=0} f && /^[ \t]*x_offset[ \t]*:/ {sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]*#.*$/, ""); print; exit}' "$overrides")
        local override_y=$(awk '/^\[cartographer\]/{f=1; next} f && /^\[/ {f=0} f && /^[ \t]*y_offset[ \t]*:/ {sub(/^[^:]*:[ \t]*/, ""); sub(/[ \t]*#.*$/, ""); print; exit}' "$overrides")
        [ -n "$override_x" ] && x="$override_x"
        [ -n "$override_y" ] && y="$override_y"
    fi
    case "${x:-?} ${y:-?}" in
        "0 -15") echo "Jamin (x=0 y=-15)" ;;
        "0 36")  echo "JimmyV (x=0 y=36)" ;;
        *)       echo "custom (x=${x:-?} y=${y:-?})" ;;
    esac
}
is_homing_hasattr() { grep -q "hasattr.*get_suspended_det_status" "$KLIPPER_DIR/klippy/extras/homing.py" 2>/dev/null; }
is_prtouch_clean() { ! grep -q '^#\*# \[prtouch_v3\]$' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null; }

# Shared essentials installed by both recommended setup paths.
is_essentials_core() {
    is_entware &&
    is_better_root &&
    is_better_init &&
    is_skip_setup &&
    is_moonraker &&
    is_fluidd &&
    is_screws_tilt &&
    is_abort_homing &&
    is_save_config_restart &&
    is_macros
}

# Human-readable setup selected through the recommended installers.
detect_install_profile() {
    if is_cartographer; then
        if is_essentials_core; then
            echo "Cartographer"
        else
            echo "Cartographer (incomplete)"
        fi
    elif is_essentials_core; then
        echo "stock probe / no-Cartographer"
    else
        echo "not installed / incomplete"
    fi
}

# Pretty-print a feature's status. Args: label, detector_function_name
status_line() {
    local label="$1"
    local fn="$2"
    if "$fn"; then
        printf '  %-43s %s\n' "$label" "$(state_installed)"
    else
        printf '  %-43s %s\n' "$label" "$(state_not_installed)"
    fi
}
