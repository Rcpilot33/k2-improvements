#!/bin/sh
# K2-Plus extras (patches not in upstream k2-improvements). Install only.

# name|detector|description|script_path|requires  (one per line; script_path
# relative to INSTALLER_DIR; requires is the name of a function that must
# return 0 for the extra to be installable - empty if no precondition).
_EXTRAS='prtouch-cleanup|is_prtouch_clean|Remove orphan [prtouch_v3] SAVE_CONFIG header|installer/extras/prtouch-cleanup/install.sh|
surface-selection-wrapper|is_surface_wrap|START_PRINT SURFACE= param loads matching scan/touch model|installer/extras/surface-selection-wrapper/install.sh|is_cartographer
cartographer-offset-setup|is_carto_offset_set|Cartographer probe X/Y offset (Jamin/JimmyV/custom)|installer/extras/cartographer-offset-setup/install.sh|is_cartographer
cartographer-macros|is_carto_macros|CARTO_* macro buttons for Fluidd (calibrate/load/touch home)|installer/extras/cartographer-macros/install.sh|is_cartographer
axis_twist_compensation|is_axis_twist|Optional Z-drift compensation across X|features/axis_twist_compensation/install.sh|
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
    printf '  - CARTO_* Fluidd buttons for default, PEI, and Coolplate\n'
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

    if is_carto_plate_workflow; then
        printf '%s\n' "$(c_green 'Plate profiles and automatic selection are already installed.')"
        press_enter
        return 0
    fi

    if ! confirm 'Install the missing plate-workflow components now?'; then
        return 0
    fi

    local pwd_home failed
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="$HOME"
    failed=0

    if ! is_carto_macros; then
        info 'installing Cartographer Fluidd macros'
        HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
            sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh" \
            || failed=1
    fi

    if [ "$failed" -eq 0 ] && ! is_surface_wrap; then
        info 'installing surface-selection wrapper'
        HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
            sh "$INSTALLER_DIR/installer/extras/surface-selection-wrapper/install.sh" \
            || failed=1
    fi

    if [ "$failed" -eq 0 ] && is_carto_plate_workflow; then
        printf '\n%s\n' "$(c_green 'Cartographer plate workflow installed successfully.')"
        printf 'Power-cycle the printer before homing.\n'
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
        ui_menu_item 4 'Cartographer plate profiles / auto-selection' "$(carto_plate_workflow_state)"
        printf '\n Security\n'
        ui_menu_item 5 'Secure Auth' "$(extra_state secure-auth)"

        printf '\n  0. Back\n\nSelect [0-5]: '
        read -r c
        case "$c" in
            1) run_extra_name r3men-bed ;;
            2) run_extra_name kamp-adaptive-purge ;;
            3) run_extra_name axis_twist_compensation ;;
            4) run_carto_plate_workflow ;;
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
    else
        warn "$name install.sh exited non-zero"
    fi
    press_enter
}
