#!/bin/sh
# Add the bed-mesh-only soak default to a preserved overrides.cfg when missing.

set -eu

CFG="${1:-${HOME}/printer_data/config/custom/overrides.cfg}"

[ -f "$CFG" ] || {
    echo "ERROR: overrides config not found: $CFG"
    exit 1
}

if grep -q '^[[:space:]]*variable_bed_mesh_soak:' "$CFG"; then
    echo "I: preserving existing variable_bed_mesh_soak in $CFG"
    exit 0
fi

BACKUP="${CFG}.before-bed-mesh-soak-$(date +%s)"
cp -p "$CFG" "$BACKUP"

if ! awk '
BEGIN { in_vars=0; inserted=0 }
/^\[gcode_macro _START_PRINT_VARS\]$/ { in_vars=1 }
in_vars && /^gcode:[[:space:]]*$/ && !inserted {
    print "variable_bed_mesh_soak: 5 # minutes; set to 0 if already heat soaked"
    inserted=1
}
{ print }
END { if (!inserted) exit 1 }
' "$CFG" > "${CFG}.new"; then
    rm -f "${CFG}.new"
    echo "ERROR: could not add variable_bed_mesh_soak to $CFG"
    echo "       backup retained at $BACKUP"
    exit 1
fi

mv "${CFG}.new" "$CFG"
echo "I: added variable_bed_mesh_soak: 5 to $CFG"
echo "I: overrides backup at $BACKUP"
