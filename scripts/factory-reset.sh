#!/bin/ash

set -eu

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
