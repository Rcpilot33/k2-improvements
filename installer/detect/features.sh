#!/bin/sh
# Per-feature install detection. Each function returns 0 if installed, 1 if not.

_load_stock_nozzle_camera_helpers() {
    command -v stock_nozzle_camera_available >/dev/null 2>&1 ||
        . "${INSTALLER_DIR:-${SCRIPT_DIR:-/mnt/UDISK/root/k2-improvements}}/scripts/stock_nozzle_camera.sh"
}
is_stock_nozzle_camera_available() {
    _load_stock_nozzle_camera_helpers && stock_nozzle_camera_available
}
is_nozzle_camera_mount_compatible() {
    _load_stock_nozzle_camera_helpers && stock_nozzle_camera_mount_compatible
}
is_nozzle_usb_cartographer() {
    local custom="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}/custom"
    local klipper="${KLIPPER_DIR:-/usr/share/klipper}"
    [ -e "$custom/k2_nozzle_camera_guard.cfg" ] &&
    [ -e "$klipper/klippy/extras/k2_nozzle_camera_guard.py" ] &&
    grep -q '^\[include k2_nozzle_camera_guard\.cfg\]$' "$custom/main.cfg" 2>/dev/null
    [ "$?" -eq 0 ] || return 1
    if grep -q '^# usb_power_hold: 1$' "$custom/k2_nozzle_camera_guard.cfg"; then
        grep -q 'k2-improvements: Cartographer nozzle USB power guard' \
            "${K2_SYSTEM_ROOT:-}/usr/bin/nozzle_cam_power.sh" 2>/dev/null &&
        [ -e "${K2_SYSTEM_ROOT:-}/etc/rc.d/S53k2-nozzle-usb" ]
    fi
}

is_entware()       { [ -x /opt/bin/opkg ]; }
is_better_root()   { grep -q '^root:.*:/mnt/UDISK/root:' /etc/passwd 2>/dev/null; }
is_cartographer() {
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    local config_present=1

    if [ -f "$PRINTER_CFG_DIR/custom/cartographer.cfg" ] || \
       grep -q '^\[cartographer\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null; then
        config_present=0
    fi

    [ "$config_present" -eq 0 ] &&
    [ -e "$klipper_dir/klippy/extras/cartographer.py" ] &&
    grep -q '^class TriggerDispatch' "$klipper_dir/klippy/mcu.py" 2>/dev/null
}
is_moonraker()     { [ -d /mnt/UDISK/printer_data/moonraker ] || [ -f /mnt/UDISK/printer_data/config/moonraker.conf ]; }
is_fluidd()        { grep -ilq 'crealityk2' /usr/share/fluidd/assets/*.js 2>/dev/null; }
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
is_start_print_fast_stop_eligible() {
    command -v detect_printer_fw >/dev/null 2>&1 &&
    command -v printer_fw_at_least >/dev/null 2>&1 &&
    is_macros &&
    printer_fw_at_least "$(detect_printer_fw)" 1.1.5.5
}
is_start_print_fast_stop() {
    local custom="$PRINTER_CFG_DIR/custom"
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    is_start_print_fast_stop_eligible &&
    [ -e "$custom/k2_start_print_fast_stop.cfg" ] &&
    [ -e "$klipper_dir/klippy/extras/k2_start_print_fast_stop.py" ] &&
    grep -q '^\[include k2_start_print_fast_stop\.cfg\]$' \
        "$custom/main.cfg" 2>/dev/null
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
is_nozzle_camera() {
    local custom="$PRINTER_CFG_DIR/custom"
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    [ -e "$custom/nozzle_camera.cfg" ] &&
    [ -x /mnt/UDISK/bin/nozzle-camera.sh ] &&
    [ -e "$klipper_dir/klippy/extras/gcode_shell_command.py" ] &&
    grep -q '^\[include nozzle_camera\.cfg\]$' "$custom/main.cfg" 2>/dev/null
}
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
    grep -q "k2_save_config_restart.sh" \
        "$root_configfile" "$system_configfile" 2>/dev/null &&
    grep -q "gcode.request_restart('restart')" \
        "$root_configfile" "$system_configfile" 2>/dev/null
}
is_virtual_sdcard_guard() {
    local root_vsd="${HOME:-/mnt/UDISK/root}/klipper/klippy/extras/virtual_sdcard.py"
    local system_vsd="${KLIPPER_DIR:-/usr/share/klipper}/klippy/extras/virtual_sdcard.py"
    grep -q 'k2-improvements: terminal multipart upload boundary guard' \
        "$root_vsd" "$system_vsd" 2>/dev/null
}
is_memory_diagnostics() {
    local custom="$PRINTER_CFG_DIR/custom"
    local klipper_dir="${KLIPPER_DIR:-${HOME:-/mnt/UDISK/root}/klipper}"
    [ -e "$custom/memory_diagnostics.cfg" ] &&
    [ -e "$klipper_dir/klippy/extras/memory_diagnostics.py" ] &&
    grep -q '^\[include memory_diagnostics\.cfg\]$' \
        "$custom/main.cfg" 2>/dev/null
}
is_better_init()   { [ -f /etc/profile.d/better-init.sh ]; }

is_surface_wrap()  { grep -q 'surface-selection wrapper' "$PRINTER_CFG_DIR/custom/start_print.cfg" 2>/dev/null; }
is_carto_macros()  { [ -L "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ] || \
                     [ -f "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ]; }
has_settings_ui_overlay() {
    local marker version
    marker="${FLUIDD_DIR:-/usr/share/fluidd}/k2-ui-overlay-support.txt"
    version=$(cat "$marker" 2>/dev/null) || return 1
    case "$version" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$version" -ge 3 ]
}
is_global_touch_offsets() {
    local custom="$PRINTER_CFG_DIR/custom"
    local editor="${KLIPPER_DIR:-${HOME:-/mnt/UDISK/root}/klipper}/klippy/extras/k2_cartographer_offset_editor.py"
    [ -e "$custom/global_touch_offsets.cfg" ] &&
    grep -q '^\[include global_touch_offsets\.cfg\]$' "$custom/main.cfg" 2>/dev/null &&
    [ -e "$editor" ] &&
    has_settings_ui_overlay
}
is_material_z_offsets() {
    local custom="$PRINTER_CFG_DIR/custom"
    local editor="${KLIPPER_DIR:-${HOME:-/mnt/UDISK/root}/klipper}/klippy/extras/k2_material_z_offset_editor.py"
    [ -e "$custom/material_z_offsets.cfg" ] &&
    grep -q '^\[include material_z_offsets\.cfg\]$' "$custom/main.cfg" 2>/dev/null &&
    grep -q 'K2_MATERIAL_Z_APPLY' "$custom/start_print.cfg" 2>/dev/null &&
    [ -e "$editor" ] &&
    has_settings_ui_overlay
}
is_carto_plate_workflow() { is_carto_macros && is_surface_wrap; }
is_carto_offset_set() { is_cartographer; }  # always "set" if cartographer is installed (some value is always there)
is_motor_guard()   { grep -q 'motor-state-guard' "$PRINTER_CFG_DIR/custom/start_print.cfg" 2>/dev/null; }

# Returns a human label for the currently-installed cartographer offset preset.
# Echoes a recognized mount profile, a custom X/Y label, or no Cartographer.
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
        "0 36")  echo "JimmyV legacy (x=0 y=36)" ;;
        "0 12")  echo "JimmyV final no 3DO (x=0 y=12)" ;;
        "0 17")  echo "JimmyV final 3DO (x=0 y=17)" ;;
        *)        echo "custom (x=${x:-?} y=${y:-?})" ;;
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
    is_virtual_sdcard_guard &&
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
