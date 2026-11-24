#!/bin/sh
# Update the installer checkout, replacing it safely when a fast-forward is impossible.

set -eu

REPO_URL="$1"
BRANCH="$2"
INSTALLER_DIR="$3"
RECOVERY_ROOT="$4"
GIT_BIN="${5:-git}"
INSTALLER_PARENT="$(dirname "$INSTALLER_DIR")"

checkout_branch() {
    if "$GIT_BIN" -C "$INSTALLER_DIR" show-ref --verify --quiet "refs/heads/$BRANCH"; then
        "$GIT_BIN" -C "$INSTALLER_DIR" checkout "$BRANCH"
    else
        "$GIT_BIN" -C "$INSTALLER_DIR" checkout -b "$BRANCH" "origin/$BRANCH"
    fi
}

normal_update() {
    "$GIT_BIN" -C "$INSTALLER_DIR" remote set-url origin "$REPO_URL" &&
        "$GIT_BIN" -C "$INSTALLER_DIR" fetch origin "$BRANCH" &&
        checkout_branch &&
        "$GIT_BIN" -C "$INSTALLER_DIR" pull --ff-only origin "$BRANCH"
}

replace_checkout() {
    temporary="$RECOVERY_ROOT/.replacement-checkout"
    pending_backup="$RECOVERY_ROOT/.previous-checkout-pending"
    backup="$RECOVERY_ROOT/previous-checkout"

    mkdir -p "$RECOVERY_ROOT"
    rm -rf "$temporary"
    rm -rf "$pending_backup"

    echo "I: cloning a clean $BRANCH checkout before replacing the existing repository."
    if ! "$GIT_BIN" clone --single-branch --branch "$BRANCH" \
        "$REPO_URL" "$temporary"; then
        rm -rf "$temporary"
        echo "E: clean checkout failed; the existing repository was not changed." >&2
        return 1
    fi

    cd "$INSTALLER_PARENT"
    if ! mv "$INSTALLER_DIR" "$pending_backup"; then
        rm -rf "$temporary"
        echo "E: could not move the existing checkout; nothing was replaced." >&2
        return 1
    fi
    if ! mv "$temporary" "$INSTALLER_DIR"; then
        mv "$pending_backup" "$INSTALLER_DIR" 2>/dev/null || true
        rm -rf "$temporary"
        echo "E: could not activate the clean checkout; the existing checkout was restored." >&2
        return 1
    fi

    # Keep exactly one complete recovery checkout.  The previous backup is not
    # removed until the replacement clone is active, and the new backup keeps
    # its Git metadata so local commits remain recoverable.
    if ! rm -rf "$backup"; then
        echo "E: clean checkout installed, but the previous recovery backup could not be removed." >&2
        echo "E: the displaced checkout remains at $pending_backup" >&2
        return 1
    fi
    if ! mv "$pending_backup" "$backup"; then
        echo "E: clean checkout installed, but the new recovery backup remains at $pending_backup" >&2
        return 1
    fi
    # Remove backups made by the older timestamped recovery implementation.
    # These patterns are confined to the dedicated recovery directory.
    for legacy_backup in "$RECOVERY_ROOT"/files-before-refresh-* \
        "$RECOVERY_ROOT"/.previous-checkout-*; do
        [ -e "$legacy_backup" ] || continue
        rm -rf "$legacy_backup"
    done
    echo "I: previous checkout, including Git history, preserved at $backup"
}

mkdir -p "$INSTALLER_PARENT"

if [ ! -d "$INSTALLER_DIR/.git" ]; then
    if [ -d "$INSTALLER_DIR" ] && [ -n "$(ls -A "$INSTALLER_DIR")" ]; then
        echo "W: checkout metadata is missing; preserving the directory during recovery."
        replace_checkout
        exit 0
    fi
    echo "I: cloning k2-improvements..."
    "$GIT_BIN" clone --single-branch --branch "$BRANCH" "$REPO_URL" "$INSTALLER_DIR"
    exit 0
fi

echo "I: k2-improvements already exists; updating existing repo."
if normal_update; then
    missing=$("$GIT_BIN" -C "$INSTALLER_DIR" ls-files --deleted -- menu.sh bootstrap installer)
    if [ -z "$missing" ]; then exit 0; fi
    echo "W: tracked installer files are missing after the update; recovering the checkout."
fi

echo "W: normal fast-forward update failed; starting bootstrap recovery."
replace_checkout
