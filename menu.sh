#!/bin/sh
# K2 Plus installer - TUI entry point. Run this on the printer.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
INSTALLER_DIR="$SCRIPT_DIR"
export INSTALLER_DIR

INSTALLER_LOCK=/tmp/k2-improvements-installer.lock
acquire_installer_lock() {
    if mkdir "$INSTALLER_LOCK" 2>/dev/null; then
        printf '%s\n' "$$" > "$INSTALLER_LOCK/pid"
        return 0
    fi

    lock_pid=$(cat "$INSTALLER_LOCK/pid" 2>/dev/null || true)
    # update.sh reloads this menu with exec, which retains the same PID.
    [ "$lock_pid" = "$$" ] && return 0
    if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
        echo "ERROR: another K2 Plus installer is running (PID $lock_pid)." >&2
        exit 1
    fi

    rm -rf "$INSTALLER_LOCK"
    mkdir "$INSTALLER_LOCK"
    printf '%s\n' "$$" > "$INSTALLER_LOCK/pid"
}

release_installer_lock() {
    lock_pid=$(cat "$INSTALLER_LOCK/pid" 2>/dev/null || true)
    [ "$lock_pid" != "$$" ] || rm -rf "$INSTALLER_LOCK"
}

acquire_installer_lock
trap release_installer_lock EXIT
# Signal traps must terminate the shell.  A cleanup-only trap returns to the
# interrupted menu loop and can leave an installer running after its terminal
# has closed.
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# If better-root has already changed root's home in /etc/passwd, but this
# SSH session was opened before that change, $HOME may still be /root.
# Correct it here so feature installers that use $HOME write to UDISK.
ROOT_HOME="$(awk -F: '$1=="root" {print $6}' /etc/passwd 2>/dev/null || true)"
if [ "$ROOT_HOME" = "/mnt/UDISK/root" ] && [ "${HOME:-}" != "/mnt/UDISK/root" ]; then
    export HOME=/mnt/UDISK/root
    cd "$HOME" 2>/dev/null || true
fi

for module in \
    installer/lib/common.sh \
    installer/detect/printer_fw.sh installer/detect/cartographer.sh installer/detect/features.sh \
    installer/menus/status.sh installer/menus/features.sh installer/menus/extras.sh \
    installer/menus/install_no_carto.sh installer/menus/install_all.sh installer/menus/carto_fw.sh \
    installer/menus/factory_reset.sh installer/menus/workflows.sh installer/migrations/catalog.sh \
    installer/menus/update.sh bootstrap/prerequisites.sh installer/menus/ota_review.sh installer/menus/main.sh
do
    if [ ! -s "$SCRIPT_DIR/$module" ]; then
        echo "E: missing $module. Rerun bootstrap for the installed branch to recover the checkout." >&2
        exit 1
    fi
    . "$SCRIPT_DIR/$module"
done

require_root
ensure_path
ota_bootstrap_preflight
if [ "$bootstrap_needs_review" = 0 ] && [ -z "$(ota_review_notice)" ]; then
    migration_offer_on_startup
fi
main_menu
