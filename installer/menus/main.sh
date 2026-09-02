#!/bin/sh
# Top-level workflow menu. Sourced by menu.sh.

detect_installer_branch() {
    if [ -d "$INSTALLER_DIR/.git" ]; then
        git -C "$INSTALLER_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || echo 'detached'
    else
        echo 'not a git checkout'
    fi
}

main_menu() {
    while :; do
        clear
        local fw chw cfw setup branch pending_updates update_state
        fw="$(detect_printer_fw)"
        chw="$(detect_carto_hw)"
        cfw="$(detect_carto_fw)"
        setup="$(detect_install_profile)"
        branch="$(detect_installer_branch)"
        pending_updates="$(migration_pending_component_count)"
        if [ "$pending_updates" -gt 0 ]; then
            update_state="$(c_yellow "$pending_updates ACTION(S) PENDING")"
        else
            update_state="$(c_dim 'NO ACTIONS PENDING')"
        fi

        ui_rule
        printf ' %s\n' "$(c_cyan 'K2 PLUS COMPATIBILITY INSTALLER')"
        printf '%s\n' '------------------------------------------------------------'
        printf ' Firmware : %s\n' "$(c_cyan "$fw")"
        printf ' Branch   : %s\n' "$(c_cyan "$branch")"
        case "$setup" in
            *incomplete*) printf ' Setup    : %s\n' "$(c_yellow "$setup")" ;;
            *) printf ' Setup    : %s\n' "$(c_green "$setup")" ;;
        esac
        if is_cartographer; then
            printf ' Probe    : %s / firmware %s\n' "$(c_cyan "${chw:-unknown}")" "$(c_cyan "${cfw:-unknown}")"
            printf ' Mount    : %s\n' "$(c_cyan "$(detect_carto_offset_label)")"
        fi
        ui_rule

        printf '\n'
        ui_menu_item 1 'Status and diagnostics'
        ui_menu_item 2 'Install or change setup'
        ui_menu_item 3 'Cartographer tools'
        ui_menu_item 4 'Optional extras'
        ui_menu_item 5 'Maintenance and recovery'
        ui_menu_item 6 'Update installer / apply updates' "$update_state"
        printf '\n  0. Exit\n\nSelect [0-6]: '
        read -r c
        case "$c" in
            1) show_status ;;
            2) menu_install_paths ;;
            3) menu_cartographer_tools ;;
            4) menu_extras ;;
            5) menu_maintenance ;;
            6) menu_update_installer ;;
            0|q|Q) exit 0 ;;
            *) ;;
        esac
    done
}
