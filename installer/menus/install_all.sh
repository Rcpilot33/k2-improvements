#!/bin/sh
# "Install all (recommended)" flow - installs every missing feature + extra
# + KAMP, in dependency order. Cartographer firmware flash is intentionally
# excluded because it requires explicit physical interaction.

# Essentials only - what's needed to have a working K2 Plus + Cartographer.
# QoL features (KAMP, surface-wrapper, axis_twist), security
# features (secure-auth - can lock you out if installed without keys), and
# hardware-specific features such as r3men-bed are excluded here.
# They stay available individually from Maintenance and Optional extras.
# Obico is not exposed in the installer menus in this fork because the inherited
# external installer did not complete cleanly.
# The legacy files remain under features/obico for manual testing.
# Order matches upstream gimme-the-jamin.sh: moonraker installs BEFORE
# cartographer/fluidd/macros so those features can register their
# update_manager entries with moonraker. prtouch-cleanup runs after
# cartographer (the orphan SAVE_CONFIG block only appears once cartographer's
# alter_config.py has run).
_INSTALL_ALL_ORDER='entware|is_entware|features/entware/install.sh
better-root|is_better_root|installer/extras/better-root-safe/install.sh
better-init|is_better_init|features/better-init/install.sh
skip-setup|is_skip_setup|features/skip-setup/install.sh
moonraker|is_moonraker|features/moonraker/install.sh
fluidd|is_fluidd|features/fluidd/install.sh
screws_tilt_adjust|is_screws_tilt_firmware_restart|features/screws_tilt_adjust/install.sh
cartographer|is_cartographer|features/cartographer/install.sh
abort_homing|is_abort_homing_firmware_restart|features/abort_homing/install.sh
save-config-restart|is_save_config_restart|features/save-config-restart/install.sh
prtouch-cleanup|is_prtouch_clean|installer/extras/prtouch-cleanup/install.sh
macros|is_macros|features/macros/install.sh'

menu_install_all() {
    clear
    ui_heading 'INSTALL CARTOGRAPHER SETUP'
    printf '\n'
    printf 'The minimum needed to run a K2 Plus + Cartographer probe. Skips anything\n'
    printf 'already installed. After the auto steps, prompts you to pick your\n'
    printf 'Cartographer mount preset (mandatory - probe offsets depend on hardware).\n\n'
    printf 'NOT in this flow (need physical interaction or are optional):\n'
    printf '  - Cartographer firmware flash (USB/Katapult or physical DFU mode)\n'
    printf '  - Hardware-specific features (e.g., r3men-bed)\n'
    printf '  - QoL features (KAMP, surface-wrapper, axis_twist, etc.) - Optional extras\n\n'
    printf 'Plan:\n'
    local OLDIFS="$IFS"
    IFS='
'
    local n=0
    for line in $_INSTALL_ALL_ORDER; do
        n=$((n+1))
        local name=$(printf '%s' "$line" | cut -d'|' -f1)
        local det=$(printf  '%s' "$line" | cut -d'|' -f2)
        local state
        if "$det" 2>/dev/null; then state=$(state_installed); else state=$(state_pending); fi
        printf '  %2d. %-34s %s\n' "$n" "$name" "$state"
    done
    IFS="$OLDIFS"
    printf '\n'
    printf '%s\n' "$(c_yellow 'WARNING: this can take 5-15 minutes and will modify Klipper.')"
    printf '         Make sure no print is active.\n\n'

    if ! confirm "Proceed with Cartographer setup installation?"; then return 0; fi

    local installed=0 skipped=0 failed=0
    OLDIFS="$IFS"
    IFS='
'
    for line in $_INSTALL_ALL_ORDER; do
        local name=$(printf '%s' "$line" | cut -d'|' -f1)
        local det=$(printf  '%s' "$line" | cut -d'|' -f2)
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
        # Force HOME into the install script's env from current /etc/passwd.
        # better-root mid-flow updates /etc/passwd, but the running menu
        # shell's HOME is cached from SSH login (won't reflect the change),
        # and child shells inherit that stale value. Setting HOME=... on
        # the sh call overrides it for that one invocation.
        pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
        info "running $name (HOME=$pwd_home)"

        if HOME="$pwd_home" sh "$script"; then
            installed=$((installed+1))
        else
            warn "$name install.sh failed (continuing)"
            failed=$((failed+1))
        fi
    done
    IFS="$OLDIFS"

    # Post-install: ensure the Entware unslung boot hook is in place.
    # Bootstrap.sh installs it during Entware setup, but if the user ran
    # the menu without re-running bootstrap (e.g. installer was already
    # cloned from a previous attempt), the hook may be missing. Idempotent
    # safety net here.
    if [ -f "$INSTALLER_DIR/features/entware/unslung.init" ] && \
       [ ! -f /etc/init.d/unslung ]; then
        cp "$INSTALLER_DIR/features/entware/unslung.init" /etc/init.d/unslung
        chmod +x /etc/init.d/unslung
        ln -sf /etc/init.d/unslung /etc/rc.d/S99unslung
        ln -sf /etc/init.d/unslung /etc/rc.d/K01unslung
        info "Entware unslung boot hook installed (S99unslung)"
    fi

    printf '\n%s\n' '----------------------------------------------------------------'
    printf 'Auto-install summary: %s installed, %s skipped, %s failed\n' \
        "$(c_green "$installed")" "$skipped" "$(c_red "$failed")"
    printf '%s\n\n' '----------------------------------------------------------------'

    # Mandatory final step: pick the Cartographer mount preset. The offset
    # values are hardware-specific so we can't auto-pick - but the user must
    # set them or Z-probing will be wrong across the bed.
    if is_cartographer; then
        printf '%s\n' "$(c_yellow 'MANDATORY: select your Cartographer mount preset')"
        printf 'Probe x_offset and y_offset depend on which physical mount you have.\n'
        printf 'Without picking the right preset, Z heights are wrong across the bed.\n\n'
        if confirm "Open the Cartographer offset picker now?"; then
            HOME=$(awk -F: '$1=="root"{print $6}' /etc/passwd) \
                sh "$INSTALLER_DIR/installer/extras/cartographer-offset-setup/install.sh" || true
        else
            printf '\n%s\n\n' "$(c_yellow 'Skipped - run it later from Cartographer tools.')"
        fi
    fi

    printf '\nFinal manual steps:\n'
    printf '  1. Power-cycle the printer from the mains (the cartographer install\n'
    printf '     restarted Klipper, which under K2 Plus motor-state caveat means\n'
    printf '     your next G28 must come AFTER a real boot).\n'
    printf '  2. Optional QoL: surface-selection-wrapper and axis_twist_compensation\n'
    printf '     are available from Optional extras.\n'
    printf '  3. Optional: firmware flashing is available from Cartographer tools.\n'
    printf '  4. Before printing, open Cartographer tools and run the Calibration\n'
    printf '     and setup checklist. Follow the steps shown for your installed\n'
    printf '     plate workflow, then test homing and probing.\n\n'
    press_enter
}
