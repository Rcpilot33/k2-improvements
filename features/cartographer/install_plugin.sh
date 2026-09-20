#!/bin/sh
# Shared source of truth: use the same repository and branch as Moonraker.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLUGIN_DIR=${1:-/mnt/UDISK/root/cartographer3d-plugin}
PLUGIN_URL=$(sed -n 's/^origin: *//p' "$SCRIPT_DIR/update-manager.cfg" | tr -d '\r')
PLUGIN_BRANCH=$(sed -n 's/^primary_branch: *//p' "$SCRIPT_DIR/update-manager.cfg" | tr -d '\r')
[ -n "$PLUGIN_URL" ] && [ -n "$PLUGIN_BRANCH" ] || exit 1

if [ ! -e "$PLUGIN_DIR" ]; then
    git clone --branch "$PLUGIN_BRANCH" "$PLUGIN_URL" "$PLUGIN_DIR"
    exit 0
fi

# Never remove an existing directory, discard edits, or reset local commits.
[ -d "$PLUGIN_DIR/.git" ] || {
    echo "E: $PLUGIN_DIR is not a plugin Git checkout; move it aside manually." >&2
    exit 1
}
cd "$PLUGIN_DIR"
[ -z "$(git status --porcelain)" ] || {
    echo "E: Cartographer has local changes; preserve them before reinstalling." >&2
    exit 1
}
CURRENT_URL=$(git config --get remote.origin.url)
case "$CURRENT_URL" in
    https://github.com/[Jj]acob10383/cartographer3d-plugin.git|https://github.com/Rcpilot33/cartographer3d-plugin.git) ;;
    *) echo "E: Unrecognized Cartographer origin: $CURRENT_URL" >&2; exit 1 ;;
esac
git fetch "$PLUGIN_URL" "refs/heads/$PLUGIN_BRANCH"
TARGET=$(git rev-parse FETCH_HEAD)
git merge-base --is-ancestor HEAD "$TARGET" || {
    echo "E: Cartographer has divergent commits; refusing to replace them." >&2
    exit 1
}
if git show-ref --verify --quiet "refs/heads/$PLUGIN_BRANCH"; then
    git merge-base --is-ancestor "$PLUGIN_BRANCH" "$TARGET" || {
        echo "E: Local $PLUGIN_BRANCH has divergent commits." >&2
        exit 1
    }
    git checkout "$PLUGIN_BRANCH"
else
    git checkout -b "$PLUGIN_BRANCH"
fi
git merge --ff-only "$TARGET"
git remote set-url origin "$PLUGIN_URL"
git config --replace-all remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git update-ref "refs/remotes/origin/$PLUGIN_BRANCH" "$TARGET"
git branch --set-upstream-to="origin/$PLUGIN_BRANCH" "$PLUGIN_BRANCH"
echo "I: Cartographer plugin ready on $PLUGIN_BRANCH at $TARGET"
