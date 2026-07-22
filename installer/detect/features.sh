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
is_kamp()          { [ -L "$PRINTER_CFG_DIR/custom/Line_Purge.cfg" ]; }
is_screws_tilt()   { [ -L "$PRINTER_CFG_DIR/custom/screws_tilt_adjust.cfg" ]; }
is_r3men_bed() {
    grep -qE '^\[thermistor R3men_bed\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null &&
    grep -qE '^[[:space:]]*sensor_type:[[:space:]]*R3men_bed' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null &&
    grep -qE '^[[:space:]]*max_power:[[:space:]]*0\.8' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null
}
is_obico()         { [ -d /mnt/UDISK/moonraker-obico ]; }
is_secure_auth()   { grep -Fq 'procd_append_param command -s' /etc/init.d/dropbear 2>/dev/null && \
                     grep -Fq 'procd_append_param command -g' /etc/init.d/dropbear 2>/dev/null; }
is_skip_setup()    {
    command -v jq >/dev/null 2>&1 &&
        jq -e '.user_info.self_test_sw == 0' \
            /mnt/UDISK/creality/userdata/config/system_config.json \
            >/dev/null 2>&1
}
is_axis_twist()    { grep -q '^\[axis_twist_compensation\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null; }
is_abort_homing() {
    local klipper_dir="${KLIPPER_DIR:-/usr/share/klipper}"
    grep -q '_handle_force_stop_homing' "$klipper_dir/klippy/webhooks.py" 2>/dev/null &&
    grep -q 'can_force_stop_homing' "$klipper_dir/klippy/webhooks.py" 2>/dev/null
}
is_better_init()   { [ -f /etc/profile.d/better-init.sh ]; }

is_surface_wrap()  { grep -q 'surface-selection wrapper' "$PRINTER_CFG_DIR/custom/start_print.cfg" 2>/dev/null; }
is_carto_macros()  { [ -L "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ] || \
                     [ -f "$PRINTER_CFG_DIR/custom/cartographer_macros.cfg" ]; }
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
        printf '  %s %s\n' "$(c_green '[X]')" "$label"
    else
        printf '  %s %s\n' "$(c_dim '[ ]')" "$label"
    fi
}
