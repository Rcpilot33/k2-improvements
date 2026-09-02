#!/bin/sh
# Switch Cartographer mount offsets without modifying cartographer.cfg.
#
# cartographer.cfg remains the Jamin/default baseline. JimmyV profile values are
# written to custom/overrides.cfg, which is included later and therefore wins.

set -eu

CFG_ROOT="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
PRINTER_CFG="$CFG_ROOT/printer.cfg"
CARTO_CFG="$CFG_ROOT/custom/cartographer.cfg"
OVERRIDES_CFG="$CFG_ROOT/custom/overrides.cfg"

[ -f "$PRINTER_CFG" ] || { echo "ERROR: $PRINTER_CFG not found"; exit 1; }
[ -f "$CARTO_CFG" ] || { echo "ERROR: $CARTO_CFG not found - install Cartographer first"; exit 1; }
[ -f "$OVERRIDES_CFG" ] || { echo "ERROR: $OVERRIDES_CFG not found - install overrides first"; exit 1; }

cfg_value() {
    awk -v wanted_section="$2" -v wanted_key="$3" '
        /^\[/ { section = $0 }
        section == "[" wanted_section "]" && $0 ~ "^[ \t]*" wanted_key "[ \t]*:" {
            line = $0
            sub(/^[^:]*:[ \t]*/, "", line)
            sub(/[ \t]*#.*$/, "", line)
            sub(/[ \t]*$/, "", line)
            print line
            exit
        }
    ' "$1"
}

STOCK_ENDSTOP=$(cfg_value "$PRINTER_CFG" stepper_y position_endstop)
STOCK_MIN=$(cfg_value "$PRINTER_CFG" stepper_y position_min)
CARTO_X=$(cfg_value "$CARTO_CFG" cartographer x_offset)
CARTO_Y=$(cfg_value "$CARTO_CFG" cartographer y_offset)
CARTO_MESH_MIN=$(cfg_value "$CARTO_CFG" bed_mesh mesh_min)
CARTO_MESH_MAX=$(cfg_value "$CARTO_CFG" bed_mesh mesh_max)
CARTO_ENDSTOP=$(cfg_value "$CARTO_CFG" stepper_y position_endstop)
CARTO_MIN=$(cfg_value "$CARTO_CFG" stepper_y position_min)

[ -n "$STOCK_ENDSTOP" ] || {
    echo "ERROR: [stepper_y] position_endstop not found in $PRINTER_CFG"
    exit 1
}
[ -n "$STOCK_MIN" ] || {
    echo "ERROR: [stepper_y] position_min not found in $PRINTER_CFG"
    exit 1
}

CURRENT_Y=$(cfg_value "$OVERRIDES_CFG" cartographer y_offset)
CURRENT_MESH_MIN=$(cfg_value "$OVERRIDES_CFG" bed_mesh mesh_min)
CURRENT_MESH_MAX=$(cfg_value "$OVERRIDES_CFG" bed_mesh mesh_max)

if [ "$CURRENT_Y" = "36" ] && [ "$CURRENT_MESH_MIN" = "5, 36" ] && [ "$CURRENT_MESH_MAX" = "345, 340" ]; then
    CURRENT_PROFILE="JimmyV legacy back-mount"
elif [ "$CURRENT_Y" = "12" ] && [ "$CURRENT_MESH_MIN" = "5, 12" ] && [ "$CURRENT_MESH_MAX" = "345, 340" ]; then
    CURRENT_PROFILE="JimmyV final back-mount without 3DO camera"
elif [ "$CURRENT_Y" = "17" ] && [ "$CURRENT_MESH_MIN" = "5, 17" ] && [ "$CURRENT_MESH_MAX" = "345, 340" ]; then
    CURRENT_PROFILE="JimmyV final back-mount with 3DO camera"
elif [ -z "$CURRENT_Y" ] && [ -z "$CURRENT_MESH_MIN" ] && [ -z "$CURRENT_MESH_MAX" ]; then
    CURRENT_PROFILE="Jamin/default (cartographer.cfg baseline)"
else
    CURRENT_PROFILE="custom/mixed overrides"
fi

echo
echo "=== Cartographer mount setup ==="
echo
echo "Current profile: $CURRENT_PROFILE"
echo
echo "Jamin/default baseline from cartographer.cfg:"
echo "  x_offset:         ${CARTO_X:-not set}"
echo "  y_offset:         ${CARTO_Y:-not set}"
echo "  mesh_min:         ${CARTO_MESH_MIN:-not set}"
echo "  mesh_max:         ${CARTO_MESH_MAX:-not set}"
echo "  position_endstop: ${CARTO_ENDSTOP:-not set}"
echo "  position_min:     ${CARTO_MIN:-not set}"
echo
echo "Stock printer.cfg stepper_y values:"
echo "  position_endstop: $STOCK_ENDSTOP"
echo "  position_min:     $STOCK_MIN"
echo
echo "Pick your mount:"
echo "  1. Jamin/default - remove mount overrides and use cartographer.cfg"
echo "  2. JimmyV legacy UNTESTED       - y=36, mesh=5,36 to 345,340"
echo "  3. JimmyV final no 3DO UNTESTED - y=12, mesh=5,12 to 345,340"
echo "  4. JimmyV final 3DO UNTESTED    - y=17, mesh=5,17 to 345,340"
echo "  5. Custom - enter offsets, mesh limits, and stepper_y source"
echo "  b. Cancel"
echo
printf 'Choose: '
read -r choice

case "$choice" in
    1) PROFILE=jamin; LABEL='Jamin/default' ;;
    2) PROFILE=jimmyv_legacy; LABEL='JimmyV legacy back-mount' ;;
    3) PROFILE=jimmyv_final_12; LABEL='JimmyV final back-mount without 3DO camera' ;;
    4) PROFILE=jimmyv_final_17; LABEL='JimmyV final back-mount with 3DO camera' ;;
    5)
        PROFILE=custom
        LABEL='custom mount'

        CURRENT_X=$(cfg_value "$OVERRIDES_CFG" cartographer x_offset)

        DEFAULT_X="${CURRENT_X:-$CARTO_X}"
        DEFAULT_Y="${CURRENT_Y:-$CARTO_Y}"
        DEFAULT_MESH_MIN="${CURRENT_MESH_MIN:-$CARTO_MESH_MIN}"
        DEFAULT_MESH_MAX="${CURRENT_MESH_MAX:-$CARTO_MESH_MAX}"

        printf '  x_offset (default %s): ' "$DEFAULT_X"
        read -r CUSTOM_X
        CUSTOM_X="${CUSTOM_X:-$DEFAULT_X}"
        printf '  y_offset (default %s): ' "$DEFAULT_Y"
        read -r CUSTOM_Y
        CUSTOM_Y="${CUSTOM_Y:-$DEFAULT_Y}"
        printf '  mesh_min as X, Y (default %s): ' "$DEFAULT_MESH_MIN"
        read -r CUSTOM_MESH_MIN
        CUSTOM_MESH_MIN="${CUSTOM_MESH_MIN:-$DEFAULT_MESH_MIN}"
        printf '  mesh_max as X, Y (default %s): ' "$DEFAULT_MESH_MAX"
        read -r CUSTOM_MESH_MAX
        CUSTOM_MESH_MAX="${CUSTOM_MESH_MAX:-$DEFAULT_MESH_MAX}"

        for value in "$CUSTOM_X" "$CUSTOM_Y"; do
            awk -v value="$value" 'BEGIN {
                if (value !~ /^[-+]?[0-9]+([.][0-9]+)?$/ || value < -100 || value > 100) exit 1
            }' || { echo "ERROR: invalid offset '$value' (expected -100..100)"; exit 1; }
        done
        for value in "$CUSTOM_MESH_MIN" "$CUSTOM_MESH_MAX"; do
            awk -v value="$value" 'BEGIN {
                count = split(value, pair, ",")
                for (i = 1; i <= count; i++) gsub(/^[ \t]+|[ \t]+$/, "", pair[i])
                number = "^[-+]?[0-9]+([.][0-9]+)?$"
                if (count != 2 || pair[1] !~ number || pair[2] !~ number) exit 1
            }' || { echo "ERROR: invalid mesh coordinate '$value' (expected X, Y)"; exit 1; }
        done

        echo "  stepper_y source:"
        echo "    1. Cartographer baseline ($CARTO_ENDSTOP / $CARTO_MIN from cartographer.cfg)"
        echo "    2. Stock printer.cfg ($STOCK_ENDSTOP / $STOCK_MIN)"
        printf '  Choose (default 1): '
        read -r CUSTOM_STEPPER
        CUSTOM_STEPPER="${CUSTOM_STEPPER:-1}"
        case "$CUSTOM_STEPPER" in
            1) CUSTOM_STEPPER=baseline ;;
            2) CUSTOM_STEPPER=stock ;;
            *) echo "ERROR: stepper_y choice must be 1 or 2"; exit 1 ;;
        esac
        ;;
    *) echo "cancelled"; exit 0 ;;
esac

CUSTOM_X="${CUSTOM_X:-}"
CUSTOM_Y="${CUSTOM_Y:-}"
CUSTOM_MESH_MIN="${CUSTOM_MESH_MIN:-}"
CUSTOM_MESH_MAX="${CUSTOM_MESH_MAX:-}"
CUSTOM_STEPPER="${CUSTOM_STEPPER:-baseline}"

NEW_CFG="${OVERRIDES_CFG}.new"
trap 'rm -f "$NEW_CFG"' EXIT HUP INT TERM

awk -v profile="$PROFILE" -v stock_endstop="$STOCK_ENDSTOP" -v stock_min="$STOCK_MIN" \
    -v custom_x="$CUSTOM_X" -v custom_y="$CUSTOM_Y" \
    -v custom_mesh_min="$CUSTOM_MESH_MIN" -v custom_mesh_max="$CUSTOM_MESH_MAX" \
    -v custom_stepper="$CUSTOM_STEPPER" '
function emit_values(section) {
    if (profile == "jamin") return
    if (profile == "jimmyv_legacy" && section == "[cartographer]") {
        print "# cartographer-offset-setup: JimmyV legacy mount"
        print "y_offset: 36"
    } else if (profile == "jimmyv_legacy" && section == "[bed_mesh]") {
        print "# cartographer-offset-setup: JimmyV legacy mount"
        print "mesh_min: 5, 36"
        print "mesh_max: 345, 340"
    } else if (profile == "jimmyv_final_12" && section == "[cartographer]") {
        print "# cartographer-offset-setup: JimmyV final mount without 3DO camera"
        print "y_offset: 12"
    } else if (profile == "jimmyv_final_12" && section == "[bed_mesh]") {
        print "# cartographer-offset-setup: JimmyV final mount without 3DO camera"
        print "mesh_min: 5, 12"
        print "mesh_max: 345, 340"
    } else if (profile == "jimmyv_final_17" && section == "[cartographer]") {
        print "# cartographer-offset-setup: JimmyV final mount with 3DO camera"
        print "y_offset: 17"
    } else if (profile == "jimmyv_final_17" && section == "[bed_mesh]") {
        print "# cartographer-offset-setup: JimmyV final mount with 3DO camera"
        print "mesh_min: 5, 17"
        print "mesh_max: 345, 340"
    } else if ((profile == "jimmyv_legacy" || profile == "jimmyv_final_12" || profile == "jimmyv_final_17") && section == "[stepper_y]") {
        print "# cartographer-offset-setup: restore stock printer.cfg values"
        print "position_endstop: " stock_endstop
        print "position_min: " stock_min
    } else if (profile == "custom" && section == "[cartographer]") {
        print "# cartographer-offset-setup: custom mount"
        print "x_offset: " custom_x
        print "y_offset: " custom_y
    } else if (profile == "custom" && section == "[bed_mesh]") {
        print "# cartographer-offset-setup: custom mount"
        print "mesh_min: " custom_mesh_min
        print "mesh_max: " custom_mesh_max
    } else if (profile == "custom" && custom_stepper == "stock" && section == "[stepper_y]") {
        print "# cartographer-offset-setup: restore stock printer.cfg values"
        print "position_endstop: " stock_endstop
        print "position_min: " stock_min
    }
}
function is_managed_key(section, line) {
    if (section == "[cartographer]" && line ~ /^[ \t]*[xy]_offset[ \t]*:/) return 1
    if (section == "[bed_mesh]" && line ~ /^[ \t]*mesh_(min|max)[ \t]*:/) return 1
    if (section == "[stepper_y]" && line ~ /^[ \t]*position_(endstop|min)[ \t]*:/) return 1
    return 0
}
/^\[/ {
    section = $0
    seen[section] = 1
    print
    emit_values(section)
    next
}
/^[ \t]*#[ \t]*cartographer-offset-setup:/ { next }
is_managed_key(section, $0) { next }
{ print }
END {
    if (profile != "jamin") {
        if (!("[cartographer]" in seen)) {
            print ""
            print "[cartographer]"
            emit_values("[cartographer]")
        }
        if (!("[bed_mesh]" in seen)) {
            print ""
            print "[bed_mesh]"
            emit_values("[bed_mesh]")
        }
        if (!("[stepper_y]" in seen) && (profile == "jimmyv_legacy" || profile == "jimmyv_final_12" || profile == "jimmyv_final_17" || custom_stepper == "stock")) {
            print ""
            print "[stepper_y]"
            emit_values("[stepper_y]")
        }
    }
}
' "$OVERRIDES_CFG" > "$NEW_CFG"

# If a JimmyV profile caused these sections to be created, do not leave empty section
# headers behind when switching back to the baseline profile.
if [ "$PROFILE" = "jamin" ] || { [ "$PROFILE" = "custom" ] && [ "$CUSTOM_STEPPER" = "baseline" ]; }; then
    CLEAN_CFG="${NEW_CFG}.clean"
    awk '
    function flush_section() {
        if (!drop_if_empty || has_content) printf "%s", buffered
        buffered = ""
        drop_if_empty = 0
        has_content = 0
    }
    /^\[/ {
        flush_section()
        drop_if_empty = ($0 == "[cartographer]" || $0 == "[stepper_y]")
        buffered = $0 ORS
        next
    }
    {
        buffered = buffered $0 ORS
        if ($0 !~ /^[ \t]*$/) has_content = 1
    }
    END { flush_section() }
    ' "$NEW_CFG" > "$CLEAN_CFG"
    mv "$CLEAN_CFG" "$NEW_CFG"
fi

if cmp -s "$OVERRIDES_CFG" "$NEW_CFG"; then
    echo "I: $LABEL is already active - no change"
    exit 0
fi

BACKUP="${OVERRIDES_CFG}.before-cartographer-offset-$(date +%s)"
cp "$OVERRIDES_CFG" "$BACKUP"
mv "$NEW_CFG" "$OVERRIDES_CFG"
trap - EXIT HUP INT TERM

# Keep recovery useful without filling custom/ after repeated mount testing.
# The glob is deliberately limited to backups created by this installer.
OLD_BACKUPS=$(ls -1t "${OVERRIDES_CFG}.before-cartographer-offset-"* 2>/dev/null | awk 'NR > 2')
if [ -n "$OLD_BACKUPS" ]; then
    printf '%s\n' "$OLD_BACKUPS" | while IFS= read -r old_backup; do
        if rm -f "$old_backup"; then
            echo "I: removed old backup $old_backup"
        else
            echo "W: could not remove old backup $old_backup"
        fi
    done
fi

echo
echo "I: applied $LABEL"
echo "I: cartographer.cfg was not changed"
echo "I: backup at $BACKUP"
echo "I: active after FIRMWARE_RESTART"
