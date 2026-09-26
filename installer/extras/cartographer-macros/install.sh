#!/bin/sh
# Install CARTO_* macros that wrap CARTOGRAPHER_* commands into [gcode_macro]
# definitions, so Fluidd's macros panel shows them as buttons.
#
# Idempotent — re-runs just refresh the symlink and ensure the include.

set -eu

SHOW_PLATE_SELECTORS=0
case "${1:-}" in
    '') ;;
    --show-plate-selectors) SHOW_PLATE_SELECTORS=1 ;;
    *) echo "ERROR: usage: install.sh [--show-plate-selectors]"; exit 2 ;;
esac

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM="$CFG_DIR/custom"
KLIPPER_EXTRAS="${KLIPPER_DIR:-${HOME}/klipper}/klippy/extras"

# Reinstalling core Cartographer must not hide selectors when the optional
# workflow is already active. A fresh optional install passes the flag before
# its surface wrapper exists.
if [ "$SHOW_PLATE_SELECTORS" -eq 0 ] && \
        grep -q 'surface-selection wrapper' "$CUSTOM/start_print.cfg" 2>/dev/null; then
    SHOW_PLATE_SELECTORS=1
fi

[ -d "$CUSTOM" ] || { echo "ERROR: $CUSTOM not found — install macros feature first"; exit 1; }
grep -q '^\[cartographer\]' "$CFG_DIR/printer.cfg" "$CUSTOM"/*.cfg 2>/dev/null || {
    echo "ERROR: no [cartographer] section found — install cartographer feature first"
    exit 1
}

ln -sfn "$SCRIPT_DIR/cartographer_macros.cfg" "$CUSTOM/cartographer_macros.cfg"
echo "I: symlinked cartographer_macros.cfg into custom/"

# The first editor prototype was bundled into this plate workflow. Remove only
# that old symlink; the separate optional feature uses a different source path.
legacy_editor="$KLIPPER_EXTRAS/k2_cartographer_offset_editor.py"
if [ -L "$legacy_editor" ]; then
    case "$(readlink "$legacy_editor")" in
        *'/cartographer-macros/k2_cartographer_offset_editor.py')
            rm -f "$legacy_editor"
            echo "I: removed the superseded plate-workflow offset editor"
            ;;
    esac
fi
# Wire include into custom/main.cfg
INSTALLER_BASE="${INSTALLER_DIR:-$(readlink -f "$SCRIPT_DIR/../../..")}"
ENSURE_INCLUDED="$INSTALLER_BASE/scripts/ensure_included.py"
if [ -f "$ENSURE_INCLUDED" ]; then
    python3 "$ENSURE_INCLUDED" "$CUSTOM/main.cfg" cartographer_macros.cfg
else
    grep -q '^\[include cartographer_macros.cfg\]' "$CUSTOM/main.cfg" 2>/dev/null \
        || echo "[include cartographer_macros.cfg]" >> "$CUSTOM/main.cfg"
fi

echo "I: cartographer-macros installed. CARTO_* macros appear in Fluidd"
echo "I: after FIRMWARE_RESTART completes the full K2 startup sequence."

if [ "$SHOW_PLATE_SELECTORS" -eq 1 ]; then
    LAYOUT_ARG="--show-plate-selectors"
else
    LAYOUT_ARG=""
fi

set --
if [ -n "${K2_PLATE_SLICERS:-}" ]; then
    set -- --plate-slicers "$K2_PLATE_SLICERS"
fi
if python3 "$SCRIPT_DIR/configure_fluidd_layout.py" $LAYOUT_ARG "$@"; then
    :
else
    echo "W: macros were installed, but their Fluidd aliases/category could not be configured"
    echo "W: use Fluidd Settings -> Macros to configure them manually"
    exit 1
fi
