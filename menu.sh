#!/bin/sh
# K2 Plus installer — TUI entry point. Run this on the printer.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
INSTALLER_DIR="$SCRIPT_DIR"
export INSTALLER_DIR

# If better-root has already changed root's home in /etc/passwd, but this
# SSH session was opened before that change, $HOME may still be /root.
# Correct it here so feature installers that use $HOME write to UDISK.
ROOT_HOME="$(awk -F: '$1=="root" {print $6}' /etc/passwd 2>/dev/null || true)"
if [ "$ROOT_HOME" = "/mnt/UDISK/root" ] && [ "${HOME:-}" != "/mnt/UDISK/root" ]; then
    export HOME=/mnt/UDISK/root
    cd "$HOME" 2>/dev/null || true
fi

. "$SCRIPT_DIR/installer/lib/common.sh"
. "$SCRIPT_DIR/installer/detect/printer_fw.sh"
. "$SCRIPT_DIR/installer/detect/cartographer.sh"
. "$SCRIPT_DIR/installer/detect/features.sh"
. "$SCRIPT_DIR/installer/menus/status.sh"
. "$SCRIPT_DIR/installer/menus/features.sh"
. "$SCRIPT_DIR/installer/menus/extras.sh"
. "$SCRIPT_DIR/installer/menus/install_no_carto.sh"
. "$SCRIPT_DIR/installer/menus/install_all.sh"
. "$SCRIPT_DIR/installer/menus/carto_fw.sh"
. "$SCRIPT_DIR/installer/menus/factory_reset.sh"
. "$SCRIPT_DIR/installer/menus/main.sh"

require_root
ensure_path
main_menu
