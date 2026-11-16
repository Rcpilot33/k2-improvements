#!/bin/sh
# Compatibility entry point: the settings dialogs now ship in Fluidd itself.
set -eu
FLUIDD_ROOT="${FLUIDD_DIR:-/usr/share/fluidd}"
OVERLAY_VERSION=8
version=$(cat "$FLUIDD_ROOT/k2-ui-overlay-support.txt" 2>/dev/null || true)
case "$version" in
    ''|*[!0-9]*) version=0 ;;
esac
if [ "$version" -lt "$OVERLAY_VERSION" ] ||
   [ "$(cat "$FLUIDD_ROOT/k2-settings-api.txt" 2>/dev/null || true)" != 1 ]; then
    echo 'ERROR: install the consolidated Rcpilot33 Fluidd build before installing settings editors.'
    echo '       Use the Fluidd core installer to install stable v1.37.5 or a newer compatible release.'
    exit 1
fi
echo 'I: settings dialogs are provided by the installed Fluidd build'
