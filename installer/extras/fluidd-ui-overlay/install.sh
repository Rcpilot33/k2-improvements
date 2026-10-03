#!/bin/sh
# Install the shared Fluidd UI used by the live settings editors.

set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
FLUIDD_ROOT="${FLUIDD_DIR:-/usr/share/fluidd}"
FLUIDD_ARCHIVE="$SCRIPT_DIR/fluidd-v1.37.4.zip"
FLUIDD_VERSION=v1.37.4
OVERLAY_VERSION=6

[ -f "$FLUIDD_ARCHIVE" ] || { echo "ERROR: bundled Fluidd UI archive is missing: $FLUIDD_ARCHIVE"; exit 1; }
[ -d "$FLUIDD_ROOT" ] || { echo "ERROR: Fluidd is not installed at $FLUIDD_ROOT"; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "ERROR: unzip is required; install the Fluidd core component first"; exit 1; }

fluidd_target="$(readlink -f "$FLUIDD_ROOT")"
case "$fluidd_target" in
    ''|'/'|"$HOME")
        echo "ERROR: refusing unsafe Fluidd target: $fluidd_target"
        exit 1
        ;;
esac

if [ "$(cat "$fluidd_target/k2-ui-overlay-support.txt" 2>/dev/null || true)" = "$OVERLAY_VERSION" ]; then
    python3 "$SCRIPT_DIR/../../../features/fluidd/set_release_source.py" \
        "$fluidd_target/release_info.json" Rcpilot33 fluidd
    chmod -R a+rX "$fluidd_target"
    echo "I: shared Fluidd settings controls are already installed"
    exit 0
fi

installed_version="$(cat "$fluidd_target/.version" 2>/dev/null || true)"
[ "$installed_version" = "$FLUIDD_VERSION" ] || {
    echo "ERROR: settings controls require Jacob Fluidd $FLUIDD_VERSION"
    echo "       Installed version: ${installed_version:-unknown}"
    echo "       Reinstall the Fluidd core component, then try again."
    exit 1
}

staging="${fluidd_target}.z-offset-ui.$$"
replaced="${fluidd_target}.replaced.$$"
legacy_backup="${fluidd_target}.before-global-touch-offsets"
backup="${fluidd_target}.before-k2-ui-overlay"
mkdir -p "$staging"
cleanup_swap() {
    if [ -e "$replaced" ] && [ ! -e "$fluidd_target" ]; then
        mv "$replaced" "$fluidd_target"
    fi
    rm -rf "$staging"
    if [ -e "$fluidd_target" ]; then
        rm -rf "$replaced"
    fi
}
trap cleanup_swap EXIT INT TERM

unzip -oq "$FLUIDD_ARCHIVE" -d "$staging"
python3 "$SCRIPT_DIR/../../../features/fluidd/set_release_source.py" \
    "$staging/release_info.json" Rcpilot33 fluidd
# Ensure nginx can read the static files even if an archive was built on a
# platform that recorded owner-only permissions for its entries.
chmod -R a+rX "$staging"
[ "$(cat "$staging/.version" 2>/dev/null || true)" = "$FLUIDD_VERSION" ] &&
    [ -f "$staging/index.html" ] &&
    [ -f "$staging/sw.js" ] &&
    [ "$(cat "$staging/k2-ui-overlay-support.txt" 2>/dev/null || true)" = "$OVERLAY_VERSION" ] || {
        echo "ERROR: bundled Fluidd UI failed validation"
        exit 1
    }

# Keep the original pre-overlay backup when upgrading an existing installation.
# Otherwise create one neutral backup exactly once.
if [ ! -e "$legacy_backup" ] && [ ! -e "$backup" ]; then
    cp -a "$fluidd_target" "$backup"
    echo "I: backed up Fluidd to $backup"
fi

mv "$fluidd_target" "$replaced"
if ! mv "$staging" "$fluidd_target"; then
    mv "$replaced" "$fluidd_target"
    echo "ERROR: could not activate the shared Fluidd Z-offset controls"
    exit 1
fi
rm -rf "$replaced"
trap - EXIT INT TERM

if [ "${K2_SKIP_NGINX_RESTART:-0}" != "1" ]; then
    /etc/init.d/nginx restart
fi
echo "I: installed the shared Fluidd settings controls"
