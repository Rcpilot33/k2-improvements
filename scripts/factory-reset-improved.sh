#!/bin/ash

set -eu

# the "all" on wipe.sock does NOT fully remove everything
# yes, I know... WHY?!?!?!

MODE="${1:-}"
UDISK_ROOT=/mnt/UDISK

case "$MODE" in
    --dry-run|--run)
        ;;
    *)
        echo "usage: sh factory-reset-improved.sh --dry-run|--run" >&2
        exit 1
        ;;
esac

if [ ! -d "$UDISK_ROOT" ]; then
    echo "ERROR: $UDISK_ROOT does not exist; refusing to continue." >&2
    exit 1
fi

echo "Scanning UDISK directories ..."

# Include both ordinary and hidden top-level entries. The existence and
# directory checks discard unmatched glob patterns, files, and special nodes.
for DIR in "$UDISK_ROOT"/* "$UDISK_ROOT"/.[!.]* "$UDISK_ROOT"/..?*; do
    [ -e "$DIR" ] || continue
    [ -d "$DIR" ] || continue

    case "$DIR" in
        "$UDISK_ROOT/root"|"$UDISK_ROOT/bin")
            echo "KEEP:   $DIR"
            ;;
        "$UDISK_ROOT"/*)
            if [ "$MODE" = "--dry-run" ]; then
                echo "REMOVE: $DIR"
            else
                echo "Removing: $DIR"
                if ! rm -rf "$DIR"; then
                    echo "" >&2
                    echo "============================================================" >&2
                    echo "!!! FACTORY RESET FAILED !!!" >&2
                    echo "============================================================" >&2
                    echo "Could not completely remove: $DIR" >&2
                    echo "The Creality wipe.sock reset was NOT started." >&2
                    echo "Review the removal error above, then retry." >&2
                    echo "============================================================" >&2
                    exit 1
                fi

                if [ -e "$DIR" ]; then
                    echo "" >&2
                    echo "============================================================" >&2
                    echo "!!! FACTORY RESET FAILED !!!" >&2
                    echo "============================================================" >&2
                    echo "Directory still exists after removal: $DIR" >&2
                    echo "The Creality wipe.sock reset was NOT started." >&2
                    echo "Review active services or files, then retry." >&2
                    echo "============================================================" >&2
                    exit 1
                fi
            fi
            ;;
        *)
            echo "ERROR: unexpected path outside $UDISK_ROOT: $DIR" >&2
            exit 1
            ;;
    esac
done

if [ "$MODE" = "--dry-run" ]; then
    echo ""
    echo "Dry run only. Nothing was removed and factory reset was not triggered."
    exit 0
fi

echo ""
echo "Begin factory reset..."
if ! echo "all" | /usr/bin/nc -U /var/run/wipe.sock; then
    echo "" >&2
    echo "============================================================" >&2
    echo "!!! FACTORY RESET FAILED !!!" >&2
    echo "============================================================" >&2
    echo "Creality wipe.sock did not accept the reset request." >&2
    echo "The printer may require manual recovery or a power cycle." >&2
    echo "============================================================" >&2
    exit 1
fi
