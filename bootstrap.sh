#!/bin/ash
set -e

# One-line installer entry point.
# Downloads the full bootstrap folder to /tmp/bootstrap,
# then runs the internal Jacob-style bootstrap script.

REPO="Rcpilot33/k2-improvements"
BRANCH="${K2_BRANCH:-main}"

EXPECT_BRANCH="no"
for ARG in "$@"; do
    if [ "$EXPECT_BRANCH" = "yes" ]; then
        BRANCH="$ARG"
        EXPECT_BRANCH="no"
        continue
    fi

    case "$ARG" in
        --branch)
            EXPECT_BRANCH="yes"
            ;;
        --branch=*)
            BRANCH="${ARG#--branch=}"
            ;;
    esac
done

if [ "$EXPECT_BRANCH" = "yes" ]; then
    echo "E: --branch requires a branch name." >&2
    exit 2
fi

case "$BRANCH" in
    ""|-*|*[!A-Za-z0-9._/-]*)
        echo "E: invalid branch name: $BRANCH" >&2
        exit 2
        ;;
esac

BASE_URL="https://raw.githubusercontent.com/$REPO/$BRANCH"

BOOTSTRAP_DIR="/tmp/bootstrap"

rm -rf "$BOOTSTRAP_DIR"
mkdir -p "$BOOTSTRAP_DIR/entware" "$BOOTSTRAP_DIR/better-root"

download() {
    SRC="$1"
    DST="$2"

    echo "Downloading $DST"
    python3 - "$SRC" "$DST" <<'PY'
import sys
import urllib.request

src = sys.argv[1]
dst = sys.argv[2]

urllib.request.urlretrieve(src, dst)
PY
}

download "$BASE_URL/bootstrap/bootstrap.sh" "$BOOTSTRAP_DIR/bootstrap.sh"
download "$BASE_URL/bootstrap/entware/install.sh" "$BOOTSTRAP_DIR/entware/install.sh"
download "$BASE_URL/bootstrap/entware/wget-ssl.py" "$BOOTSTRAP_DIR/entware/wget-ssl.py"
download "$BASE_URL/bootstrap/entware/unslung.init" "$BOOTSTRAP_DIR/entware/unslung.init"
download "$BASE_URL/bootstrap/entware/unslung,init" "$BOOTSTRAP_DIR/entware/unslung,init"
download "$BASE_URL/bootstrap/better-root/install.sh" "$BOOTSTRAP_DIR/better-root/install.sh"
download "$BASE_URL/bootstrap/better-root/README.md" "$BOOTSTRAP_DIR/better-root/README.md"

chmod +x "$BOOTSTRAP_DIR/bootstrap.sh"
chmod +x "$BOOTSTRAP_DIR/entware/install.sh"
chmod +x "$BOOTSTRAP_DIR/better-root/install.sh"

cd "$BOOTSTRAP_DIR"
export K2_BRANCH="$BRANCH"
sh ./bootstrap.sh "$@"
