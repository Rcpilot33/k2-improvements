#!/bin/ash

set -eu

# the "all" on wipe.sock does NOT fully remove everything
# yes, I know... WHY?!?!?!

MODE="${1:-}"
UDISK_ROOT=/mnt/UDISK
CLEANUP_FAILURES=0

remove_path() {
    rm -rf -- "$1"
}

record_cleanup_failure() {
    CLEANUP_FAILURES=$((CLEANUP_FAILURES + 1))
    echo "W: improved cleanup could not completely remove: $1" >&2
    echo "W: continuing so Creality's wipe.sock reset can finish recovery." >&2
}

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
        "$UDISK_ROOT/creality")
            # Creality services continuously write files below userdata/log.
            # Removing this live tree races those writers and can fail with
            # "Directory not empty". It is stock-owned data, so hand it to
            # Creality's own wipe.sock reset instead of pre-deleting it.
            if [ "$MODE" = "--dry-run" ]; then
                echo "DEFER:  $DIR (active stock data; removed by Creality factory reset)"
            else
                echo "Deferring: $DIR (active stock data; Creality factory reset owns this path)"
            fi
            ;;
        "$UDISK_ROOT"/*)
            if [ "$MODE" = "--dry-run" ]; then
                echo "REMOVE: $DIR"
            else
                echo "Removing: $DIR"
                if ! remove_path "$DIR"; then
                    record_cleanup_failure "$DIR"
                    continue
                fi

                if [ -e "$DIR" ]; then
                    record_cleanup_failure "$DIR"
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
    UPDATER_STATE=/mnt/UDISK/root/.k2-improvements/installer-state/updater
    if [ -d "$UPDATER_STATE" ]; then
        echo "REMOVE: $UPDATER_STATE (installer update-tracker state)"
    fi
    echo ""
    echo "Dry run only. Nothing was removed and factory reset was not triggered."
    exit 0
fi

# /mnt/UDISK/root is intentionally preserved, but update completion records
# describe the installation being removed. Clear only that exact state folder
# so a later install is evaluated as new instead of inheriting stale results.
UPDATER_STATE=/mnt/UDISK/root/.k2-improvements/installer-state/updater
case "$UPDATER_STATE" in
    /mnt/UDISK/root/.k2-improvements/installer-state/updater)
        if [ -d "$UPDATER_STATE" ]; then
            echo "Clearing installer update-tracker state: $UPDATER_STATE"
            if ! remove_path "$UPDATER_STATE" || [ -e "$UPDATER_STATE" ]; then
                record_cleanup_failure "$UPDATER_STATE"
            fi
        fi
        ;;
    *)
        echo "ERROR: unexpected updater state path; refusing reset." >&2
        exit 1
        ;;
esac

if [ "$CLEANUP_FAILURES" -gt 0 ]; then
    echo "" >&2
    echo "============================================================" >&2
    echo "!!! IMPROVED CLEANUP INCOMPLETE !!!" >&2
    echo "============================================================" >&2
    echo "$CLEANUP_FAILURES path(s) could not be completely removed." >&2
    echo "Continuing with the confirmed Creality factory reset." >&2
    echo "Some third-party files may remain afterward." >&2
    echo "============================================================" >&2
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
