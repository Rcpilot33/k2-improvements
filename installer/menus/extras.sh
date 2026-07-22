#!/bin/sh
# K2-Plus extras (patches not in upstream k2-improvements). Install only.

# name|detector|description|script_path|requires  (one per line; script_path
# relative to INSTALLER_DIR; requires is the name of a function that must
# return 0 for the extra to be installable — empty if no precondition).
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

menu_extras() {
    while :; do
        clear
        printf '\n=== K2-Plus extras ===\n\n'
        local n=0
        local OLDIFS="$IFS"
        IFS='
'
        for line in $_EXTRAS; do
            n=$((n+1))
            local name=$(printf '%s' "$line" | cut -d'|' -f1)
            local det=$(printf  '%s' "$line" | cut -d'|' -f2)
            local desc=$(printf '%s' "$line" | cut -d'|' -f3)
            local req=$(printf  '%s' "$line" | cut -d'|' -f5)
            local mark hint=""
            if "$det" 2>/dev/null; then
                mark=$(c_green '[X]')
            elif [ -n "$req" ] && ! "$req" 2>/dev/null; then
                mark=$(c_yellow '[!]')
                hint=" $(c_yellow "($(_extras_requires_label "$req"))")"
            else
                mark=$(c_dim '[ ]')
            fi
            printf '  %2d. %s %-30s %s%s\n' "$n" "$mark" "$name" "$(c_dim "$desc")" "$hint"
        done
        IFS="$OLDIFS"
        printf '\n   b. Back\n\n'
        printf 'Choose: '
        read -r c
        case "$c" in
            b|B|q|Q) return ;;
            ''|*[!0-9]*) ;;
            *)
                local picked=$(printf '%s' "$_EXTRAS" | sed -n "${c}p")
                [ -n "$picked" ] && install_extra "$picked"
                ;;
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
    printf '\n=== %s ===\n\n' "$name"

    # Precondition gate: refuse with a clean message if the extra requires
    # something that's not present (e.g. is_cartographer fails). The
    # install scripts have their own grep checks too — this is just the
    # friendlier UX layer that prevents the user from running the script
    # at all when the precondition is missing.
    if [ -n "$req" ] && ! "$req" 2>/dev/null; then
        printf '%s\n\n' "$(c_yellow "Cannot install: $(_extras_requires_label "$req")")"
        case "$req" in
            is_cartographer)
                printf '  This extra requires Cartographer to be installed first.\n'
                printf '  On a fresh K2 Plus, install Cartographer via:\n\n'
                printf '    - Menu item 3 (Install Cartographer setup)  — recommended path\n'
                printf '    - Menu item 4 (Features) -> cartographer\n'
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
