#!/bin/sh
# K2-Plus extras (patches not in upstream k2-improvements). Install only.

# name|detector|description|script_path|requires  (one per line; script_path
# relative to INSTALLER_DIR; requires is the name of a function that must
# return 0 for the extra to be installable - empty if no precondition).
_EXTRAS='prtouch-cleanup|is_prtouch_clean|Remove orphan [prtouch_v3] SAVE_CONFIG header|installer/extras/prtouch-cleanup/install.sh|is_cartographer
surface-selection-wrapper|is_surface_wrap|START_PRINT SURFACE= param loads matching scan/touch model|installer/extras/surface-selection-wrapper/install.sh|is_cartographer
cartographer-offset-setup|is_carto_offset_set|Cartographer probe X/Y offset (Jamin/JimmyV/custom)|installer/extras/cartographer-offset-setup/install.sh|is_cartographer
cartographer-macros|is_carto_macros|CARTO_* macro buttons for Fluidd (calibrate/load/touch home)|installer/extras/cartographer-macros/install.sh|is_cartographer
axis_twist_compensation|is_axis_twist|Optional Z-drift compensation across X|features/axis_twist_compensation/install.sh|
plate-aware-mesh|is_plate_aware_mesh|Saved meshes selected by build plate and temperature|installer/extras/plate-aware-mesh/install.sh|is_stock_probe
secure-auth|is_secure_auth|Disable SSH password login (requires a tested public key)|features/secure-auth/install.sh|
r3men-bed|is_r3men_bed|R3MEN graphite-bed thermistor profile|features/r3men-bed/install.sh|'

# Keep this conditional so older checkouts without the KAMP extra do not
# advertise an installer that is not present.
if [ -f "$INSTALLER_DIR/installer/extras/kamp-adaptive-purge/install.sh" ]; then
    _EXTRAS="${_EXTRAS}
kamp-adaptive-purge|is_kamp|KAMP adaptive purge|installer/extras/kamp-adaptive-purge/install.sh|"
fi

# Human-readable hint for the requires_function name. Add new entries here
# when new precondition functions are introduced.
_extras_requires_label() {
    case "$1" in
        is_cartographer) echo "needs Cartographer" ;;
        is_stock_probe)  echo "stock PR Touch only" ;;
        *)               echo "blocked: $1" ;;
    esac
}

extra_line() {
    printf '%s\n' "$_EXTRAS" | grep "^$1|" | head -1
}

extra_state() {
    local line det req
    line="$(extra_line "$1")"
    [ -n "$line" ] || { c_yellow 'UNAVAILABLE'; return; }
    det=$(printf '%s' "$line" | cut -d'|' -f2)
    req=$(printf '%s' "$line" | cut -d'|' -f5)

    if "$det" 2>/dev/null; then
        state_installed
    elif [ -n "$req" ] && ! "$req" 2>/dev/null; then
        case "$req" in
            is_cartographer) state_requires 'CARTOGRAPHER' ;;
            is_stock_probe) state_requires 'STOCK PR TOUCH' ;;
            *) state_blocked ;;
        esac
    else
        state_not_installed
    fi
}

run_extra_name() {
    local line
    line="$(extra_line "$1")"
    if [ -z "$line" ]; then
        clear
        ui_heading 'OPTIONAL EXTRA UNAVAILABLE'
        printf '\nThe selected installer is not present in this checkout.\n'
        press_enter
        return 1
    fi
    install_extra "$line"
}

show_secure_auth_setup_guide() {
    local guide="$INSTALLER_DIR/features/secure-auth/SETUP.md"

    if [ ! -f "$guide" ]; then
        warn "Secure Auth setup guide not found: $guide"
        return 1
    fi

    if command -v less >/dev/null 2>&1; then
        less "$guide"
    elif command -v more >/dev/null 2>&1; then
        more "$guide"
    else
        cat "$guide"
    fi
}

carto_plate_workflow_state() {
    if is_carto_plate_workflow; then
        state_installed
    elif is_carto_macros || is_surface_wrap; then
        state_incomplete
    elif ! is_cartographer; then
        state_requires 'CARTOGRAPHER'
    else
        state_not_installed
    fi
}

run_carto_plate_workflow() {
    clear
    ui_heading 'CARTOGRAPHER PLATE PROFILES / AUTO-SELECTION'
    printf '\nThis installs the two tied parts of the plate workflow:\n'
    printf '  - CARTO_* Fluidd buttons for the four Creality Print plate types\n'
    printf '  - START_PRINT surface selection using the slicer plate choice\n\n'

    if ! is_cartographer; then
        printf '%s\n' "$(c_yellow 'Cannot install: Cartographer is required first.')"
        press_enter
        return 1
    fi

    printf '  %-32s %s\n' 'Cartographer Fluidd macros' \
        "$(if is_carto_macros; then state_installed; else state_not_installed; fi)"
    printf '  %-32s %s\n\n' 'Surface-selection wrapper' \
        "$(if is_surface_wrap; then state_installed; else state_not_installed; fi)"

    if ! confirm 'Install the missing plate-workflow components now?'; then
        return 0
    fi

    local pwd_home failed
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="$HOME"
    failed=0

    info 'refreshing Cartographer Fluidd macros'
    HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
        sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh" \
        || failed=1

    if [ "$failed" -eq 0 ]; then
        info 'refreshing surface-selection wrapper'
        HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
            sh "$INSTALLER_DIR/installer/extras/surface-selection-wrapper/install.sh" \
            || failed=1
    fi

    if [ "$failed" -eq 0 ] && is_carto_plate_workflow; then
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            migration_mark_component_current cartographer-plate-workflow
        fi
        printf '\n%s\n' "$(c_green 'Cartographer plate workflow installed successfully.')"
        printf 'When no print is active, run FIRMWARE_RESTART and wait for the complete\n'
        printf 'K2 startup sequence. Power-cycle before homing only if it reports an error.\n'
    else
        printf '\n%s\n' "$(c_yellow 'Plate workflow is incomplete; review the errors above.')"
    fi
    press_enter
}

menu_extras() {
    while :; do
        clear
        ui_heading 'OPTIONAL EXTRAS'
        printf '\n Hardware\n'
        ui_menu_item 1 'R3MEN bed thermistor profile' "$(extra_state r3men-bed)"
        printf '\n Print workflow\n'
        ui_menu_item 2 'KAMP adaptive purge' "$(extra_state kamp-adaptive-purge)"
        ui_menu_item 3 'Axis twist compensation' "$(extra_state axis_twist_compensation)"
        if is_cartographer; then
            ui_menu_item 4 'Cartographer plate workflow' "$(carto_plate_workflow_state)"
            printf '\n Security\n'
            ui_menu_item 5 'Secure Auth' "$(extra_state secure-auth)"
            printf '\n  0. Back\n\nSelect [0-5]: '
        else
            ui_menu_item 4 'Plate-aware saved meshes' "$(extra_state plate-aware-mesh)"
            printf '\n Security\n'
            ui_menu_item 5 'Secure Auth' "$(extra_state secure-auth)"
            printf '\n  0. Back\n\nSelect [0-5]: '
        fi
        read -r c
        case "$c" in
            1) run_extra_name r3men-bed ;;
            2) run_extra_name kamp-adaptive-purge ;;
            3) run_extra_name axis_twist_compensation ;;
            4)
                if is_cartographer; then
                    run_carto_plate_workflow
                else
                    run_extra_name plate-aware-mesh
                fi
                ;;
            5) run_extra_name secure-auth ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

install_extra() {
    local line="$1"
    local name=$(printf '%s' "$line" | cut -d'|' -f1)
    local det=$(printf  '%s' "$line" | cut -d'|' -f2)
    local script_rel=$(printf '%s' "$line" | cut -d'|' -f4)
    local req=$(printf  '%s' "$line" | cut -d'|' -f5)
    local script="$INSTALLER_DIR/$script_rel"
    local readme="$(dirname "$script")/README.md"

    clear
    ui_heading "$name"
    printf '\n'

    # Precondition gate: refuse with a clean message if the extra requires
    # something that's not present (e.g. is_cartographer fails). The
    # install scripts have their own grep checks too - this is just the
    # friendlier UX layer that prevents the user from running the script
    # at all when the precondition is missing.
    if [ -n "$req" ] && ! "$req" 2>/dev/null; then
        printf '%s\n\n' "$(c_yellow "Cannot install: $(_extras_requires_label "$req")")"
        case "$req" in
            is_cartographer)
                printf '  This extra requires Cartographer to be installed first.\n'
                printf '  On a fresh K2 Plus, install Cartographer via:\n\n'
                printf '    - Install or change setup -> Cartographer setup\n'
                printf '    - Maintenance -> Core component installer -> cartographer\n'
                printf '    - Or Jacob10383'"'"'s original gimme-the-jamin.sh\n\n'
                printf '  Once Cartographer is installed and Klipper has restarted with the\n'
                printf '  new config, this extra will become available.\n\n'
                ;;
            is_stock_probe)
                printf '  This extra is for a K2 Plus using the stock PR Touch probe.\n'
                printf '  Cartographer installations create adaptive meshes per print and use\n'
                printf '  the separate Cartographer plate workflow.\n\n'
                ;;
            *)
                printf '  Precondition function "%s" returned false.\n\n' "$req"
                ;;
        esac
        press_enter
        return 1
    fi

    if [ ! -f "$script" ]; then
        warn "install script not found: $script"
        warn "(this extra is not yet implemented in v1)"
        press_enter
        return 1
    fi

    show_feature_readme "$name" "$readme"

    case "$name" in
        cartographer-offset-setup)
            local label=$(detect_carto_offset_label)
            printf '  Currently configured: %s\n\n' "$(c_green "$label")"
            if ! confirm "Open the offset picker?"; then return 0; fi
            ;;
        secure-auth)
            if "$det" 2>/dev/null; then
                printf '  Status: %s\n\n' "$(c_green 'ALREADY APPLIED')"
            fi
            if confirm 'Open the complete setup guide in this terminal now?'; then
                show_secure_auth_setup_guide
                printf '\n'
            fi
            printf '%s\n' "$(c_red 'Secure Auth disables SSH password login and disconnects active SSH sessions.')"
            printf 'Confirm that key-only login works in a second terminal before continuing.\n\n'
            printf 'Type SECURE AUTH to continue: '
            local secure_auth_answer
            read -r secure_auth_answer
            if [ "$secure_auth_answer" != "SECURE AUTH" ]; then
                warn 'confirmation did not match; Secure Auth was not changed.'
                press_enter
                return 0
            fi
            ;;
        *)
            if "$det" 2>/dev/null; then
                printf '  Status: %s\n\n' "$(c_green 'ALREADY APPLIED')"
                if ! confirm "Re-run install.sh anyway?"; then return 0; fi
            else
                if ! confirm "Apply $name now?"; then return 0; fi
            fi
            ;;
    esac

    local pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="$HOME"
    info "running $script (HOME=$pwd_home)"
    if HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" sh "$script"; then
        info "$name install completed"
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            migration_mark_component_current "$name"
        fi
    else
        warn "$name install.sh exited non-zero"
    fi
    press_enter
}
