#!/bin/ash

set -eu

# The stock reset may preserve /mnt/UDISK/root. Completion records belong to
# the installation being reset and must not be inherited by its replacement.
UPDATER_STATE=/mnt/UDISK/root/.k2-improvements/installer-state/updater
case "$UPDATER_STATE" in
    /mnt/UDISK/root/.k2-improvements/installer-state/updater)
        [ ! -d "$UPDATER_STATE" ] || rm -rf -- "$UPDATER_STATE"
        ;;
    *)
        echo "ERROR: unexpected updater state path; refusing reset." >&2
        exit 1
        ;;
esac

echo "Begin Creality factory reset (wipe.sock only)..."

if ! echo "all" | /usr/bin/nc -U /var/run/wipe.sock; then
    echo "" >&2
    echo "============================================================" >&2
    echo "!!! FACTORY RESET FAILED !!!" >&2
    echo "============================================================" >&2
    echo "Creality wipe.sock did not accept the reset request." >&2
    echo "No improved UDISK cleanup was attempted." >&2
    echo "The printer may require manual recovery or a power cycle." >&2
    echo "============================================================" >&2
    exit 1
fi
