#!/bin/sh
# Top-level workflow menu. Sourced by menu.sh.

detect_installer_branch() {
    if [ -d "$INSTALLER_DIR/.git" ]; then
        git -C "$INSTALLER_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || echo 'detached'
    else
        echo 'not a git checkout'
    fi
}

detect_installer_commit() {
    if [ -d "$INSTALLER_DIR/.git" ]; then
        git -C "$INSTALLER_DIR" rev-parse --short=7 HEAD 2>/dev/null || echo 'unknown'
    else
        echo 'not a git checkout'
    fi
}

detect_remote_commit_state() {
    local branch local_commit remote_commit output_file pid elapsed
    if [ ! -d "$INSTALLER_DIR/.git" ]; then
        echo unavailable
        return
    fi
    branch=$(git -C "$INSTALLER_DIR" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
    local_commit=$(git -C "$INSTALLER_DIR" rev-parse --verify HEAD 2>/dev/null || true)
    if [ -z "$branch" ] || [ -z "$local_commit" ]; then
        echo unavailable
        return
    fi

    # Keep an offline printer from delaying the menu indefinitely. This is a
    # read-only remote-head query; option 6 remains responsible for pulling.
    output_file=$(mktemp /tmp/k2-installer-remote-head.XXXXXX) || {
        echo unavailable
        return
    }
    # Run Git directly so wait sees its exit status, not a successful awk
    # pipeline masking a failed query. On timeout, stop the query itself.
    GIT_TERMINAL_PROMPT=0 git -C "$INSTALLER_DIR" ls-remote --heads origin \
        "refs/heads/$branch" > "$output_file" 2>/dev/null &
    pid=$!
    elapsed=0
    while kill -0 "$pid" 2>/dev/null && [ "$elapsed" -lt 5 ]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        rm -f "$output_file"
        echo unavailable
        return
    fi
    if wait "$pid" 2>/dev/null; then
        remote_commit=$(awk -v ref="refs/heads/$branch" '$2 == ref { print $1; exit }' \
            "$output_file")
    else
        remote_commit=
    fi
    rm -f "$output_file"
    if [ -z "$remote_commit" ]; then
        echo unavailable
    elif [ "$remote_commit" = "$local_commit" ]; then
        echo current
    else
        echo available
    fi
}

main_menu() {
    local remote_commit_state checked_revision carto_version refresh_probe
    remote_commit_state=not_checked
    checked_revision=
    carto_version=
    refresh_probe=yes
    while :; do
        clear
        local fw chw cfw setup branch commit pending_updates update_state
        fw="$(detect_printer_fw)"
        if [ "$refresh_probe" = yes ]; then
            carto_version=
            if is_cartographer; then
                carto_version="$(_detect_carto_version_string || true)"
            fi
        fi
        chw="$(detect_carto_hw "$carto_version")"
        cfw="$(detect_carto_fw "$carto_version")"
        setup="$(detect_install_profile)"
        branch="$(detect_installer_branch)"
        commit="$(detect_installer_commit)"
        pending_updates="$(migration_pending_component_count)"
        # A manual result belongs to the checked branch and local commit.
        # Changing either requires another explicit check, never a network
        # request during an ordinary menu redraw.
        if [ -n "$checked_revision" ] && [ "$checked_revision" != "$branch:$commit" ]; then
            remote_commit_state=not_checked
            checked_revision=
        fi
        case "$remote_commit_state" in
            not_checked) update_state="$(c_dim 'NOT CHECKED')" ;;
            available) update_state="$(c_yellow 'INSTALLER UPDATE AVAILABLE')" ;;
            current) update_state="$(c_green 'INSTALLER UP TO DATE')" ;;
            *) update_state="$(c_yellow 'CHECK FAILED')" ;;
        esac
        if [ "$pending_updates" -gt 0 ]; then
            update_state="$(c_yellow "$pending_updates ACTION(S) PENDING") | $update_state"
        fi

        ui_rule
        printf ' %s\n' "$(c_cyan 'K2 PLUS COMPATIBILITY INSTALLER')"
        printf '%s\n' '------------------------------------------------------------'
        printf ' Firmware : %s\n' "$(c_cyan "$fw")"
        printf ' Branch   : %s\n' "$(c_cyan "$branch")"
        printf ' Commit   : %s\n' "$(c_cyan "$commit")"
        case "$setup" in
            *incomplete*) printf ' Setup    : %s\n' "$(c_yellow "$setup")" ;;
            *) printf ' Setup    : %s\n' "$(c_green "$setup")" ;;
        esac
        if is_cartographer; then
            printf ' Probe    : %s / firmware %s\n' "$(c_cyan "${chw:-unknown}")" "$(c_cyan "${cfw:-unknown}")"
            printf ' Mount    : %s\n' "$(c_cyan "$(detect_carto_offset_label)")"
        fi
        ui_rule

        printf '\n'
        ui_menu_item 1 'Status and diagnostics'
        ui_menu_item 2 'Install or change setup'
        ui_menu_item 3 'Cartographer tools'
        ui_menu_item 4 'Optional extras'
        ui_menu_item 5 'Maintenance and recovery'
        ui_menu_item 6 'Update installer / apply updates' "$update_state"
        ui_menu_item 7 'Check for installer updates'
        printf '\n  0. Exit\n\nSelect [0-7]: '
        read_prompt c
        refresh_probe=yes
        case "$c" in
            1) show_status ;;
            2) menu_install_paths ;;
            3) menu_cartographer_tools ;;
            4) menu_extras ;;
            5) menu_maintenance ;;
            6) menu_update_installer ;;
            7)
                printf '\nChecking installer updates for %s (up to 5 seconds)...\n' "$branch"
                remote_commit_state="$(detect_remote_commit_state)"
                checked_revision="$branch:$commit"
                # Checking GitHub does not change probe firmware. Reuse this
                # panel's metadata instead of repeating an offline MCU query.
                refresh_probe=no
                ;;
            0|q|Q) exit 0 ;;
            *) ;;
        esac
    done
}
