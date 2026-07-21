#!/bin/sh
# Top-level menu loop. Sourced by menu.sh.

main_menu() {
    while :; do
        clear
        local fw=$(detect_printer_fw)
        local chw=$(detect_carto_hw)
        local setup=$(detect_install_profile)

            printf '\n=== K2 Plus Installer ===  fw: %s  carto: %s\n' "$fw" "${chw:-unknown}"
            printf '    setup: %s\n\n' "$setup"
            printf '  1. Status — show what is installed\n'
            printf '  2. Install stock probe / no-Cartographer setup\n'
            printf '  3. Install Cartographer setup\n'
            printf '  4. Core features (Cartographer stack) ▶\n'
            printf '  5. Extras (optional features / patches) ▶\n'
            printf '  6. Cartographer firmware flash ▶\n'
            printf '  7. Factory reset / cleanup tools ▶\n'
            printf '  8. Update installer (git pull)\n'
            printf '  0. Exit\n\n'
            printf 'Choose [0-8]: '
            read -r c
            case "$c" in
                1) show_status ;;
                2) menu_install_no_carto ;;
                3) menu_install_all ;;
                4) menu_features ;;
                5) menu_extras ;;
                6) menu_carto_fw ;;
                7) menu_factory_reset ;;
                8) menu_update_installer ;;
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
