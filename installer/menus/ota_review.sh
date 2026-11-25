#!/bin/sh
# The OTA baseline is independent of the pre-git-pull migration snapshot.
OTA_SNAPSHOT="$MIGRATION_STATE_DIR/verified-setup"
OTA_OPTIONS='r3men-bed kamp-adaptive-purge cartographer-plate-workflow global-touch-offsets global-prtouch-offsets material-z-offsets plate-aware-mesh nozzle-camera nozzle-usb-cartographer memory-diagnostics secure-auth'

ota_baseline_firmware() { sed -n 's/^firmware=//p' "$OTA_SNAPSHOT" 2>/dev/null; }

ota_settings() {
    local action="$1" setup="$2"
    shift 2
    python3 "$INSTALLER_DIR/installer/migrations/ota_settings.py" "$action" \
        "$PRINTER_CFG_DIR/custom" "$MIGRATION_STATE_DIR/settings-$setup.zip" "$@"
}

ota_save_before_update() {
    local setup fw old options
    fw=$(detect_installed_firmware)
    old=$(ota_baseline_firmware) || old=
    if [ -f "$MIGRATION_STATE_DIR/settings-restart-pending" ]; then
        warn 'Finish the pending settings restore with option 6 -> 1 before saving a new backup.'
        return 1
    fi
    if [ -z "$fw" ] || { [ -n "$old" ] && [ "$fw" != "$old" ]; }; then
        warn 'Review this firmware with option 6 -> 1 before saving a new settings backup.'
        return 1
    fi
    if has_cartographer_configuration; then setup=cartographer; else setup=stock-probe; fi
    if [ -f "$MIGRATION_STATE_DIR/settings-$setup.zip" ]; then
        confirm 'Save the current settings for the next OTA and retain the previous copy?' || return 1
    fi
    options=$(ota_setup_options "$setup") || return 1
    ota_write_snapshot "$fw" "$setup" "$options" captured || return 1
    printf 'Saved %s setup on firmware %s. Optional components:\n%s\n' "$setup" "$fw" "${options:-none}"
}

ota_review_notice() {
    local old current
    old=$(ota_baseline_firmware) || old=
    current=$(detect_installed_firmware)
    if [ -n "$old" ] && [ -n "$current" ] && [ "$old" != "$current" ]; then
        echo "FIRMWARE CHANGED $old -> $current | REVIEW SETUP"
    elif [ -n "$old" ] && [ -z "$current" ]; then
        echo 'INSTALLED FIRMWARE UNKNOWN | REVIEW SETUP'
    elif [ "${bootstrap_needs_review:-0}" = 1 ]; then
        echo 'BOOTSTRAP REPAIR NEEDED'
    elif [ -f "$MIGRATION_STATE_DIR/settings-restart-pending" ]; then
        echo 'SETTINGS RESTORE PENDING'
    elif [ -z "$old" ] && { is_macros || has_cartographer_configuration; }; then
        echo 'SETUP BASELINE NEEDED'
    elif grep -Fxq 'setup=cartographer' "$OTA_SNAPSHOT" 2>/dev/null &&
         ! ota_component_ready cartographer-registration 2>/dev/null; then
        echo 'CARTOGRAPHER REGISTRATION INCOMPLETE | REVIEW SETUP'
    fi
}

ota_bootstrap_check() {
    local failed=0
    bootstrap_entware_ready "$INSTALLER_DIR/bootstrap" || { warn 'Check Entware packages, /opt, SFTP, login profile and boot hooks'; failed=1; }
    bootstrap_home_ready || { warn 'Check persistent root home and printer component links'; failed=1; }
    bootstrap_checkout_ready "$INSTALLER_DIR" || { warn 'Check local installer checkout and menu files'; failed=1; }
    return "$failed"
}

ota_option_ready() {
    case "$1" in
        secure-auth) is_secure_auth ;;
        *) migration_component_installed "$1" ;;
    esac
}

# Successful menu actions can update individual choices, even when the old
# verified firmware must remain pending. Never infer a removal from a scan.
ota_record_option() {
    local option="$1" action="${2:-add}"
    [ -f "$OTA_SNAPSHOT" ] && [ "${OTA_REVIEW_ACTIVE:-0}" != 1 ] || return 0
    case " $OTA_OPTIONS " in *" $option "*) ;; *) return 0 ;; esac
    local tmp="$OTA_SNAPSHOT.new.$$"
    awk -v entry="option=$option" '$0 != entry' "$OTA_SNAPSHOT" > "$tmp" || return 1
    if [ "$action" = add ]; then printf 'option=%s\n' "$option" >> "$tmp" || return 1; fi
    mv "$tmp" "$OTA_SNAPSHOT"
}

ota_component_ready() {
    local name="$1" file
    case "$name" in
        better-init)
            is_better_init || return 1
            for file in klipper klipper_mcu webrtc; do
                [ -x "/etc/init.d/$file" ] || return 1
                # nozzle USB protection deliberately changes the Klipper DEPEND line.
                if [ "$file" = klipper ] && is_nozzle_usb_cartographer; then continue; fi
                cmp -s "$INSTALLER_DIR/features/better-init/$file.init" "/etc/init.d/$file" || return 1
            done
            for file in sudo supervisorctl systemctl; do
                bootstrap_link_ready "/mnt/UDISK/bin/$file" "$INSTALLER_DIR/features/better-init/bin/$file" || return 1
            done ;;
        moonraker-service)
            bootstrap_link_ready /etc/init.d/moonraker "$INSTALLER_DIR/features/moonraker/moonraker.init" &&
            bootstrap_link_ready /opt/etc/init.d/S56moonraker /etc/init.d/moonraker &&
            [ -s "$PRINTER_CFG_DIR/moonraker.conf" ] &&
            [ -x "$HOME/moonraker-env/bin/python" ] && [ -f "$HOME/moonraker/moonraker/moonraker.py" ] ;;
        cartographer)
            cartographer_core_ready || return 1
            for file in mcu.py serialhdl.py clocksync.py extras/bed_mesh.py extras/homing.py extras/temperature_mcu.py extras/k2_safe_move_z.py; do
                cmp -s "$KLIPPER_DIR/klippy/$file" "$INSTALLER_DIR/features/cartographer/patches/${file##*/}" || return 1
            done
            for file in k2_cartographer_scan_guard k2_cartographer_probe_wait; do
                [ -f "$KLIPPER_DIR/klippy/extras/$file.py" ] || return 1
            done
            if grep -Eq '^[[:space:]]*serial:[[:space:]]*/dev/cartographer([[:space:]]|$)' "$PRINTER_CFG_DIR/custom/cartographer.cfg"; then
                [ -x /mnt/UDISK/bin/usb_bridge_new ] &&
                bootstrap_link_ready /etc/init.d/cartographer "$INSTALLER_DIR/features/cartographer/cartographer.init" &&
                bootstrap_link_ready /opt/etc/init.d/S50cartographer /etc/init.d/cartographer || return 1
            fi ;;
        cartographer-registration) is_cartographer_registered ;;
        nozzle-usb-cartographer)
            [ ! -f /tmp/k2-klippy-code-restart-required ] && is_nozzle_usb_cartographer &&
            "${K2_PYTHON:-python3}" -B "$INSTALLER_DIR/installer/extras/nozzle-usb-cartographer/verify_install.py" ;;
        fluidd)
            is_fluidd &&
            grep -Fxq '[include updates/fluidd.cfg]' "$PRINTER_CFG_DIR/moonraker.conf" &&
            python3 "$INSTALLER_DIR/features/fluidd/configure_update_manager.py" --check --config "$PRINTER_CFG_DIR/updates/fluidd.cfg" ;;
        save-config-restart) is_save_config_restart && [ -x "$KLIPPER_DIR/klippy/k2_save_config_restart.sh" ] ;;
        skip-setup) is_skip_setup ;;
        prtouch-cleanup) is_prtouch_clean ;;
        *) ota_option_ready "$name" ;;
    esac
}

ota_scan() {
    local setup="$1" options="$2" name components
    components='better-init skip-setup moonraker-service moonraker-source fluidd screws_tilt_adjust'
    if [ "$setup" = cartographer ]; then components="$components cartographer prtouch-cleanup"; fi
    components="$components abort_homing save-config-restart virtual-sdcard-guard macros"
    if [ "$setup" = cartographer ]; then components="$components cartographer-registration"; fi
    if is_start_print_fast_stop_eligible; then components="$components start-print-fast-stop"; fi
    for name in $components $options; do
        if ! ota_component_ready "$name" >/dev/null 2>&1; then echo "$name"; fi
    done
}

ota_detect_options() {
    local option
    for option in $OTA_OPTIONS; do
        if ota_option_ready "$option" >/dev/null 2>&1 || migration_component_present "$option" >/dev/null 2>&1; then
            echo "$option"
        fi
    done
}

# Use the selected setup even when a firmware upgrade has erased its files.
ota_filter_setup_options() {
    awk -v setup="$1" '
        setup == "cartographer" && ($0 == "global-prtouch-offsets" || $0 == "plate-aware-mesh") { next }
        setup == "stock-probe" && ($0 == "global-touch-offsets" || $0 == "cartographer-plate-workflow") { next }
        NF && !seen[$0]++
    '
}

ota_write_snapshot() {
    local fw="$1" setup="$2" options="$3" state="$4" option tmp="$OTA_SNAPSHOT.new.$$"
    local model='K2 Plus'
    if [ "${K2_PRINTER_MODEL:-}" = F012 ]; then model='K2 Pro'; fi
    [ -n "$fw" ] || { warn 'Installed firmware version is unknown; keeping previous snapshot'; return 1; }
    mkdir -p "$MIGRATION_STATE_DIR" || return 1
    {
        printf 'firmware=%s\nmodel=%s\nsetup=%s\nstate=%s\n' "$fw" "$model" "$setup" "$state"
        for option in $options; do printf 'option=%s\n' "$option"; done
    } > "$tmp" || return 1
    if [ "$state" = captured ] || [ ! -f "$MIGRATION_STATE_DIR/settings-$setup.zip" ]; then
        ota_settings save "$setup" "$tmp" || { rm -f "$tmp"; return 1; }
    fi
    mv "$tmp" "$OTA_SNAPSHOT"
}

ota_verify_setup() {
    local setup="$1" options="$2" fw missing component layouts carto_layout
    fw=$(detect_installed_firmware)
    ota_bootstrap_check || return 1
    missing=$(ota_scan "$setup" "$options")
    if [ -n "$missing" ]; then warn "Still needs review: $missing"; return 1; fi
    python3 "$INSTALLER_DIR/installer/migrations/verify_ota_runtime.py" "$setup" $options || return 1
    layouts=macros
    carto_layout=cartographer
    for component in $options; do
        case "$component" in
            cartographer-plate-workflow) carto_layout=$component ;;
            global-touch-offsets|material-z-offsets) layouts="$layouts $component" ;;
        esac
    done
    if [ "$setup" = cartographer ]; then layouts="$layouts $carto_layout"; fi
    for component in $layouts; do
        if ! python3 "$INSTALLER_DIR/installer/migrations/verify_fluidd_layout.py" "$component"; then
            [ "${OTA_REVIEW_ACTIVE:-0}" = 1 ] && confirm "Restore the Fluidd macro grouping for $component?" &&
                migration_reconcile_fluidd_layout "$component" || return 1
        fi
    done
    ota_write_snapshot "$fw" "$setup" "$options" verified
}

ota_setup_options() {
    {
        ota_detect_options
        if [ -f "$OTA_SNAPSHOT" ]; then
            # A firmware upgrade can erase all traces of an installed option.
            sed -n 's/^option=//p' "$OTA_SNAPSHOT"
        fi
    } | ota_filter_setup_options "$1"
}

ota_setup_installed() {
    local setup="$1" options
    options=$(ota_setup_options "$setup") || return 1
    ota_verify_setup "$setup" "$options"
}

ota_repair_bootstrap() {
    local base="$INSTALLER_DIR/bootstrap"
    if ! bootstrap_entware_ready "$base"; then
        sh "$base/entware/install.sh" && bootstrap_entware_ready "$base" || return 1
    fi
    if ! bootstrap_home_ready; then
        K2_SKIP_BETTER_ROOT_LOGOUT=1 sh "$base/better-root/install.sh" && bootstrap_home_ready || return 1
    fi
    export HOME=/mnt/UDISK/root
    ensure_path
    bootstrap_checkout_ready "$INSTALLER_DIR" || {
        warn 'Rerun the branch-specific bootstrap to recover the installer checkout.'
        return 1
    }
}

ota_bootstrap_preflight() {
    bootstrap_needs_review=0
    ota_bootstrap_check && return 0
    bootstrap_needs_review=1
    if confirm 'Repair the listed bootstrap prerequisites before opening the menu?' &&
       migration_require_idle && run_logged_install bootstrap-repair ota_repair_bootstrap && ota_bootstrap_check; then
        bootstrap_needs_review=0
        export HOME=/mnt/UDISK/root
        ensure_path
    fi
}

ota_review() (
    local setup options available fw name missing manual extra tmp choice requirement repair_nozzle_usb=0
    OTA_REVIEW_ACTIVE=1
    fw=$(detect_installed_firmware)
    printf 'Reviewing local setup. Installed firmware: %s, saved baseline: %s\n' \
        "${fw:-unknown}" "$(ota_baseline_firmware || echo 'none')"
    if ! ota_bootstrap_check; then
        confirm 'Repair bootstrap prerequisites first?' && migration_require_idle && ota_repair_bootstrap || return 1
    fi
    if [ -f "$OTA_SNAPSHOT" ]; then
        setup=$(sed -n 's/^setup=//p' "$OTA_SNAPSHOT")
        case "$setup" in cartographer|stock-probe) ;; *) warn 'Invalid setup in saved snapshot'; return 1 ;; esac
        options=$(sed -n 's/^option=//p' "$OTA_SNAPSHOT" | ota_filter_setup_options "$setup")
    else
        if has_cartographer_configuration; then setup=cartographer; else setup=stock-probe; fi
        printf 'No saved setup snapshot. Detected %s. Select the previously installed setup:\n' "$setup"
        printf '  1. Stock probe\n  2. Cartographer\n  0. Back\n'
        read_prompt choice
        case "$choice" in 1) setup=stock-probe ;; 2) setup=cartographer ;; *) return 0 ;; esac
        options=$(ota_setup_options "$setup")
        available=$(printf '%s\n' $OTA_OPTIONS | ota_filter_setup_options "$setup" | tr '\n' ' ')
        printf 'Detected options:\n%s\nAvailable option names:\n%s\n' "${options:-none}" "$available"
        printf 'Enter any additional previously installed option names (Enter to continue): '
        read_prompt extra
        for name in $extra; do
            case " $available " in *" $name "*) ;; *) warn "Option unavailable for $setup: $name"; return 1 ;; esac
        done
        options=$(printf '%s\n' $options $extra | awk 'NF && !seen[$0]++')
    fi
    if [ "$setup" = stock-probe ] && has_cartographer_configuration; then
        warn 'Stock-probe selection conflicts with the Cartographer configuration. Review the saved setup.'
        return 1
    fi
    printf 'Expected %s setup. Optional components:\n%s\n' "$setup" "${options:-none}"
    if [ -f "$MIGRATION_STATE_DIR/settings-$setup.zip" ]; then
        ota_settings check "$setup"
        case "$?" in
            0) info 'Saved settings match the current files.' ;;
            3) migration_require_idle && ota_settings restore "$setup" || return 1 ;;
            *) return 1 ;;
        esac
    fi
    missing=$(ota_scan "$setup" "$options")
    if [ "$setup" = cartographer ] && ! has_cartographer_configuration; then
        warn "Restore the saved Cartographer configuration from backup before repairing these components: $missing"
        return 1
    fi
    if [ -n "$missing" ]; then
        printf 'Missing or incomplete components:\n%s\n' "$missing"
        tmp=$(mktemp) || return 1
        trap 'rm -f "$tmp"' EXIT
        manual=0
        for name in $missing; do
            requirement=$(extra_line "$name" | cut -d'|' -f5)
            if [ -n "$requirement" ] && ! "$requirement"; then
                case "$requirement" in
                    is_macros) grep -Fxq macros "$tmp" && requirement= ;;
                    is_cartographer) grep -Fxq cartographer "$tmp" && requirement= ;;
                esac
                if [ -n "$requirement" ]; then
                    warn "$name requires $requirement. Review the prerequisite in Optional extras."
                    manual=1
                    continue
                fi
            fi
            case "$name" in
                nozzle-usb-cartographer)
                    info 'This review will ask how the Cartographer probe is wired before restoring nozzle-camera protection.'
                    repair_nozzle_usb=1 ;;
                secure-auth|nozzle-camera)
                    warn "Review $name in Optional extras to confirm the current hardware or SSH settings."
                    manual=1 ;;
                *) printf '%s\n' "$name" >> "$tmp" ;;
            esac
        done
        if [ -s "$tmp" ]; then
            # Stock replacement modules are version-specific. Unknown firmware
            # can still be audited locally without applying those replacements.
            case "$fw" in 1.1.3.13|1.1.5.2|1.1.5.5|1.1.8.0) ;;
                *) if grep -Eq '^(cartographer|save-config-restart|better-init|screws_tilt_adjust|abort_homing|virtual-sdcard-guard|macros|start-print-fast-stop)$' "$tmp"; then
                       warn "The plan replaces firmware files. Check compatibility with ${fw:-unknown} before applying it."
                       return 1
                   fi ;;
            esac
            confirm 'Repair the listed automatic components and perform their required restart?' || return 1
            K2_OTA_ACTIVITY_CONFIRM=1 migration_apply_components "$tmp" || return 1
        fi
        if [ "$repair_nozzle_usb" = 1 ] && ! ota_component_ready nozzle-usb-cartographer; then
            # The hardware installer checks live print status. Recover Moonraker
            # and Klipper first when they were part of the automatic repairs.
            K2_DEFER_FIRMWARE_RESTART=0 sh "$INSTALLER_DIR/installer/extras/nozzle-usb-cartographer/install.sh" --ota-repair || {
                warn 'Nozzle-camera protection is still pending. Retry from this review.'
                return 1
            }
            ota_component_ready nozzle-usb-cartographer && migration_mark_component_current nozzle-usb-cartographer || {
                warn 'Could not verify or record nozzle-camera protection. Retry from this review.'
                return 1
            }
            # The hardware installer completed a protected code restart.
            rm -f "$MIGRATION_STATE_DIR/settings-restart-pending" || return 1
        fi
        [ "$manual" -eq 0 ] || return 1
    fi
    if [ -f "$MIGRATION_STATE_DIR/settings-restart-pending" ]; then
        info 'Activating restored settings with a protected restart.'
        migration_require_idle && K2_DEFER_FIRMWARE_RESTART=0 sh "$INSTALLER_DIR/scripts/firmware_restart.sh" || return 1
        rm -f "$MIGRATION_STATE_DIR/settings-restart-pending" || return 1
    fi
    ota_verify_setup "$setup" "$options" || return 1
    info "Verified $setup on firmware $fw. Saved the installed options."
)
