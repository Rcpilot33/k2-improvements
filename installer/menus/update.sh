#!/bin/sh
# Installer update tracking, migration planning, and direct repair actions.

MIGRATION_STATE_DIR="${MIGRATION_STATE_DIR:-/mnt/UDISK/root/.k2-improvements/installer-state/updater}"
MIGRATION_COMPLETED="$MIGRATION_STATE_DIR/completed-migrations"
MIGRATION_INITIALIZED="$MIGRATION_STATE_DIR/initialized"
MIGRATION_LAST_PULL="$MIGRATION_STATE_DIR/last-pull"
MIGRATION_INSTALLED_SNAPSHOT="$MIGRATION_STATE_DIR/installed-before-update"

migration_component_label() {
    case "$1" in
        cartographer) echo 'Cartographer' ;;
        macros) echo 'Macros (START_PRINT / M191 / bed mesh)' ;;
        save-config-restart) echo 'SAVE_CONFIG restart protection' ;;
        abort_homing) echo 'Abort Homing' ;;
        screws_tilt_adjust) echo 'Screws Tilt Adjust' ;;
        kamp-adaptive-purge) echo 'KAMP adaptive purge' ;;
        r3men-bed) echo 'R3MEN bed thermistor profile' ;;
        axis_twist_compensation) echo 'Axis Twist Compensation' ;;
        cartographer-plate-workflow) echo 'Cartographer plate workflow' ;;
        plate-aware-mesh) echo 'Plate-aware saved meshes' ;;
        *) echo "$1" ;;
    esac
}

migration_component_installed() {
    case "$1" in
        cartographer) is_cartographer ;;
        macros) is_macros ;;
        save-config-restart) is_save_config_restart ;;
        abort_homing) is_abort_homing ;;
        screws_tilt_adjust) is_screws_tilt ;;
        kamp-adaptive-purge) is_kamp ;;
        r3men-bed) is_r3men_bed ;;
        axis_twist_compensation) is_axis_twist ;;
        cartographer-plate-workflow) is_carto_plate_workflow ;;
        plate-aware-mesh) is_plate_aware_mesh ;;
        *) return 1 ;;
    esac
}

migration_component_applicable() {
    migration_component_installed "$1" 2>/dev/null && return 0
    migration_component_present "$1" 2>/dev/null && return 0
    [ -f "$MIGRATION_INSTALLED_SNAPSHOT" ] &&
        grep -qxF "$1" "$MIGRATION_INSTALLED_SNAPSHOT" 2>/dev/null
}

# Presence is intentionally less strict than the normal status detectors. An
# older or partially installed component must be offered for repair rather
# than disappearing from the update plan because a new detector expects files
# that only the repair will install.
migration_component_present() {
    local custom configfile
    custom="$PRINTER_CFG_DIR/custom"
    case "$1" in
        cartographer)
            [ -f "$custom/cartographer.cfg" ] ||
                grep -q '^\[cartographer\]' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null
            ;;
        macros)
            [ -e "$custom/start_print.cfg" ] || [ -e "$custom/m191.cfg" ]
            ;;
        save-config-restart)
            configfile="${HOME:-/mnt/UDISK/root}/klipper/klippy/configfile.py"
            [ -L "$configfile" ] &&
                readlink "$configfile" 2>/dev/null | grep -q 'save-config-restart'
            ;;
        abort_homing)
            grep -Eq 'force_stop_homing|can_force_stop_homing' \
                "${KLIPPER_DIR:-/usr/share/klipper}/klippy/webhooks.py" 2>/dev/null
            ;;
        screws_tilt_adjust)
            [ -e "$custom/screws_tilt_adjust.cfg" ]
            ;;
        kamp-adaptive-purge)
            [ -f "$custom/Line_Purge.cfg" ] || [ -f "$custom/kamp_settings.cfg" ]
            ;;
        r3men-bed)
            grep -q 'R3men_bed' "$PRINTER_CFG_DIR/printer.cfg" 2>/dev/null
            ;;
        axis_twist_compensation)
            [ -e "$custom/axis_twist_compensation.cfg" ]
            ;;
        cartographer-plate-workflow)
            [ -e "$custom/cartographer_macros.cfg" ] ||
                grep -q 'surface-selection wrapper' "$custom/start_print.cfg" 2>/dev/null
            ;;
        plate-aware-mesh)
            [ -e "$custom/plate_aware_mesh.cfg" ]
            ;;
        *) return 1 ;;
    esac
}

migration_capture_installed_components() {
    local temporary component
    mkdir -p "$MIGRATION_STATE_DIR"
    temporary="$MIGRATION_STATE_DIR/.installed.$$"
    : > "$temporary"
    for component in cartographer save-config-restart abort_homing \
        screws_tilt_adjust macros r3men-bed kamp-adaptive-purge \
        axis_twist_compensation cartographer-plate-workflow plate-aware-mesh; do
        if migration_component_installed "$component" 2>/dev/null ||
           migration_component_present "$component" 2>/dev/null; then
            printf '%s\n' "$component" >> "$temporary"
        fi
    done
    migration_write_atomic "$MIGRATION_INSTALLED_SNAPSHOT" "$temporary"
}

migration_is_complete() {
    [ -f "$MIGRATION_COMPLETED" ] && grep -qxF "$1" "$MIGRATION_COMPLETED" 2>/dev/null
}

migration_pending_entries() {
    local id component detector reason
    migration_catalog | while IFS='|' read -r id component detector reason; do
        [ -n "$id" ] || continue
        migration_component_applicable "$component" || continue
        migration_is_complete "$id" && continue
        printf '%s|%s|%s\n' "$id" "$component" "$reason"
    done
}

migration_pending_components() {
    local entries component
    entries=$(migration_pending_entries)
    for component in cartographer save-config-restart abort_homing \
        screws_tilt_adjust macros r3men-bed kamp-adaptive-purge \
        axis_twist_compensation cartographer-plate-workflow plate-aware-mesh; do
        if printf '%s\n' "$entries" | grep -q "^[^|]*|$component|"; then
            printf '%s\n' "$component"
        fi
    done
}

migration_has_pending() {
    [ -n "$(migration_pending_components)" ]
}

migration_pending_component_count() {
    migration_pending_components | awk 'NF { count++ } END { print count + 0 }'
}

migration_write_atomic() {
    local target source
    target="$1"
    source="$2"
    mkdir -p "$MIGRATION_STATE_DIR"
    mv -f "$source" "$target"
}

migration_mark_component_current() {
    local component temporary
    component="$1"
    if ! migration_component_installed "$component" 2>/dev/null; then
        warn "$(migration_component_label "$component") still appears incomplete; leaving its update pending"
        return 1
    fi
    mkdir -p "$MIGRATION_STATE_DIR"
    temporary="$MIGRATION_STATE_DIR/.completed.$$"
    {
        [ -f "$MIGRATION_COMPLETED" ] && cat "$MIGRATION_COMPLETED"
        migration_catalog | awk -F'|' -v component="$component" '$2 == component { print $1 }'
    } | awk 'NF && !seen[$0]++' > "$temporary"
    migration_write_atomic "$MIGRATION_COMPLETED" "$temporary"
}

migration_print_details() {
    local component
    clear
    ui_heading 'WHY THESE UPDATES ARE RECOMMENDED'
    printf '\n'
    migration_pending_components | while IFS= read -r component; do
        [ -n "$component" ] || continue
        printf '%s\n' "$(migration_component_label "$component")"
        migration_pending_entries | awk -F'|' -v component="$component" \
            '$2 == component { printf "  - %s\n", $3 }'
        printf '\n'
    done
    press_enter
}

migration_print_state_summary() {
    local old new branch
    if [ -f "$MIGRATION_LAST_PULL" ]; then
        IFS='|' read -r old new branch < "$MIGRATION_LAST_PULL"
        printf ' Last update: %s -> %s\n' "${old:-unknown}" "${new:-unknown}"
        printf ' Branch     : %s\n\n' "${branch:-unknown}"
    fi
}

printer_activity_state() {
    local api query
    api="${MOONRAKER_URL:-http://127.0.0.1:7125}"
    if [ -x /opt/bin/curl ]; then
        query=$(/opt/bin/curl -fsS --max-time 3 \
            "$api/printer/objects/query?print_stats=state" 2>/dev/null || true)
    elif command -v curl >/dev/null 2>&1; then
        query=$(curl -fsS --max-time 3 \
            "$api/printer/objects/query?print_stats=state" 2>/dev/null || true)
    else
        echo unknown
        return
    fi
    case "$query" in
        *'"state": "printing"'*|*'"state":"printing"'*) echo printing ;;
        *'"state": "paused"'*|*'"state":"paused"'*) echo paused ;;
        *'"state":'*) echo idle ;;
        *) echo unknown ;;
    esac
}

migration_require_idle() {
    local state
    state=$(printer_activity_state)
    case "$state" in
        printing|paused)
            warn "cannot update or repair components while the printer is $state"
            press_enter
            return 1
            ;;
        unknown)
            warn 'could not confirm printer activity through Moonraker.'
            if ! confirm 'Continue only if the printer is idle?'; then return 1; fi
            ;;
    esac
    return 0
}

migration_repair_component() {
    local component pwd_home
    component="$1"
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="$HOME"

    case "$component" in
        cartographer)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/cartographer/install.sh"
            ;;
        macros)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/macros/install.sh"
            ;;
        save-config-restart)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/save-config-restart/install.sh"
            ;;
        abort_homing)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/abort_homing/install.sh"
            ;;
        screws_tilt_adjust)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/screws_tilt_adjust/install.sh"
            ;;
        kamp-adaptive-purge)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/installer/extras/kamp-adaptive-purge/install.sh"
            ;;
        r3men-bed)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/r3men-bed/install.sh"
            ;;
        axis_twist_compensation)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/features/axis_twist_compensation/install.sh"
            ;;
        cartographer-plate-workflow)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh" &&
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/installer/extras/surface-selection-wrapper/install.sh"
            ;;
        plate-aware-mesh)
            HOME="$pwd_home" K2_DEFER_FIRMWARE_RESTART=1 \
                sh "$INSTALLER_DIR/installer/extras/plate-aware-mesh/install.sh" --no-restart
            ;;
        *)
            warn "no repair action is registered for $component"
            return 1
            ;;
    esac
}

migration_component_restart_kind() {
    case "$1" in
        cartographer|save-config-restart|abort_homing|screws_tilt_adjust|kamp-adaptive-purge|axis_twist_compensation)
            echo code ;;
        *) echo config ;;
    esac
}

migration_apply_components() {
    local components_file succeeded restart_kind failures component restart_script
    components_file="$1"
    migration_require_idle || return 1
    succeeded="/tmp/k2-update-succeeded.$$"
    : > "$succeeded"
    restart_kind=config
    failures=0

    while IFS= read -r component; do
        [ -n "$component" ] || continue
        printf '\n--- Refreshing %s ---\n' "$(migration_component_label "$component")"
        if migration_repair_component "$component"; then
            printf '%s\n' "$component" >> "$succeeded"
            [ "$(migration_component_restart_kind "$component")" = code ] && restart_kind=code
        else
            warn "$(migration_component_label "$component") refresh failed; it remains pending"
            failures=$((failures + 1))
        fi
    done < "$components_file"

    if [ ! -s "$succeeded" ]; then
        rm -f "$succeeded"
        warn 'no component refresh completed'
        return 1
    fi

    printf '\n--- Final protected restart ---\n'
    if [ "$restart_kind" = code ] || [ -f /tmp/k2-klippy-code-restart-required ]; then
        restart_script="$INSTALLER_DIR/scripts/klippy_code_restart.sh"
    else
        restart_script="$INSTALLER_DIR/scripts/firmware_restart.sh"
    fi

    if K2_DEFER_FIRMWARE_RESTART=0 sh "$restart_script"; then
        while IFS= read -r component; do
            if ! migration_mark_component_current "$component"; then
                failures=$((failures + 1))
            fi
        done < "$succeeded"
        rm -f "$succeeded"
        if [ "$failures" -eq 0 ]; then
            printf '\n%s\n' "$(c_green 'Selected updates installed and activated successfully.')"
        else
            warn 'one or more updates remain pending; review the messages above'
        fi
    else
        rm -f "$succeeded"
        warn 'final protected restart failed; completed repairs remain pending for verification'
        warn 'power-cycle before homing or attempting a print'
        return 1
    fi

    [ "$failures" -eq 0 ]
}

menu_update_results() {
    local pending_file n component all_choice details_choice choice one_file
    mkdir -p "$MIGRATION_STATE_DIR"
    : > "$MIGRATION_INITIALIZED"
    while :; do
        clear
        ui_heading 'INSTALLER UPDATE RESULTS'
        printf '\n'
        migration_print_state_summary
        pending_file="/tmp/k2-update-pending.$$"
        migration_pending_components > "$pending_file"
        if [ ! -s "$pending_file" ]; then
            rm -f "$pending_file"
            printf '%s\n\n' "$(c_green 'All installed components are current. No repair action is pending.')"
            press_enter
            return 0
        fi

        printf 'Recommended updates for components installed on this printer:\n\n'
        n=0
        while IFS= read -r component; do
            n=$((n + 1))
            ui_menu_item "$n" "$(migration_component_label "$component")" "$(c_yellow 'ACTION NEEDED')"
        done < "$pending_file"
        all_choice=$((n + 1))
        details_choice=$((n + 2))
        ui_menu_item "$all_choice" 'Apply all recommended updates'
        ui_menu_item "$details_choice" 'Explain why each update is needed'
        printf '\n  0. Finish later / Back\n\nSelect [0-%s]: ' "$details_choice"
        read -r choice
        case "$choice" in
            0|b|B|q|Q)
                rm -f "$pending_file"
                return 0
                ;;
            ''|*[!0-9]*) ;;
            *)
                if [ "$choice" -eq "$all_choice" ] 2>/dev/null; then
                    if confirm 'Refresh every listed component and perform one final protected restart?'; then
                        migration_apply_components "$pending_file" || true
                        press_enter
                    fi
                elif [ "$choice" -eq "$details_choice" ] 2>/dev/null; then
                    rm -f "$pending_file"
                    migration_print_details
                    continue
                elif [ "$choice" -ge 1 ] 2>/dev/null && [ "$choice" -le "$n" ] 2>/dev/null; then
                    component=$(sed -n "${choice}p" "$pending_file")
                    one_file="/tmp/k2-update-one.$$"
                    printf '%s\n' "$component" > "$one_file"
                    if confirm "Refresh $(migration_component_label "$component") now?"; then
                        migration_apply_components "$one_file" || true
                        press_enter
                    fi
                    rm -f "$one_file"
                fi
                ;;
        esac
        rm -f "$pending_file"
    done
}

migration_pull_installer() {
    local review_after old new branch temporary
    review_after="$1"
    clear
    ui_heading 'UPDATE INSTALLER'
    printf '\n'
    migration_require_idle || return 1
    ensure_path
    if [ ! -d "$INSTALLER_DIR/.git" ]; then
        warn "$INSTALLER_DIR is not a git checkout - cannot auto-update."
        warn 'Re-run bootstrap.sh from the host to refresh.'
        press_enter
        return 1
    fi

    old=$(git -C "$INSTALLER_DIR" rev-parse --verify HEAD 2>/dev/null || echo unknown)
    branch=$(git -C "$INSTALLER_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || echo detached)
    if [ -n "$(git -C "$INSTALLER_DIR" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
        warn 'tracked installer files have local modifications; update stopped without changing them.'
        press_enter
        return 1
    fi

    # Preserve the old code's view of installed optional components before a
    # pull can introduce stricter or renamed detectors.
    migration_capture_installed_components

    info "git pull in $INSTALLER_DIR"
    if ! (cd "$INSTALLER_DIR" && git pull --ff-only); then
        warn 'git pull failed; the current menu remains loaded.'
        press_enter
        return 1
    fi
    new=$(git -C "$INSTALLER_DIR" rev-parse --verify HEAD 2>/dev/null || echo unknown)
    mkdir -p "$MIGRATION_STATE_DIR"
    temporary="$MIGRATION_STATE_DIR/.last-pull.$$"
    printf '%s|%s|%s\n' "$old" "$new" "$branch" > "$temporary"
    migration_write_atomic "$MIGRATION_LAST_PULL" "$temporary"
    if [ "$review_after" = yes ]; then
        : > "$MIGRATION_STATE_DIR/review-after-reload"
    fi
    printf '\n%s\n' "$(c_green 'Update complete. Reloading the installer...')"
    exec sh "$INSTALLER_DIR/menu.sh"
}

menu_update_installer() {
    while :; do
        clear
        ui_heading 'UPDATE INSTALLER'
        printf '\n'
        ui_menu_item 1 'Update and review required actions'
        ui_menu_item 2 'Review pending update actions'
        ui_menu_item 3 'Update installer files only'
        printf '\n  0. Back\n\nSelect [0-3]: '
        read -r choice
        case "$choice" in
            1) migration_pull_installer yes ;;
            2) menu_update_results ;;
            3)
                printf '\nUpdating files without repairs can leave installed generated files behind.\n'
                printf 'Pending actions will remain available from this menu.\n\n'
                if confirm 'Update installer files only?'; then migration_pull_installer no; fi
                ;;
            0|b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

migration_offer_on_startup() {
    local old new branch temporary
    if [ -f "$MIGRATION_STATE_DIR/review-after-reload" ]; then
        rm -f "$MIGRATION_STATE_DIR/review-after-reload"
        menu_update_results
        return
    fi
    # The pre-tracker updater could not write a handoff record before pulling
    # this code. A fast-forward pull normally leaves ORIG_HEAD available, so
    # recover it for the first report when possible. The catalog remains
    # authoritative if that Git metadata is unavailable.
    if [ ! -f "$MIGRATION_LAST_PULL" ] && [ -d "$INSTALLER_DIR/.git" ]; then
        old=$(git -C "$INSTALLER_DIR" rev-parse --verify ORIG_HEAD 2>/dev/null || true)
        new=$(git -C "$INSTALLER_DIR" rev-parse --verify HEAD 2>/dev/null || true)
        if [ -n "$old" ] && [ -n "$new" ] && [ "$old" != "$new" ]; then
            branch=$(git -C "$INSTALLER_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || echo detached)
            mkdir -p "$MIGRATION_STATE_DIR"
            temporary="$MIGRATION_STATE_DIR/.last-pull.$$"
            printf '%s|%s|%s\n' "$old" "$new" "$branch" > "$temporary"
            migration_write_atomic "$MIGRATION_LAST_PULL" "$temporary"
        fi
    fi
    # First tracker-aware launch on a legacy installation.  An unconfigured
    # printer has no applicable components and is left at the normal main menu.
    if [ ! -f "$MIGRATION_INITIALIZED" ] && migration_has_pending; then
        menu_update_results
    fi
}
