#!/bin/sh
# Remove only this installer's stock-camera extra; never switch off its USB rail.
set -eu
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
. "$REPO_ROOT/scripts/stock_nozzle_camera.sh"
CFG_ROOT="${PRINTER_CFG_DIR:-/mnt/UDISK/printer_data/config}"
CAMERA_CFG="$CFG_ROOT/custom/nozzle_camera.cfg"
MAIN_CFG="$CFG_ROOT/custom/main.cfg"
BIN_LINK="${K2_BIN_DIR:-/mnt/UDISK/bin}/nozzle-camera.sh"
case "${1:-}" in
    ''|--no-restart) ;;
    *) echo "ERROR: usage: uninstall.sh [--no-restart]" >&2; exit 1 ;;
esac
stock_nozzle_camera_present || { echo "I: stock nozzle-camera extra is not installed"; exit 0; }

# Refuse unfamiliar replacements instead of deleting user-owned camera code.
for target in "$CAMERA_CFG" "$BIN_LINK"; do
    [ -e "$target" ] || [ -L "$target" ] || continue
    case "$target" in
        "$CAMERA_CFG") source_file="$SCRIPT_DIR/nozzle_camera.cfg" ;;
        *) source_file="$SCRIPT_DIR/nozzle-camera.sh" ;;
    esac
    if [ -L "$target" ]; then
        case "$(readlink "$target")" in
            */installer/extras/nozzle-camera/$(basename "$source_file")) ;;
            *) echo "ERROR: refusing to remove unfamiliar camera link: $target" >&2; exit 1 ;;
        esac
    elif [ "$target" = "$CAMERA_CFG" ] && stock_camera_private_config "$source_file" | cmp -s "$target" -; then
        :
    elif [ "$target" = "$CAMERA_CFG" ] && ! cmp -s "$target" "$source_file"; then
        # Exact installer copies from before the independent camera timer.
        case "$(sha256sum "$target" | cut -d ' ' -f 1)" in
            48590c65a70ace9ae9fe88a9b9f35d5abfae4d1169b7784eeb5bbccbd32f67ab|\
            1cfdfd46b39d9205cb431aa5d2979b9633f75ab25f7297f5fe58bd3db484b413|\
            9c0dd0385e69d86729e385dffc1b3cfacfef4190990df13e056469672be5c7f3) ;;
            *) echo "ERROR: refusing to remove modified camera file: $target" >&2; exit 1 ;;
        esac
    elif ! cmp -s "$target" "$source_file"; then
        echo "ERROR: refusing to remove modified camera file: $target" >&2
        exit 1
    fi
done

stock_nozzle_camera_require_idle || {
    echo "ERROR: cannot confirm printer is idle; stock camera was not removed" >&2
    exit 1
}

# Cancel the already-loaded timer before removing its config. A partially
# installed extra without loaded macros has no timer to cancel.
objects=$(stock_nozzle_camera_curl -fsS --max-time 3 \
    "${MOONRAKER_URL:-http://127.0.0.1:7125}/printer/objects/list")
printf '%s' "$objects" | grep -q '"objects"' &&
    ! printf '%s' "$objects" | grep -q '"error"' || {
        echo "ERROR: cannot check camera timer state; nothing was removed" >&2
        exit 1
    }
cancel=""
if printf '%s' "$objects" | grep -qi 'delayed_gcode _NOZZLE_CAMERA_AUTO_OFF'; then
    cancel="UPDATE_DELAYED_GCODE ID=_NOZZLE_CAMERA_AUTO_OFF DURATION=0"
elif printf '%s' "$objects" | grep -Eq '"(gcode_shell_command|k2_camera_command) nozzle_camera_off"'; then
    cancel="K2_SET_CAMERA_SHUTOFF DURATION=0"
fi
if [ -n "$cancel" ]; then
    reply=$(stock_nozzle_camera_curl -fsS --max-time 5 -X POST \
        -H 'Content-Type: application/json' \
        -d "{\"script\":\"$cancel\"}" \
        "${MOONRAKER_URL:-http://127.0.0.1:7125}/printer/gcode/script")
    printf '%s' "$reply" | grep -q '"result"' &&
        ! printf '%s' "$reply" | grep -q '"error"' || {
            echo "ERROR: camera auto-off cancellation failed; nothing was removed" >&2
            exit 1
        }
fi
sh "$SCRIPT_DIR/nozzle-camera.sh" stop

stamp=$(date +%s)-$$
if [ -f "$MAIN_CFG" ]; then
    temp=$(mktemp "${MAIN_CFG}.camera-remove.XXXXXX")
    trap 'rm -f "$temp"' EXIT HUP INT TERM
    awk '!/^\[include[[:space:]]+nozzle_camera\.cfg\][[:space:]]*(#.*)?$/' "$MAIN_CFG" > "$temp"
    if ! cmp -s "$MAIN_CFG" "$temp"; then
        cp -p "$MAIN_CFG" "${MAIN_CFG}.before-stock-camera-remove-$stamp"
        # Preserve a shared main.cfg symlink and its file mode.
        cp "$temp" "$MAIN_CFG"
    fi
    rm -f "$temp"
    trap - EXIT HUP INT TERM
fi
for target in "$CAMERA_CFG" "$BIN_LINK"; do
    if [ -e "$target" ] || [ -L "$target" ]; then
        if [ -L "$target" ]; then
            cp -P "$target" "${target}.before-stock-camera-remove-$stamp"
        else
            cp -p "$target" "${target}.before-stock-camera-remove-$stamp"
        fi
        rm -f "$target"
    fi
done
echo "I: removed stock nozzle-camera stream and macros; recovery backups kept beside removed files"
echo "I: USB rail power was not changed; shared shell-command support and ffmpeg were retained"
echo "I: remove any manually added stock-camera entry from Fluidd Settings -> Cameras"
if [ "${1:-}" != --no-restart ]; then
    sh "$REPO_ROOT/scripts/firmware_restart.sh"
fi
