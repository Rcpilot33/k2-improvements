#!/bin/sh
# Safe, resumable replacement for upstream no-carto.sh.
# Installs the same stock-probe feature set without Cartographer.

_INSTALL_NO_CARTO_ORDER='entware|is_entware|features/entware/install.sh
better-root|is_better_root|installer/extras/better-root-safe/install.sh
better-init|is_better_init|features/better-init/install.sh
skip-setup|is_skip_setup|features/skip-setup/install.sh
moonraker|is_moonraker|features/moonraker/install.sh
fluidd|is_fluidd|features/fluidd/install.sh
screws_tilt_adjust|is_screws_tilt_firmware_restart|features/screws_tilt_adjust/install.sh
abort_homing|is_abort_homing_firmware_restart|features/abort_homing/install.sh
save-config-restart|is_save_config_restart|features/save-config-restart/install.sh
macros|is_macros|features/macros/install.sh'

menu_install_no_carto() {
    clear
    ui_heading 'INSTALL STOCK PROBE / NO-CARTOGRAPHER SETUP'
    printf '\n'
    printf 'Safe, resumable replacement for Jacob10383%s no-carto.sh.\n' "'"
    printf 'Installs the same stock PR Touch feature set while skipping components\n'
    printf 'that are already installed. It does NOT install or remove Cartographer.\n\n'

    if is_cartographer; then
        printf '%s\n\n' "$(c_yellow 'Cartographer is currently installed.')"
        printf 'This installer does not remove Cartographer or restore PR Touch config.\n'
        printf 'Use the appropriate cleanup/conversion procedure before selecting the\n'
        printf 'stock-probe setup on a converted printer.\n\n'
        press_enter
        return 1
    fi

    printf 'Plan:\n'
    local OLDIFS="$IFS"
    IFS='
'
    local n=0
    for line in $_INSTALL_NO_CARTO_ORDER; do
        n=$((n+1))
        local name=$(printf '%s' "$line" | cut -d'|' -f1)
        local det=$(printf '%s' "$line" | cut -d'|' -f2)
        local state
        if "$det" 2>/dev/null; then state=$(state_installed); else state=$(state_pending); fi
        printf '  %2d. %-34s %s\n' "$n" "$name" "$state"
    done
    IFS="$OLDIFS"

    printf '\n%s\n' "$(c_yellow 'WARNING: this can take 5-15 minutes and will modify Klipper.')"
    printf '         Make sure no print is active.\n\n'
    if ! confirm "Proceed with stock probe / no-Cartographer setup?"; then return 0; fi

    local installed=0 skipped=0 failed=0
    OLDIFS="$IFS"
    IFS='
'
    for line in $_INSTALL_NO_CARTO_ORDER; do
        local name=$(printf '%s' "$line" | cut -d'|' -f1)
        local det=$(printf '%s' "$line" | cut -d'|' -f2)
        local script_rel=$(printf '%s' "$line" | cut -d'|' -f3)
        local script="$INSTALLER_DIR/$script_rel"

        printf '\n--- %s ---\n' "$name"
        if "$det" 2>/dev/null; then
            info "already installed - skipping"
            skipped=$((skipped+1))
            continue
        fi
        if [ ! -f "$script" ]; then
            warn "missing $script - skipping"
            failed=$((failed+1))
            continue
        fi

        local pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
        info "running $name (HOME=$pwd_home)"
        if HOME="$pwd_home" sh "$script"; then
            installed=$((installed+1))
        else
            warn "$name install.sh failed (continuing)"
            failed=$((failed+1))
        fi
    done
    IFS="$OLDIFS"

    # Match the Cartographer essentials flow's Entware boot-hook safety net.
    if [ -f "$INSTALLER_DIR/features/entware/unslung.init" ] && \
       [ ! -f /etc/init.d/unslung ]; then
        cp "$INSTALLER_DIR/features/entware/unslung.init" /etc/init.d/unslung
        chmod +x /etc/init.d/unslung
        ln -sf /etc/init.d/unslung /etc/rc.d/S99unslung
        ln -sf /etc/init.d/unslung /etc/rc.d/K01unslung
        info "Entware unslung boot hook installed (S99unslung)"
    fi

    printf '\n%s\n' '----------------------------------------------------------------'
    printf 'Stock-probe summary: %s installed, %s skipped, %s failed\n' \
        "$(c_green "$installed")" "$skipped" "$(c_red "$failed")"
    printf '%s\n\n' '----------------------------------------------------------------'
    printf 'Detected setup: %s\n\n' "$(detect_install_profile)"
    if [ "$failed" -eq 0 ]; then
        printf '%s\n' "$(c_green 'All requested components completed without a restart error.')"
        printf 'Continue with manual calibration.\n\n'
    else
        printf '%s\n' "$(c_red 'One or more components failed or reported a restart error.')"
        printf 'Review the output and power-cycle the printer before running G28.\n\n'
    fi
    press_enter
}
