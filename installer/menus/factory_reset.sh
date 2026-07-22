#!/bin/sh
# Factory reset / cleanup tools sub-menu.

menu_factory_reset() {
    while :; do
        clear
        ui_heading 'FACTORY RESET AND CLEANUP'
        printf '\n'

        printf '%s\n' "$(c_red 'WARNING: These tools are destructive.')"
        printf '%s\n' "$(c_dim 'factory-reset-improved removes leftover UDISK directories, then triggers Creality factory reset.')"
        printf '\n'

        printf '  1. Show what factory-reset-improved removes\n'
        printf '  2. Run factory-reset-improved\n'
        printf '  0. Back\n\n'
        printf 'Select [0-2]: '
        read -r c

        case "$c" in
            1) factory_reset_dry_run ;;
            2) factory_reset_run ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

factory_reset_script_path() {
    echo "$INSTALLER_DIR/scripts/factory-reset-improved.sh"
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

    sh "$script" --run

    printf '\n'
    printf '%s\n' "$(c_yellow 'Factory reset command was sent.')"
    printf 'Power-cycle the printer when the reset process is complete.\n\n'
    press_enter
}
