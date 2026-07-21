#!/bin/sh
# Top-level menu loop. Sourced by menu.sh.

main_menu() {
    while :; do
        clear
        local fw=$(detect_printer_fw)
        local chw=$(detect_carto_hw)

            printf '\n=== K2 Plus Installer ===  fw: %s  carto: %s\n\n' "$fw" "${chw:-unknown}"
            printf '  1. Status — show what is installed\n'
            printf '  2. Install stock probe / no-Cartographer setup\n'
            printf '  3. Install Cartographer setup\n'
            printf '  4. Features (k2-improvements) ▶\n'
            printf '  5. Extras (K2-Plus patches) ▶\n'
            printf '  6. KAMP adaptive purge ▶\n'
            printf '  7. Cartographer firmware flash ▶\n'
            printf '  8. Factory reset / cleanup tools ▶\n'
            printf '  9. Update installer (git pull)\n'
            printf '  0. Exit\n\n'
            printf 'Choose [0-9]: '
            read -r c
            case "$c" in
                1) show_status ;;
                2)
                    clear
                    printf '\n=== Install stock probe / no-Cartographer setup ===\n\n'
                    printf 'This installs the K2 Improvements core setup for the stock PR Touch probe path.\n'
                    printf 'It does NOT install the Cartographer feature.\n\n'
                    printf 'Included:\n'
                    printf '  - better-init\n'
                    printf '  - skip-setup\n'
                    printf '  - moonraker\n'
                    printf '  - fluidd\n'
                    printf '  - screws_tilt_adjust\n'
                    printf '  - abort_homing\n'
                    printf '  - bed_mesh / m191 / start_print / overrides macros\n\n'
                    printf '%s\n' "$(c_yellow 'WARNING: this will modify Klipper/printer config. Make sure no print is active.')"
                    printf '\n'
                    if confirm "Proceed with stock probe / no-Cartographer setup?"; then
                        sh "$INSTALLER_DIR/no-carto.sh"
                    fi
                    press_enter
                    ;;
                3)
                    clear
                    printf '\n=== Install Cartographer ===\n\n'
                    printf 'This installs the K2 Improvements for the Cartographer feature.\n'
                    printf 'Included:\n'
                    printf '  - better-init\n'
                    printf '  - skip-setup\n'
                    printf '  - moonraker\n'
                    printf '  - fluidd\n'
                    printf '  - screws_tilt_adjust\n'
                    printf '  - cartographer\n'
                    printf '  - abort_homing\n'
                    printf '  - bed_mesh / m191 / start_print / overrides macros\n\n'
                    printf '%s\n' "$(c_yellow 'WARNING: Cartographer must be flashed and installed. Make sure Y-axis spacers are installed if required.')"
                    printf '%s\n' "$(c_yellow 'WARNING: this will modify Klipper/printer config. Make sure no print is active.')"
                    printf '\n'
                    if confirm "Proceed with Cartographer setup?"; then
                        sh "$INSTALLER_DIR/gimme-the-jamin.sh"
                    fi
                    press_enter
                    ;;
                4) menu_features ;;
                5) menu_extras ;;
                6) menu_kamp ;;
                7) menu_carto_fw ;;
                8) menu_factory_reset ;;
                9) menu_update_installer ;;
                0|q|Q) exit 0 ;;
                *) ;;
            esac
    done
}

stub_menu() {
    clear
    printf '\n%s — not yet implemented.\n' "$1"
    printf 'Tracked in installer-v1 milestone.\n\n'
    press_enter
}

menu_update_installer()  {
    clear
    ensure_path
    if [ -d "$INSTALLER_DIR/.git" ]; then
        info "git pull in $INSTALLER_DIR"
        ( cd "$INSTALLER_DIR" && git pull --ff-only )
    else
        warn "$INSTALLER_DIR is not a git checkout — can't auto-update."
        warn "Re-run bootstrap.sh from the host to refresh."
    fi
    press_enter
}
