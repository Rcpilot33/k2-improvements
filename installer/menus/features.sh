#!/bin/sh
# k2-improvements feature install sub-menu. Install only - uninstall is v2.

# name|detector|description (one per line)
_FEATURES='entware|is_entware|Package tools (git/curl/dialog)
better-root|is_better_root|Persistent root home on UDISK
better-init|is_better_init|Profile and PATH loader
skip-setup|is_skip_setup|Skip first-run wizard
moonraker|is_moonraker|Mainline Klipper API server
fluidd|is_fluidd|Updated printer web UI
screws_tilt_adjust|is_screws_tilt|Manual bed-screw assist
cartographer|is_cartographer|Probe and Klipper patches
abort_homing|is_abort_homing|Abort homing on M112/cancel
save-config-restart|is_save_config_restart|Safe firmware reset after SAVE_CONFIG
macros|is_macros|START_PRINT / M191 / bed mesh'

menu_features() {
    while :; do
        clear
        printf '%s\n' '================================================================================================'
        printf ' %s\n' "$(c_cyan 'CORE COMPONENT INSTALLER')"
        printf '%s\n' '================================================================================================'
        printf '\n%s\n\n' "$(c_yellow 'Advanced: install or repair individual components.')"
        local n=0
        local OLDIFS="$IFS"
        IFS='
'
        for line in $_FEATURES; do
            n=$((n+1))
            local name=$(printf '%s' "$line" | cut -d'|' -f1)
            local det=$(printf '%s'  "$line" | cut -d'|' -f2)
            local desc=$(printf '%s' "$line" | cut -d'|' -f3)
            local state
            if "$det"; then state=$(state_installed); else state=$(state_not_installed); fi
            printf '  %2d. %-24s %-42s %s\n' "$n" "$name" "$desc" "$state"
        done
        IFS="$OLDIFS"
        printf '\n   0. Back\n\nSelect [0-%s]: ' "$n"
        read -r c
        case "$c" in
            0|b|B|q|Q) return ;;
            ''|*[!0-9]*) ;;
            *)
                local picked=$(printf '%s' "$_FEATURES" | sed -n "${c}p" | cut -d'|' -f1)
                [ -n "$picked" ] && install_feature "$picked"
                ;;
        esac
    done
}

# Run a feature's install.sh from the upstream k2-improvements layout
install_feature() {
    local name="$1"
    local script="$INSTALLER_DIR/features/$name/install.sh"
    local readme="$INSTALLER_DIR/features/$name/README.md"

    clear
    ui_heading "$name"
    printf '\n'

    if [ ! -f "$script" ]; then
        warn "feature script not found: $script"
        warn "(installer must live at $INSTALLER_DIR - check your bootstrap)"
        press_enter
        return 1
    fi

    show_feature_readme "$name" "$readme"

    local det=$(printf '%s' "$_FEATURES" | grep "^$name|" | cut -d'|' -f2)
    if [ -n "$det" ] && "$det"; then
        printf '  Status: %s\n\n' "$(c_green 'ALREADY INSTALLED')"
        if ! confirm "Re-run install.sh anyway?"; then return 0; fi
    else
        if ! confirm "Install $name now?"; then return 0; fi
    fi

    # Force HOME from /etc/passwd - better-root may have changed root's
    # home mid-session, but the menu shell's HOME is cached from login.
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    info "running $name (HOME=$pwd_home)"
    if HOME="$pwd_home" sh "$script"; then
        info "$name install completed"
    else
        warn "$name install.sh exited non-zero"
    fi
    press_enter
}

# Print a feature's README inline. User scrolls back in their terminal if needed.
show_feature_readme() {
    local name="$1"
    local readme="$2"
    local menu_summary="$(dirname "$readme")/MENU.txt"
    local display_file="$readme"
    local readme_relative=""
    local readme_url=""

    if [ ! -f "$readme" ]; then
        local desc=$(printf '%s' "$_FEATURES" | grep "^$name|" | cut -d'|' -f3)
        printf '(no README.md ships with this feature)\n'
        [ -n "$desc" ] && printf 'Short description: %s\n' "$desc"
        printf '\n'
        return
    fi

    if [ -f "$menu_summary" ]; then
        display_file="$menu_summary"
    fi

    printf '%s\n' '----------------------------------------------------------------'
    if [ "$display_file" = "$menu_summary" ]; then
        printf 'SUMMARY: %s\n' "$name"
    else
        printf 'README: %s\n' "$name"
    fi
    printf '%s\n\n' '----------------------------------------------------------------'
    # The menu is a plain terminal, not a Markdown renderer. Retain the text
    # while removing Markdown syntax that is distracting in terminal output.
    awk '
        /^[[:space:]]*```/ { next }
        {
            sub(/\r$/, "")
            sub(/^#[#]*[[:space:]]+/, "")
            gsub(/`/, "")
            gsub(/\*\*/, "")
            print
        }
    ' "$display_file"
    if [ "$display_file" = "$menu_summary" ]; then
        case "$readme" in
            "$INSTALLER_DIR"/*)
                readme_relative=${readme#"$INSTALLER_DIR"/}
                readme_url="https://github.com/Rcpilot33/k2-improvements/blob/main/$readme_relative"
                printf '\nFull guide online (Ctrl+click or copy):\n%s\n' "$readme_url"
                ;;
        esac
        printf '\nRead directly in the printer SSH terminal:\nless %s\n' "$readme"
    fi
    printf '\n%s\n\n' '----------------------------------------------------------------'
}
