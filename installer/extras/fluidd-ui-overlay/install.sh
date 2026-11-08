#!/bin/sh
# Compatibility entry point: the settings dialogs now ship in Fluidd itself.
set -eu
FLUIDD_ROOT="${FLUIDD_DIR:-/usr/share/fluidd}"
OVERLAY_VERSION=9
version=$(cat "$FLUIDD_ROOT/k2-ui-overlay-support.txt" 2>/dev/null || true)
case "$version" in
    ''|*[!0-9]*) version=0 ;;
esac
if [ "$version" -lt "$OVERLAY_VERSION" ]; then
    echo 'ERROR: install the consolidated Rcpilot33 Fluidd build before installing settings editors.'
    echo '       Test builds: features/fluidd/install.sh --archive /absolute/path/fluidd.zip'
    exit 1
fi
echo 'I: settings dialogs are provided by the installed Fluidd build'
