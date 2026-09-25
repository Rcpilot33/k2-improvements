#!/bin/sh

set -e

[ "$#" -eq 1 ] || {
    echo "Usage: $0 PATH" >&2
    exit 2
}

FULLPATH=$(readlink -f "$1") || {
    echo "ERROR: unable to resolve path: $1" >&2
    exit 2
}

[ -n "$FULLPATH" ] || {
    echo "ERROR: resolved path is empty" >&2
    exit 2
}

case "$FULLPATH" in
    /|/bin|/etc|/lib|/sbin|/usr|/var|/overlay|/overlay/*|/mnt|/mnt/*)
        echo "ERROR: refusing unsafe restore target: $FULLPATH" >&2
        exit 2
        ;;
esac

OVERLAY_PATH="/overlay/upper${FULLPATH}"
rm -fr "$FULLPATH"
rm -fr "$OVERLAY_PATH"
mount -o remount /
