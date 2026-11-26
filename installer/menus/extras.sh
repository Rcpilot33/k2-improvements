#!/bin/sh
# K2-Plus extras (patches not in upstream k2-improvements). Install only.

# name|detector|description|script_path|requires  (one per line; script_path
# relative to INSTALLER_DIR; requires is the name of a function that must
# return 0 for the extra to be installable - empty if no precondition).
_EXTRAS='prtouch-cleanup|is_prtouch_clean|Remove orphan [prtouch_v3] SAVE_CONFIG header|installer/extras/prtouch-cleanup/install.sh|is_cartographer
surface-selection-wrapper|is_surface_wrap|START_PRINT SURFACE= param loads matching scan/touch model|installer/extras/surface-selection-wrapper/install.sh|is_cartographer
cartographer-offset-setup|is_carto_offset_set|Cartographer mount offset profiles/custom|installer/extras/cartographer-offset-setup/install.sh|is_cartographer
cartographer-macros|is_carto_macros|CARTO_* Fluidd buttons (profiles/calibration/load)|installer/extras/cartographer-macros/install.sh|is_cartographer
global-touch-offsets|is_global_touch_offsets|Interactive Cartographer global Scan/Touch offset editor|installer/extras/global-touch-offsets/install.sh|is_cartographer
global-prtouch-offsets|is_global_prtouch_offsets|Default and plate-aware no-Carto global Z editor|installer/extras/global-prtouch-offsets/install.sh|is_stock_probe
material-z-offsets|is_material_z_offsets|Interactive material Z-offset editor|installer/extras/material-z-offsets/install.sh|is_macros
plate-aware-mesh|is_plate_aware_mesh|Saved meshes selected by build plate and temperature|installer/extras/plate-aware-mesh/install.sh|is_stock_probe
secure-auth|is_secure_auth|Disable SSH password login (requires a tested public key)|features/secure-auth/install.sh|
r3men-bed|is_r3men_bed|R3MEN graphite-bed thermistor profile|features/r3men-bed/install.sh|'

if [ -f "$INSTALLER_DIR/installer/extras/nozzle-camera/install.sh" ]; then
    _EXTRAS="${_EXTRAS}
nozzle-camera|is_nozzle_camera|Stream the factory nozzle camera in Fluidd|installer/extras/nozzle-camera/install.sh|is_stock_nozzle_camera_available"
fi

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
        is_macros)       echo "needs Macros" ;;
        is_stock_nozzle_camera_available) echo "JimmyV mounts have no factory nozzle camera" ;;
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

    if [ "$req" = is_stock_nozzle_camera_available ] && ! "$req" 2>/dev/null; then
        c_yellow 'UNAVAILABLE (JIMMYV MOUNT)'
    elif "$det" 2>/dev/null; then
        state_installed
    elif [ -n "$req" ] && ! "$req" 2>/dev/null; then
        case "$req" in
            is_cartographer) state_requires 'CARTOGRAPHER' ;;
            is_stock_probe) state_requires 'STOCK PR TOUCH' ;;
            is_macros) state_requires 'MACROS' ;;
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
    elif is_surface_wrap; then
        state_incomplete
    elif ! is_cartographer; then
        state_requires 'CARTOGRAPHER'
    else
        state_not_installed
    fi
}

choose_plate_workflow_slicers() {
    local plate_choice
    printf '\nPlate selectors: 1. Creality Print  2. OrcaSlicer  3. Both\n'
    printf 'Select [1-3], or Enter to keep the saved choice: '
    read_prompt plate_choice
    case "$plate_choice" in
        1) plate_slicers=creality ;;
        2) plate_slicers=orca ;;
        3) plate_slicers=both ;;
        '') plate_slicers='' ;;
        *) warn 'Invalid plate selector choice'; press_enter; return 1 ;;
    esac
}

run_carto_plate_workflow() {
    clear
    ui_heading 'CARTOGRAPHER PLATE PROFILES / AUTO-SELECTION'
    printf '\nThis installs the two tied parts of the plate workflow:\n'
    printf '  - reveals plate buttons for Creality Print, OrcaSlicer, or both\n'
    printf '  - START_PRINT surface selection using the slicer plate choice\n\n'

    if ! is_cartographer; then
        printf '%s\n' "$(c_yellow 'Cannot install: Cartographer is required first.')"
        press_enter
        return 1
    fi

    printf '  %-32s %s\n' 'Named plate selectors' \
        "$(if is_carto_macros; then state_installed; else state_not_installed; fi)"
    printf '  %-32s %s\n\n' 'Surface-selection wrapper' \
        "$(if is_surface_wrap; then state_installed; else state_not_installed; fi)"

    if ! confirm 'Install or update the plate workflow and choose its selectors?'; then
        return 0
    fi

    migration_require_idle || return 1
    local pwd_home failed plate_slicers
    choose_plate_workflow_slicers || return 1
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="${HOME:-/mnt/UDISK/root}"
    [ -n "$pwd_home" ] || pwd_home=/mnt/UDISK/root
    failed=0

    info 'refreshing Cartographer Fluidd macros'
    K2_PLATE_SLICERS="$plate_slicers" HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
        sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh" \
            --show-plate-selectors \
        || failed=1

    if [ "$failed" -eq 0 ]; then
        info 'refreshing surface-selection wrapper'
        HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" \
            sh "$INSTALLER_DIR/installer/extras/surface-selection-wrapper/install.sh" \
            || failed=1
    fi

    if [ "$failed" -eq 0 ] && is_carto_plate_workflow; then
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            if ! migration_mark_component_current cartographer-plate-workflow; then
                warn "Plate workflow update verification is incomplete; review pending actions in Update installer / apply updates"
                return 1
            fi
        fi
        printf '\n%s\n' "$(c_green 'Cartographer plate workflow installed successfully.')"
        printf 'When no print is active, run FIRMWARE_RESTART and wait for the complete\n'
        printf 'K2 startup sequence. Power-cycle before homing only if it reports an error.\n'
    else
        printf '\n%s\n' "$(c_yellow 'Plate workflow is incomplete; review the errors above.')"
    fi
    press_enter
}

run_axis_twist_removal() {
    # Recheck at selection time: ATC may have been removed since the menu was
    # drawn, or the user may have entered the hidden legacy option number.
    if ! has_legacy_axis_twist; then
        info 'Legacy Axis Twist was not detected; nothing to remove.'
        press_enter
        return 0
    fi
    clear
    ui_heading 'REMOVE LEGACY AXIS TWIST'
    show_feature_readme axis-twist-removal "$INSTALLER_DIR/installer/extras/axis-twist-removal/README.md"
    printf '\nRestores the hash-matched stock probe helper and PR Touch registration.\n'
    printf 'Backs up ATC files/calibration, keeps meshes and Z offsets, and performs\n'
    printf 'the protected Klippy restart. Re-mesh and recheck Z offsets afterward.\n'
    printf 'Unknown firmware/files will be refused before any change.\n\n'
    if ! confirm 'Printer idle and pending meshes saved: remove legacy ATC now?'; then return 0; fi
    if sh "$INSTALLER_DIR/installer/extras/axis-twist-removal/uninstall.sh"; then
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            migration_mark_component_current axis-twist-removal || return 1
        fi
    else
        warn 'ATC removal did not complete; review the error above before homing'
        press_enter
        return 1
    fi
    press_enter
}

# Ordered allowlist: security, hardware conversion, removal and calibration
# actions remain individual workflows. Plate selection precedes offset editors.
extras_batch_names() {
    printf '%s\n' r3men-bed
    if is_stock_nozzle_camera_available; then printf '%s\n' nozzle-camera; fi
    printf '%s\n' kamp-adaptive-purge
    if is_cartographer; then
        printf '%s\n' cartographer-plate-workflow global-touch-offsets
    elif is_stock_probe; then
        printf '%s\n' plate-aware-mesh global-prtouch-offsets
    fi
    if is_macros; then printf '%s\n' material-z-offsets; fi
}

extras_batch_install() {
    local name="$1" line script req
    if [ "$name" = cartographer-plate-workflow ]; then
        is_cartographer || return 1
        sh "$INSTALLER_DIR/installer/extras/cartographer-macros/install.sh" --show-plate-selectors || return 1
        sh "$INSTALLER_DIR/installer/extras/surface-selection-wrapper/install.sh"
        return $?
    fi
    line=$(extra_line "$name")
    [ -n "$line" ] || return 1
    req=$(printf '%s' "$line" | cut -d'|' -f5)
    if [ -n "$req" ]; then "$req" || return 1; fi
    script=$(printf '%s' "$line" | cut -d'|' -f4)
    [ -f "$INSTALLER_DIR/$script" ] || return 1
    sh "$INSTALLER_DIR/$script"
}

run_extras_batch() {
    local names number name choices choice selected='' plate_slicers=''
    local completed='' failed=0 attempted=0 pwd_home
    names=$(extras_batch_names)
    ui_heading 'INSTALL MULTIPLE OPTIONAL EXTRAS'
    printf '\nSelect numbers separated by spaces. Installed extras will be refreshed.\n'
    printf 'Secure Auth, hardware conversion, removal and calibration stay separate.\n'
    number=0
    for name in $names; do
        number=$((number + 1))
        printf '  %s. %s\n' "$number" "$name"
    done
    printf '\nSelection (Enter or 0 to go back): '
    read_prompt choices
    case "$choices" in ''|0) return 0 ;; esac
    # Validate every token before any installer or settings prompt runs.
    for choice in $choices; do
        case "$choice" in *[!0-9]*|'') warn 'Invalid selection'; return 1 ;; esac
        if ! printf '%s\n' "$names" | awk -v n="$choice" 'NR == n {found=1} END {exit !found}'; then
            warn 'Invalid selection'; return 1
        fi
    done
    number=0
    for name in $names; do
        number=$((number + 1))
        for choice in $choices; do
            if [ "$choice" -eq "$number" ]; then
                selected="$selected $name"
                break
            fi
        done
    done
    [ -n "$selected" ] || { warn 'No extras selected'; return 1; }
    printf '\nInstall order:\n'
    for name in $selected; do printf '  %s\n' "$name"; done
    case " $selected " in
        *' r3men-bed '*) printf '\nR3MEN is only for the matching replacement bed thermistor.\n' ;;
    esac
    printf 'Feature settings questions still apply. One protected restart follows.\n'
    confirm 'Install the selected extras?' || return 0
    migration_require_idle || return 1
    case " $selected " in
        *' cartographer-plate-workflow '*|*' plate-aware-mesh '*) choose_plate_workflow_slicers || return 1 ;;
    esac
    pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="${HOME:-/mnt/UDISK/root}"
    for name in $selected; do
        info "Installing $name"
        attempted=1
        # A subshell confines the exported batch settings; stdin remains the
        # terminal so KAMP and other interactive installers keep their prompts.
        if (
            export HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH"
            export K2_DEFER_FIRMWARE_RESTART=1 K2_PLATE_SLICERS="$plate_slicers"
            extras_batch_install "$name"
        ); then
            completed="$completed $name"
        else
            warn "$name failed; remaining selections were not attempted."
            failed=1
            break
        fi
    done
    if [ "$attempted" -eq 1 ]; then
        # Some extras install Python modules without setting the reload marker.
        # Always reload the host, then use its protected firmware restart.
        if ! K2_DEFER_FIRMWARE_RESTART=0 sh "$INSTALLER_DIR/scripts/klippy_code_restart.sh"; then
            warn 'Final protected restart failed; power-cycle before homing. Updates remain pending.'
            press_enter
            return 1
        fi
    fi
    for name in $completed; do
        info "$name installed"
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            migration_mark_component_current "$name" || {
                warn "$name verification incomplete; review pending updates."
                failed=1
            }
        fi
    done
    if [ "$failed" -eq 0 ]; then
        info 'Selected extras installed and protected restart completed.'
    else
        warn 'Batch incomplete; review the failures above before printing.'
    fi
    press_enter
    return "$failed"
}

menu_extras() {
    while :; do
        clear
        ui_heading 'OPTIONAL EXTRAS'
        printf '\n Hardware\n'
        ui_menu_item 1 'R3MEN bed thermistor profile' "$(extra_state r3men-bed)"
        printf '\n Camera\n'
        ui_menu_item 2 'Stock nozzle camera stream' "$(extra_state nozzle-camera)"
        printf '\n Print workflow\n'
        ui_menu_item 3 'KAMP adaptive purge' "$(extra_state kamp-adaptive-purge)"
        if has_legacy_axis_twist; then
            ui_menu_item 4 'Remove legacy Axis Twist' "$(c_yellow 'REMOVAL AVAILABLE')"
        fi
        if is_cartographer; then
            ui_menu_item 5 'Cartographer plate workflow' "$(carto_plate_workflow_state)"
            ui_menu_item 6 'Global Carto Z Offsets' "$(extra_state global-touch-offsets)"
            ui_menu_item 7 'Material Z Offsets' "$(extra_state material-z-offsets)"
            printf '\n Security\n'
            ui_menu_item 8 'Secure Auth' "$(extra_state secure-auth)"
            printf '\n Nozzle-camera replacement\n'
            ui_menu_item 9 'JimmyV AI / nozzle USB power protection' "$(if is_nozzle_usb_cartographer; then state_installed; else state_not_installed; fi)"
            printf '\n Batch install\n'
            ui_menu_item 10 'Install multiple optional extras'
            printf '\n  0. Back\n\nSelect [0-10]: '
        else
            ui_menu_item 5 'Plate-aware saved meshes' "$(extra_state plate-aware-mesh)"
            ui_menu_item 6 'Global No-Carto Z Offsets' "$(extra_state global-prtouch-offsets)"
            ui_menu_item 7 'Material Z Offsets' "$(extra_state material-z-offsets)"
            printf '\n Security\n'
            ui_menu_item 8 'Secure Auth' "$(extra_state secure-auth)"
            printf '\n Batch install\n'
            ui_menu_item 10 'Install multiple optional extras'
            printf '\n  0. Back\n\nSelect [0-8,10]: '
        fi
        read_prompt c
        case "$c" in
            10) run_extras_batch ;;
            1) run_extra_name r3men-bed ;;
            2) run_extra_name nozzle-camera ;;
            3) run_extra_name kamp-adaptive-purge ;;
            4) run_axis_twist_removal ;;
            5)
                if is_cartographer; then
                    run_carto_plate_workflow
                else
                    run_extra_name plate-aware-mesh
                fi
                ;;
            6)
                if is_cartographer; then
                    run_extra_name global-touch-offsets
                else
                    run_extra_name global-prtouch-offsets
                fi
                ;;
            7)
                if is_cartographer; then
                    run_extra_name material-z-offsets
                else
                    run_extra_name material-z-offsets
                fi
                ;;
            8)
                run_extra_name secure-auth
                ;;
            9)
                if is_cartographer; then
                    show_feature_readme nozzle-usb-cartographer "$INSTALLER_DIR/installer/extras/nozzle-usb-cartographer/README.md"
                    migration_require_idle || continue
                    if sh "$INSTALLER_DIR/installer/extras/nozzle-usb-cartographer/install.sh"; then
                        if is_nozzle_usb_cartographer; then
                            migration_mark_component_current nozzle-usb-cartographer
                            if ! is_nozzle_camera; then ota_record_option nozzle-camera remove; fi
                        else
                            ota_record_option nozzle-usb-cartographer remove
                        fi
                    fi
                    press_enter
                fi
                ;;
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
    local script_arg=''
    local plate_slicers="${K2_PLATE_SLICERS:-}"

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
            is_macros)
                printf '  This extra requires the managed START_PRINT macros first.\n\n'
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
        plate-aware-mesh)
            if "$det" 2>/dev/null; then
                printf '  Status: %s\n\n' "$(c_green 'ALREADY APPLIED')"
            fi
            if ! confirm 'Install or update plate-aware meshes and choose its slicers?'; then return 0; fi
            choose_plate_workflow_slicers || return 1
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
            read_prompt secure_auth_answer
            if [ "$secure_auth_answer" != "SECURE AUTH" ]; then
                warn 'confirmation did not match; Secure Auth was not changed.'
                press_enter
                return 0
            fi
            ;;
        kamp-adaptive-purge)
            if "$det" 2>/dev/null; then
                printf '  Status: %s\n\n' "$(c_green 'ALREADY APPLIED')"
                printf '  1. Review/change settings\n'
                printf '  2. Reinstall/update KAMP\n'
                printf '  0. Back\n\n'
                printf 'Select [0-2]: '
                local kamp_choice
                read_prompt kamp_choice
                case "$kamp_choice" in
                    1) script_arg='--configure-only' ;;
                    2) ;;
                    0|b|B|q|Q|'') return 0 ;;
                    *)
                        warn 'invalid selection'
                        press_enter
                        return 0
                        ;;
                esac
            else
                if ! confirm "Apply $name now?"; then return 0; fi
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

    migration_require_idle || return 1
    local pwd_home=$(awk -F: '$1=="root"{print $6}' /etc/passwd)
    [ -n "$pwd_home" ] || pwd_home="${HOME:-/mnt/UDISK/root}"
    [ -n "$pwd_home" ] || pwd_home=/mnt/UDISK/root
    info "running $script (HOME=$pwd_home)"
    if K2_PLATE_SLICERS="$plate_slicers" HOME="$pwd_home" PATH="/opt/bin:/opt/sbin:$PATH" sh "$script" $script_arg; then
        info "$name install completed"
        if command -v migration_mark_component_current >/dev/null 2>&1; then
            if ! migration_mark_component_current "$name"; then
                warn "$name installed, but update verification is incomplete; review pending actions in Update installer / apply updates"
            fi
        fi
    else
        warn "$name install.sh exited non-zero"
    fi
    press_enter
}
