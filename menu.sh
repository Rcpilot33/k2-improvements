#!/bin/sh
# K2 Plus installer - TUI entry point. Run this on the printer.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
INSTALLER_DIR="$SCRIPT_DIR"
export INSTALLER_DIR

. "$SCRIPT_DIR/installer/detect/printer_model.sh"
check_installer_model menu || exit 1

INSTALLER_LOCK=/tmp/k2-improvements-installer.lock
if [ "${K2_MENU_LOCK_PID:-}" != "$$" ]; then
    exec python3 "$SCRIPT_DIR/installer/menu_lock.py" "$INSTALLER_LOCK" sh "$SCRIPT_DIR/menu.sh" "$@"
fi

# Keep the old PID marker for older checkouts. The kernel owns the actual lock.
trap 'rm -f "$INSTALLER_LOCK/pid"; rmdir "$INSTALLER_LOCK" 2>/dev/null || :' EXIT
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
migration_offer_on_startup
main_menu
