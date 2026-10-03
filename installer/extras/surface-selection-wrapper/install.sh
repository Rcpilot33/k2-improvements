#!/bin/sh
# Install a managed START_PRINT copy with slicer-driven Cartographer model
# selection. The tracked macro source is never modified.

set -eu

SCRIPT_DIR="$(readlink -f "$(dirname "$0")")"
INSTALLER_BASE="${INSTALLER_DIR:-$(readlink -f "$SCRIPT_DIR/../../..")}" # repository root
CFG_DIR="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
TARGET="$CFG_DIR/custom/start_print.cfg"
SOURCE="$SCRIPT_DIR/../../../features/macros/start_print/start_print.cfg"
. "$INSTALLER_BASE/installer/lib/start_print_backups.sh"

# The wrapper calls Cartographer commands and must not be installed on the
# stock PR Touch path.
grep -qE '^\[cartographer\]' "$CFG_DIR/printer.cfg" "$CFG_DIR/custom/"*.cfg 2>/dev/null || {
    echo "ERROR: no [cartographer] section found in printer config."
    echo "       Install Cartographer before adding the plate workflow."
    exit 1
}

[ -e "$TARGET" ] || {
    echo "ERROR: $TARGET not found - install macros first"
    exit 1
}
[ -f "$SOURCE" ] || {
    echo "ERROR: tracked source macro not found: $SOURCE"
    exit 1
}

if ! grep -q 'STATUS_MSG.*MSG="Preheating' "$SOURCE"; then
    echo "ERROR: anchor not found in $SOURCE"
    echo "  expected line containing: STATUS_MSG ... MSG=\"Preheating ...\""
    echo "  upstream macros file may have changed; stopping without modification"
    exit 1
fi

if grep -qE '^[[:space:]]*# === BEGIN surface-selection wrapper' "$SOURCE" &&
   ! grep -qE '^[[:space:]]*# === END surface-selection wrapper' "$SOURCE"; then
    echo "ERROR: incomplete surface-selection wrapper in $SOURCE"
    echo "       restore the tracked source before retrying"
    exit 1
fi

cleanup_managed_start_print_backups "$TARGET" "$SOURCE"
backup_unmanaged_start_print "$TARGET" "$SOURCE" \
    "before-surface-wrapper-$(date +%s)"

# Rebuild from the latest tracked source each time. Dropping any marked block
# from the input keeps this safe if an older checkout already contains one.
awk '
/^[[:space:]]*# === BEGIN surface-selection wrapper/ { dropping=1; next }
/^[[:space:]]*# === END surface-selection wrapper/ { dropping=0; next }
dropping { next }
/STATUS_MSG.*MSG="Preheating/ && !inserted {
    print "  # === BEGIN surface-selection wrapper ==="
    print "  {% set SURFACE = params.SURFACE|default(\047default\047)|lower %}"
    print "  CARTOGRAPHER_SCAN_MODEL LOAD={SURFACE}"
    print "  {% if CARTO_FINAL_Z_MODE == \047touch\047 %}"
    print "    CARTOGRAPHER_TOUCH_MODEL LOAD={SURFACE}"
    print "  {% endif %}"
    print "  # === END surface-selection wrapper ==="
    print ""
    inserted=1
}
{ print }
' "$SOURCE" > "${TARGET}.new"

# Replacing the destination path converts the macro symlink into a regular,
# managed custom file rather than writing through it into the Git checkout.
mv "${TARGET}.new" "$TARGET"

echo "I: managed surface-selection wrapper installed at $TARGET"
echo "I: tracked source left unchanged at $SOURCE"
echo "I: active on next Klipper restart"
