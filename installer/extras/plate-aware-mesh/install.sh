#!/bin/sh
# Enable plate-aware saved mesh names on the stock PR Touch setup.

set -eu

NO_RESTART=0
case "${1:-}" in
    '') ;;
    --no-restart) NO_RESTART=1 ;;
    *) echo 'ERROR: usage: install.sh [--no-restart]'; exit 2 ;;
esac

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CUSTOM_DIR="$CFG_DIR/custom"
MAIN_CFG="$CUSTOM_DIR/main.cfg"
OVERRIDES_CFG="$CUSTOM_DIR/overrides.cfg"
TARGET="$CUSTOM_DIR/plate_aware_mesh.cfg"
SOURCE="$SCRIPT_DIR/plate_aware_mesh.cfg"
PYTHON="${K2_PYTHON:-python3}"

if grep -qE '^\[cartographer\]' "$CFG_DIR/printer.cfg" "$CUSTOM_DIR/"*.cfg 2>/dev/null; then
    echo "ERROR: plate-aware saved meshes are for the stock PR Touch path."
    echo "       Cartographer creates an adaptive mesh for each print and uses"
    echo "       its separate plate-model workflow."
    exit 1
fi

[ -f "$SOURCE" ] || {
    echo "ERROR: feature config not found: $SOURCE"
    exit 1
}
[ -f "$CUSTOM_DIR/start_print.cfg" ] || {
    echo "ERROR: custom/start_print.cfg not found - install macros first"
    exit 1
}
[ -f "$CUSTOM_DIR/bed_mesh.cfg" ] || {
    echo "ERROR: custom/bed_mesh.cfg not found - install macros first"
    exit 1
}
[ -f "$MAIN_CFG" ] || {
    echo "ERROR: custom/main.cfg not found - install macros first"
    exit 1
}
[ -f "$OVERRIDES_CFG" ] || {
    echo "ERROR: custom/overrides.cfg not found - install macros first"
    exit 1
}
grep -q '_PLATE_AWARE_MESH' "$CUSTOM_DIR/start_print.cfg" || {
    echo "ERROR: active START_PRINT macros do not support plate-aware meshes."
    echo "       Update this branch and reinstall the macros component first."
    exit 1
}
grep -q '_PLATE_AWARE_MESH' "$CUSTOM_DIR/bed_mesh.cfg" || {
    echo "ERROR: active bed-mesh macros do not support plate-aware meshes."
    echo "       Update this branch and reinstall the macros component first."
    exit 1
}

set -- --config-dir "$CFG_DIR"
if [ -n "${K2_PLATE_SLICERS:-}" ]; then
    set -- "$@" --slicers "$K2_PLATE_SLICERS"
fi
"$PYTHON" "$SCRIPT_DIR/configure_slicers.py" "$@" --check-only

# Existing overrides.cfg files are intentionally preserved. Add only this new
# default when missing, leaving every user value and unrelated section intact.
sh "$SCRIPT_DIR/../../../features/macros/overrides/ensure_bed_mesh_soak.sh" \
    "$OVERRIDES_CFG"

mkdir -p "$CUSTOM_DIR"
ln -sf "$SOURCE" "$TARGET"
"$PYTHON" "$SCRIPT_DIR/../../../scripts/ensure_included.py" \
    "$MAIN_CFG" plate_aware_mesh.cfg
"$PYTHON" "$SCRIPT_DIR/configure_slicers.py" "$@"

echo "I: plate-aware saved mesh selection installed"
echo "I: SURFACE=<name> creates/loads <name>_<bed>c_<chamber>c"
echo "I: omitting SURFACE keeps the existing <bed>c_<chamber>c name"

if [ "$NO_RESTART" -eq 0 ]; then
    sh "$SCRIPT_DIR/../../../scripts/firmware_restart.sh"
fi
