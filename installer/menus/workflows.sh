#!/bin/sh
# Workflow-oriented menu groups. The underlying installers remain in their
# original locations so existing symlinks and upstream paths stay stable.

menu_install_paths() {
    while :; do
        clear
        ui_heading 'INSTALL OR CHANGE SETUP'
        printf '\n Current setup: %s\n\n' "$(c_cyan "$(detect_install_profile)")"

        if is_cartographer; then
            ui_menu_item 1 'Return to stock PR Touch' "$(c_yellow 'RECOVERY - PLANNED')"
            ui_menu_item 2 'Repair or complete Cartographer setup' "$(state_installed)"
        else
            local profile
            profile="$(detect_install_profile)"
            case "$profile" in
                'stock probe / no-Cartographer')
                    ui_menu_item 1 'Repair stock probe / no-Cartographer setup' "$(state_installed)"
                    ui_menu_item 2 'Convert stock setup to Cartographer' "$(state_available)"
                    ;;
                *)
                    ui_menu_item 1 'Install stock probe / no-Cartographer setup' "$(state_available)"
                    ui_menu_item 2 'Install Cartographer setup' "$(state_available)"
                    ;;
            esac
        fi

        printf '\n  0. Back\n\nSelect [0-2]: '
        read -r c
        case "$c" in
            1)
                if is_cartographer; then
                    show_return_to_stock_planned
                else
                    menu_install_no_carto
                fi
                ;;
            2) menu_install_all ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

show_return_to_stock_planned() {
    clear
    ui_heading 'RETURN TO STOCK PR TOUCH'
    printf '\n%s\n\n' "$(c_yellow 'RECOVERY WORKFLOW - NOT YET IMPLEMENTED')"
    printf 'The existing no-Cartographer installer does not safely remove an active\n'
    printf 'Cartographer setup. A future recovery workflow will restore PR Touch,\n'
    printf 'remove Cartographer overrides and services, repair the stock setup, and\n'
    printf 'require a full power cycle before homing.\n\n'
    printf 'Until that workflow is implemented and tested, use a known-good backup\n'
    printf 'or a factory reset instead of attempting a partial conversion here.\n'
    press_enter
}

menu_cartographer_tools() {
    while :; do
        clear
        local chw cfw usb offset normal_flash_state dfu_flash_state
        chw="$(detect_carto_hw)"
        cfw="$(detect_carto_fw)"
        usb="$(detect_carto_usb_state)"
        offset="$(detect_carto_offset_label)"

        case "$usb" in
            *'runtime USB detected'*|*'Katapult bootloader detected'*)
                normal_flash_state=$(c_green 'READY')
                dfu_flash_state=$(state_recovery)
                ;;
            *'DFU recovery mode detected'*)
                normal_flash_state=$(c_yellow 'USE DFU RECOVERY')
                dfu_flash_state=$(c_green 'READY')
                ;;
            *)
                normal_flash_state=$(state_requires 'USB PROBE')
                dfu_flash_state=$(state_recovery)
                ;;
        esac

        ui_heading 'CARTOGRAPHER TOOLS'
        printf '\n Hardware : %s\n' "$(c_cyan "${chw:-unknown}")"
        printf ' Firmware : %s\n' "$(c_cyan "${cfw:-unknown}")"
        printf ' USB      : %s\n' "$(c_cyan "${usb:-unknown}")"
        printf ' Mount    : %s\n\n' "$(c_cyan "$offset")"

        ui_menu_item 1 'Normal USB / Katapult firmware flash' "$normal_flash_state"
        ui_menu_item 2 'DFU recovery flash' "$dfu_flash_state"
        if is_cartographer; then
            ui_menu_item 3 'Select mount and probe offsets' "$(c_green 'CONFIGURED')"
            ui_menu_item 4 'Calibration and setup checklist' "$(state_available)"
        else
            ui_menu_item 3 'Select mount and probe offsets' "$(state_requires 'CARTOGRAPHER')"
            ui_menu_item 4 'Calibration and setup checklist' "$(state_requires 'CARTOGRAPHER')"
        fi
        ui_menu_item 5 'Firmware and DFU notes' "$(state_available)"

        printf '\n  0. Back\n\nSelect [0-5]: '
        read -r c
        case "$c" in
            1) carto_fw_launch ;;
            2) carto_fw_dfu_launch ;;
            3) run_extra_name cartographer-offset-setup ;;
            4) show_cartographer_setup_checklist ;;
            5) menu_carto_fw_notes ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

menu_carto_fw_notes() {
    while :; do
        clear
        ui_heading 'CARTOGRAPHER FIRMWARE NOTES'
        printf '\n  1. Normal USB / Katapult flashing notes\n'
        printf '  2. DFU recovery notes\n'
        printf '  0. Back\n\nSelect [0-2]: '
        read -r c
        case "$c" in
            1) carto_fw_show_katapult_notes ;;
            2) carto_fw_show_dfu_notes ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

show_cartographer_setup_checklist() {
    clear
    ui_heading 'CARTOGRAPHER SETUP CHECKLIST'
    if ! is_cartographer; then
        printf '\n%s\n' "$(c_yellow 'Cartographer must be installed before calibration.')"
        press_enter
        return
    fi

    cat <<'EOF'

  1. Confirm the correct physical mount and offset preset is selected.
  2. Power-cycle the printer before the next G28 after any installer change,
     SAVE_CONFIG, or FIRMWARE_RESTART.
EOF
    if is_carto_plate_workflow; then
        cat <<'EOF'
  3. Cartographer plate profiles and automatic selection are installed. With
     the correct plate on the bed, calibrate the matching profiles in Fluidd:

       Epoxy Resin Plate  -> A31 / A32 / A33
       High Temp Plate    -> A41 / A42 / A43
       Textured PEI Plate -> A21 / A22 / A23
       Customized Plate   -> A51 / A52 / A53

     Run its scan and touch calibration buttons, then run:

       BED_MESH_CALIBRATE

  4. The plate selected in your slicer automatically loads the matching
     calibrated Cartographer models.
EOF
    else
        if is_carto_macros || is_surface_wrap; then
            cat <<'EOF'
  3. The optional Cartographer plate workflow is INCOMPLETE. Open Extras and
     run "Cartographer plate workflow" to install its missing
     component before relying on automatic plate selection.
EOF
        else
            cat <<'EOF'
  3. Optional per-plate profiles and automatic selection are not installed.
     For that workflow, install "Cartographer plate workflow"
     from Extras. It supplies the predefined Fluidd buttons and slicer wrapper
     together.
EOF
        fi
        cat <<'EOF'
  4. Until then, follow the standard Cartographer calibration workflow for the
     active default plate; slicer plate selection will not switch models.
EOF
    fi
    cat <<'EOF'
  5. Test homing and probing before starting a print.

EOF
    press_enter
}

menu_maintenance() {
    while :; do
        clear
        ui_heading 'MAINTENANCE AND RECOVERY'
        printf '\n'
        ui_menu_item 1 'Core component installer' "$(c_cyan 'OPEN MENU')"
        ui_menu_item 2 'PR Touch SAVE_CONFIG cleanup' "$(if is_prtouch_clean; then state_complete; else state_available; fi)"
        ui_menu_item 3 'Factory reset and cleanup tools' "$(state_destructive)"

        printf '\n  0. Back\n\nSelect [0-3]: '
        read -r c
        case "$c" in
            1) menu_features ;;
            2) run_extra_name prtouch-cleanup ;;
            3) menu_factory_reset ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}
