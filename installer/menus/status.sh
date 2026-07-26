#!/bin/sh
# Status panel: shows installed setup, versions, and component states.

show_status() {
    clear
    local fw chw cfw profile profile_display
    fw="$(detect_printer_fw)"
    chw="$(detect_carto_hw)"
    cfw="$(detect_carto_fw)"
    profile="$(detect_install_profile)"

    case "$profile" in
        *incomplete*) profile_display=$(c_yellow "$profile") ;;
        *) profile_display=$(c_green "$profile") ;;
    esac

    ui_heading 'SYSTEM STATUS AND DIAGNOSTICS'
    printf '\n Installation\n'
    printf '  %-27s %s\n' 'Setup profile' "$profile_display"
    printf '  %-27s %s\n' 'Printer firmware' "$(c_cyan "$fw")"

    printf '\n Cartographer\n'
    if is_cartographer; then
        printf '  %-27s %s\n' 'State' "$(state_installed)"
        printf '  %-27s %s\n' 'Hardware' "$(c_cyan "${chw:-unknown}")"
        printf '  %-27s %s\n' 'Firmware' "$(c_cyan "${cfw:-unknown}")"
        printf '  %-27s %s\n' 'Mount profile' "$(c_cyan "$(detect_carto_offset_label)")"
    else
        printf '  %-27s %s\n' 'State' "$(state_not_installed)"
    fi

    printf '\n Bootstrap\n'
    status_line 'Entware (opkg, git, curl)' is_entware
    status_line 'better-root ($HOME -> UDISK)' is_better_root
    status_line 'better-init (PATH/profile.d)' is_better_init

    printf '\n Core components\n'
    status_line 'cartographer' is_cartographer
    status_line 'moonraker' is_moonraker
    status_line 'fluidd' is_fluidd
    status_line 'macros (start_print/m191/bed_mesh)' is_macros
    status_line 'screws_tilt_adjust' is_screws_tilt
    status_line 'abort_homing' is_abort_homing
    status_line 'skip-setup' is_skip_setup

    printf '\n Optional extras\n'
    status_line 'axis_twist_compensation' is_axis_twist
    status_line 'secure-auth' is_secure_auth
    status_line 'R3MEN bed thermistor profile' is_r3men_bed
    if [ -f "$INSTALLER_DIR/installer/extras/kamp-adaptive-purge/install.sh" ]; then
        status_line 'KAMP adaptive purge' is_kamp
    fi
    if is_cartographer; then
        if is_carto_plate_workflow; then
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_installed)"
        elif is_carto_macros || is_surface_wrap; then
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_incomplete)"
        else
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_not_installed)"
        fi

        printf '\n Maintenance\n'
        if is_prtouch_clean; then
            printf '  %-43s %s\n' 'prtouch_v3 SAVE_CONFIG clean' "$(state_complete)"
        else
            printf '  %-43s %s\n' 'prtouch_v3 SAVE_CONFIG clean' "$(state_available)"
        fi
    fi
    printf '\n'
    press_enter
}
