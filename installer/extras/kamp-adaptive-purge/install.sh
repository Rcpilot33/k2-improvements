#!/bin/ash
#
# Install KAMP (Klipper Adaptive Meshing & Purging) for adaptive line-purge
# on the K2 Plus. Clones upstream KAMP, installs a corrected Line_Purge.cfg
# copy into custom/, drops K2 Plus-tailored settings + an [exclude_object]
# block, and ensures all three are included from custom/main.cfg.
#
# A standalone interactive install shows its complete instructions, then waits
# for Enter before performing the required protected restart. Full setup
# workflows set K2_DEFER_FIRMWARE_RESTART=1 and perform one final restart after
# every selected component has been installed.

set -e

SCRIPT_DIR="$(readlink -f $(dirname $0))"
KAMP_DIR="${HOME}/Klipper-Adaptive-Meshing-Purging"
KAMP_REPO="https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging.git"
OVERRIDES_CFG="${HOME}/printer_data/config/custom/overrides.cfg"

configure_kamp_settings() {
    python3 "${SCRIPT_DIR}/configure_kamp_settings.py" \
        "${SCRIPT_DIR}/kamp_settings.cfg" \
        "${OVERRIDES_CFG}"
}

activate_kamp() {
    restart_script="$1"
    restart_description="$2"

    if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" != "1" ] && [ -t 0 ]; then
        echo ""
        echo "------------------------------------------------------------------"
        echo " WARNING: the restart will stop an active print. Confirm the printer is idle."
        printf " Press Enter to %s and activate KAMP..." "$restart_description"
        read -r _kamp_restart_confirm
    fi

    sh "$restart_script"
}

if [ "${1:-}" = "--configure-only" ]; then
    if [ ! -f ~/printer_data/config/custom/kamp_settings.cfg ]; then
        echo "E: KAMP is not installed; run the complete installer first"
        exit 1
    fi
    configure_kamp_settings
    activate_kamp \
        "${SCRIPT_DIR}/../../../scripts/firmware_restart.sh" \
        "perform the protected firmware restart"
    exit 0
fi

test -d ~/printer_data/config/custom || mkdir -p ~/printer_data/config/custom

# Install the shared, lazy file scanner. Cartographer uses the same status
# object for adaptive meshes; KAMP uses it even on the stock-probe path.
sh "${SCRIPT_DIR}/../../../features/prime_tower/install.sh"

# ------------------------------------------------------------
# 1. Clone or update KAMP at $HOME/Klipper-Adaptive-Meshing-Purging
# ------------------------------------------------------------
if [ -d "${KAMP_DIR}/.git" ]; then
    echo "I: KAMP repo already present at ${KAMP_DIR}, pulling latest"
    git -C "${KAMP_DIR}" pull --ff-only
else
    echo "I: cloning KAMP to ${KAMP_DIR}"
    git clone --depth=1 "${KAMP_REPO}" "${KAMP_DIR}"
fi

# ------------------------------------------------------------
# 2. Install a corrected copy of KAMP's Line_Purge.cfg into custom/
# ------------------------------------------------------------
#
# Upstream currently leaves G10/G11 unquoted in its Jinja assignments and
# retracts before the final string-break move without restoring that filament
# before returning to the slicer. Build a validated local copy so the slicer's
# own retract/travel/unretract sequence starts from a balanced extrusion state.
echo "I: creating K2-compatible Line_Purge.cfg from upstream KAMP"
python3 "${SCRIPT_DIR}/patch_line_purge.py" \
    "${KAMP_DIR}/Configuration/Line_Purge.cfg" \
    ~/printer_data/config/custom/Line_Purge.cfg

# ------------------------------------------------------------
# 3. Drop our K2 Plus-tailored kamp_settings.cfg into custom/
# (NOT a symlink — survives KAMP repo updates intact)
# ------------------------------------------------------------
echo "I: copying kamp_settings.cfg into custom/"
cp -f "${SCRIPT_DIR}/kamp_settings.cfg" \
    ~/printer_data/config/custom/kamp_settings.cfg

# ------------------------------------------------------------
# 4. Drop the [exclude_object] block (required for KAMP)
# ------------------------------------------------------------
# Only ship our own block if no [exclude_object] exists already anywhere
# in the config tree. If user already has one, leave it alone.
if ! grep -rEhq '^\[exclude_object\]' ~/printer_data/config/ 2>/dev/null; then
    echo "I: copying exclude_object.cfg into custom/"
    cp -f "${SCRIPT_DIR}/exclude_object.cfg" \
        ~/printer_data/config/custom/exclude_object.cfg
else
    echo "I: [exclude_object] already defined elsewhere, skipping"
fi

# ------------------------------------------------------------
# 5. Wire all three into custom/main.cfg
# ------------------------------------------------------------
echo "I: ensuring includes in custom/main.cfg"
python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/printer.cfg custom/main.cfg
python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg kamp_settings.cfg
python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg Line_Purge.cfg
if [ -f ~/printer_data/config/custom/exclude_object.cfg ]; then
    python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
        ~/printer_data/config/custom/main.cfg exclude_object.cfg
fi

# ------------------------------------------------------------
# 6. Review and preserve user-facing KAMP settings
# ------------------------------------------------------------
configure_kamp_settings

# Keep overrides.cfg last so user-selected values win over refreshed defaults.
# ensure_included.py inserts future feature includes before this one. Add the
# include only after the settings writer has successfully created the file.
python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
    ~/printer_data/config/custom/main.cfg overrides.cfg

# ------------------------------------------------------------
# 7. Optional: enable Klipper firmware retraction
# ------------------------------------------------------------
# KAMP's LINE_PURGE prefers G10/G11 (firmware retraction) over inline
# G1 E-.5/+.5 fallbacks, and prints a recommendation message at print
# time if firmware retraction is not configured. Offer to add a default
# config here. Skip silently if [firmware_retraction] already exists
# anywhere in the config tree, or if running non-interactively (e.g.
# via menu.sh batch with no controlling terminal).

FW_RETRACT_STATUS="not configured"

if grep -rEhq '^\[firmware_retraction\]' ~/printer_data/config/ 2>/dev/null; then
    echo "I: [firmware_retraction] already configured — skipping"
    FW_RETRACT_STATUS="already configured (left alone)"
elif [ ! -t 0 ]; then
    echo "I: non-interactive run; skipping firmware_retraction prompt"
    echo "I:   to enable later: cp ${SCRIPT_DIR}/firmware_retraction.cfg \\"
    echo "I:                       ~/printer_data/config/custom/ and add to main.cfg"
    FW_RETRACT_STATUS="not configured (run this installer interactively to enable)"
else
    echo ""
    echo "Optional: enable Klipper firmware retraction?"
    echo "  - Silences KAMP's purge-time warning"
    echo "  - Lets G10/G11 work in any macro"
    echo "  - One place to tune retraction length/speed"
    echo "  - Default ships with conservative PLA values (0.5mm @ 35mm/s)"
    echo "  - If you have it set per-filament in the slicer, you can skip this"
    echo ""
    printf "Enable firmware retraction with default values? [y/N] "
    read FW_RETRACT_CHOICE
    case "$FW_RETRACT_CHOICE" in
        y|Y|yes|YES)
            echo "I: copying firmware_retraction.cfg into custom/"
            cp -f "${SCRIPT_DIR}/firmware_retraction.cfg" \
                ~/printer_data/config/custom/firmware_retraction.cfg
            python3 ${SCRIPT_DIR}/../../../scripts/ensure_included.py \
                ~/printer_data/config/custom/main.cfg firmware_retraction.cfg
            FW_RETRACT_STATUS="enabled with PLA defaults — tune in custom/firmware_retraction.cfg"
            ;;
        *)
            echo "I: skipped firmware retraction"
            echo "I:   to enable later: cp ${SCRIPT_DIR}/firmware_retraction.cfg \\"
            echo "I:                       ~/printer_data/config/custom/ and add to main.cfg"
            FW_RETRACT_STATUS="not configured"
            ;;
    esac
fi

# ------------------------------------------------------------
# 8. Done — instructions for the user
# ------------------------------------------------------------
echo ""
echo "=================================================================="
echo " KAMP adaptive line-purge installed."
echo "=================================================================="
echo ""
echo " Firmware retraction: ${FW_RETRACT_STATUS}"
echo ""
echo " IMPORTANT — slicer-side changes are required for KAMP to work."
echo " Without object polygons, the K2 boundary guard warns and safely"
echo " skips by default. The preserved stock-purge fallback setting can"
echo " opt into the original fixed path for this missing-data case only."
echo ""
echo "------------------------------------------------------------------"
if [ "${K2_DEFER_FIRMWARE_RESTART:-0}" = "1" ]; then
    echo " 1. This update or setup workflow will perform one final protected"
    echo "    restart after every selected component has been installed. Wait for"
else
    echo " 1. The installer will prompt for the required protected restart after"
    echo "    these instructions. Wait for"
fi
echo "    the complete Klippy code reload and K2"
echo "    startup sequence. The new prime-tower scanner, [exclude_object], and"
echo "    LINE_PURGE will then be active."
echo ""
echo "------------------------------------------------------------------"
echo " 2. Enable the slicer option that emits object polygons."
echo ""
echo "    KAMP reads EXCLUDE_OBJECT_DEFINE polygons. Without those polygons,"
echo "    LINE_PURGE is skipped."
echo ""
echo "    Creality Print 7.x: Process settings (left panel) -> use the"
echo "                        search box, type 'exclude' -> enable"
echo "                        'Exclude objects' (Others tab in 7.x)."
echo "                        'Label objects' alone is not sufficient."
echo ""
echo "    Orca / OrcaSlicer:  Process tab -> Quality -> Advanced ->"
echo "                        enable 'Label objects' (or 'Use exclude_object')."
echo ""
echo "------------------------------------------------------------------"
echo " 3. Update your slicer's Machine Start G-code."
echo ""
echo "    Creality Print 7.1.1 templates:"
echo "      slicer-templates/creality-start-material-only.gcode"
echo "      slicer-templates/creality-start-material-kamp.gcode"
echo "      slicer-templates/creality-start-material-surface-profiles.gcode"
echo "      slicer-templates/creality-start-material-surface-profiles-kamp.gcode"
echo "      slicer-templates/orca-machine-start.gcode (unverified — bed_type"
echo "                                                strings may differ)"
echo ""
echo "    Choose KAMP only, plate selection only, or both. KAMP templates"
echo "    replace the hardcoded purge with LINE_PURGE after a blocking M109."
echo ""
echo "    On the printer, the templates are at:"
echo "      ${SCRIPT_DIR}/slicer-templates/"
echo ""
echo "    Open the file you need, copy the contents, paste into:"
echo "      Slicer -> printer profile -> Machine G-code -> Machine start"
echo ""
echo "------------------------------------------------------------------"
echo " 4. Verify it took effect."
echo ""
echo "    Slice your test print, then before sending it to the printer:"
echo "      head -100 your-print.gcode | grep -E 'EXCLUDE_OBJECT_DEFINE|LINE_PURGE'"
echo ""
echo "    You should see:"
echo "      - EXCLUDE_OBJECT_DEFINE NAME=... POLYGON=...  (one per object)"
echo "      - LINE_PURGE  (in the start-print block)"
echo ""
echo "    If EXCLUDE_OBJECT_DEFINE is missing -> exclude-object output is OFF."
echo "    If LINE_PURGE is missing -> machine start gcode change didn't save."
echo ""
echo "------------------------------------------------------------------"
echo " 5. Tune (optional)."
echo ""
echo "    Reopen Optional Extras -> KAMP adaptive purge and choose"
echo "    'Review/change settings'. User selections are stored in"
echo "    custom/overrides.cfg and survive future KAMP reinstalls."
echo ""
echo "    Maintained defaults remain in custom/kamp_settings.cfg."
echo ""
echo "------------------------------------------------------------------"
echo " See installer/extras/kamp-adaptive-purge/README.md for the full guide."
echo ""

activate_kamp \
    "${SCRIPT_DIR}/../../../scripts/klippy_code_restart.sh" \
    "reload Klippy and perform the protected firmware restart"
