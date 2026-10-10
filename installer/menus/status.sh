#!/bin/sh
# Status panel: shows installed setup, versions, and component states.

show_status() {
    clear
    local fw chw cfw profile profile_display carto_version
    fw="$(detect_printer_fw)"
    carto_version=
    if is_cartographer; then
        carto_version="$(_detect_carto_version_string || true)"
    fi
    chw="$(detect_carto_hw "$carto_version")"
    cfw="$(detect_carto_fw "$carto_version")"
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

    printf '\n Core components\n'
    status_line 'better-init (PATH/profile.d)' is_better_init
    status_line 'skip-setup' is_skip_setup
    status_line 'moonraker' is_moonraker
    status_line 'fluidd' is_fluidd
    status_line 'screws_tilt_adjust' is_screws_tilt
    status_line 'cartographer' is_cartographer
    status_line 'abort_homing' is_abort_homing
    status_line 'SAVE_CONFIG firmware restart protection' is_save_config_restart
    status_line 'virtual SD-card upload guard' is_virtual_sdcard_guard
    status_line 'macros (start_print/m191/bed_mesh)' is_macros

    printf '\n Optional extras\n'
    status_line 'axis_twist_compensation' is_axis_twist
    status_line 'secure-auth' is_secure_auth
    status_line 'R3MEN bed thermistor profile' is_r3men_bed
    status_line 'Stock nozzle camera stream' is_nozzle_camera
    status_line 'Nozzle-camera AI / USB protection' is_nozzle_usb_cartographer
    if [ -f "$INSTALLER_DIR/installer/extras/kamp-adaptive-purge/install.sh" ]; then
        status_line 'KAMP adaptive purge' is_kamp
    fi
    status_line 'Material Z Offsets' is_material_z_offsets
    if ! is_cartographer; then
        status_line 'Plate-aware saved meshes' is_plate_aware_mesh
    fi
    if is_cartographer; then
        if is_carto_plate_workflow; then
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_installed)"
        elif is_surface_wrap; then
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_incomplete)"
        else
            printf '  %-43s %s\n' 'Cartographer plate workflow' "$(state_not_installed)"
        fi
        status_line 'Global Carto Z Offsets' is_global_touch_offsets

        printf '\n Maintenance\n'
        if is_prtouch_clean; then
            printf '  %-43s %s\n' 'prtouch_v3 SAVE_CONFIG clean' "$(state_complete)"
        else
            printf '  %-43s %s\n' 'prtouch_v3 SAVE_CONFIG clean' "$(state_available)"
        fi
    fi
    printf '\n Installer updates\n'
    pending_updates=$(migration_pending_component_count)
    if [ "$pending_updates" -gt 0 ]; then
        printf '  %-43s %s\n' "$pending_updates component action(s) pending" "$(c_yellow 'ACTION NEEDED')"
    else
        printf '  %-43s %s\n' 'Installed components' "$(c_green 'CURRENT')"
    fi
    printf '\n'
    press_enter
}
