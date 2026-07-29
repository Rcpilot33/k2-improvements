#!/bin/sh
# Factory reset / cleanup tools sub-menu.

menu_factory_reset() {
    while :; do
        clear
        ui_heading 'FACTORY RESET AND CLEANUP'
        printf '\n'

        printf '%s\n' "$(c_red 'WARNING: These tools are destructive.')"
        printf '%s\n' "$(c_dim 'Choose improved UDISK cleanup + reset, or Creality wipe.sock reset only.')"
        printf '\n'

        printf '  1. Preview improved cleanup\n'
        printf '  2. Run improved cleanup + Creality factory reset\n'
        printf '  3. Run Creality factory reset only (wipe.sock all)\n'
        printf '  0. Back\n\n'
        printf 'Select [0-3]: '
        read -r c

        case "$c" in
            1) factory_reset_dry_run ;;
            2) factory_reset_run ;;
            3) factory_reset_stock_run ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

factory_reset_script_path() {
    echo "$INSTALLER_DIR/scripts/factory-reset-improved.sh"
}

factory_reset_stock_script_path() {
    echo "$INSTALLER_DIR/scripts/factory-reset.sh"
}

factory_reset_dry_run() {
    local script
    script="$(factory_reset_script_path)"

    clear
    printf '\n=== factory-reset-improved dry run ===\n\n'

    if [ ! -f "$script" ]; then
        warn "factory-reset-improved.sh not found: $script"
        press_enter
        return
    fi

    printf '%s\n' "$(c_yellow 'Note: /mnt/UDISK/printer_data contains Klipper config, custom macros, saved meshes, logs, and backups.')"
    printf '\n'

    sh "$script" --dry-run
    printf '\n'
    press_enter
}

factory_reset_run() {
    local script
    script="$(factory_reset_script_path)"

    clear
    printf '\n=== Run factory-reset-improved ===\n\n'

    if [ ! -f "$script" ]; then
        warn "factory-reset-improved.sh not found: $script"
        press_enter
        return
    fi

    printf '%s\n' "$(c_red 'This is destructive.')"
    printf '\n'
    printf 'This will remove most top-level directories under /mnt/UDISK,\n'
    printf 'except /mnt/UDISK/root and /mnt/UDISK/bin, then trigger Creality factory reset.\n\n'
    printf 'This WILL remove /mnt/UDISK/printer_data.\n'
    printf 'That includes Klipper config, custom macros, saved meshes, logs, and backups stored there.\n\n'
    printf 'This may also remove downloaded firmware, timelapse/image folders,\n'
    printf 'K2 Improvements files outside the preserved root path, and other user files.\n\n'
    printf 'Run the dry-run option first if you have not already reviewed what will be removed.\n\n'

    printf 'Type FACTORY RESET to continue: '
    read -r answer

    if [ "$answer" != "FACTORY RESET" ]; then
        warn "confirmation did not match; aborting."
        press_enter
        return
    fi

    printf '\n'
    warn "Running factory-reset-improved now..."
    printf '\n'

    if ! sh "$script" --run; then
        printf '\n'
        printf '%s\n' "$(c_red '============================================================')"
        printf '%s\n' "$(c_red '!!! FACTORY RESET FAILED !!!')"
        printf '%s\n' "$(c_red '============================================================')"
        printf '%s\n' "$(c_red 'The Creality factory wipe was not completed.')"
        printf '%s\n' "$(c_red 'Review the error above before retrying or changing firmware.')"
        printf '%s\n' "$(c_red '============================================================')"
        printf '\n'
        press_enter
        return
    fi

    # A successful wipe.sock request resets the printer and terminates SSH.
    # Do not display a success prompt that could be mistaken for completion
    # after a failed or incomplete reset.
}

factory_reset_stock_run() {
    local script
    script="$(factory_reset_stock_script_path)"

    clear
    printf '\n=== Run Creality factory reset only ===\n\n'

    if [ ! -f "$script" ]; then
        warn "factory-reset.sh not found: $script"
        press_enter
        return
    fi

    printf '%s\n' "$(c_red 'This is destructive.')"
    printf '\n'
    printf 'This sends only "all" to Creality wipe.sock.\n'
    printf 'It does NOT pre-delete directories under /mnt/UDISK.\n\n'
    printf 'Use this for the stock Creality reset behavior or when you specifically\n'
    printf 'do not want factory-reset-improved to remove UDISK directories first.\n\n'
    printf 'Third-party files that Creality does not remove may remain afterward.\n\n'

    printf 'Type CREALITY RESET to continue: '
    read -r answer

    if [ "$answer" != "CREALITY RESET" ]; then
        warn "confirmation did not match; aborting."
        press_enter
        return
    fi

    printf '\n'
    warn "Sending Creality wipe.sock factory reset now..."
    printf '\n'

    if ! sh "$script"; then
        printf '\n'
        printf '%s\n' "$(c_red '============================================================')"
        printf '%s\n' "$(c_red '!!! FACTORY RESET FAILED !!!')"
        printf '%s\n' "$(c_red '============================================================')"
        printf '%s\n' "$(c_red 'Creality wipe.sock did not complete the reset request.')"
        printf '%s\n' "$(c_red 'No improved UDISK cleanup was attempted.')"
        printf '%s\n' "$(c_red 'Review the error above before retrying or changing firmware.')"
        printf '%s\n' "$(c_red '============================================================')"
        printf '\n'
        press_enter
        return
    fi

    # A successful wipe.sock request resets the printer and terminates SSH.
    # There is intentionally no post-success prompt.
}
