#!/bin/ash
set -e

cd $(dirname $0)
CURDIR=$(pwd)
REPO_URL="https://github.com/Rcpilot33/k2-improvements.git"
MODEL=$(get_sn_mac.sh model 2>/dev/null) || MODEL=
case "$MODEL" in
    F008) BRANCH="${K2_BRANCH:-main}" ;;
    F012) BRANCH="${K2_BRANCH:-k2-pro-support}" ;;
    *) echo "Unsupported printer model: ${MODEL:-unknown}" >&2; exit 1 ;;
esac

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

# Other branches can still expose the Plus setup menu on a Pro.
if [ "$MODEL" = F012 ] && [ "$BRANCH" != k2-pro-support ]; then
    echo 'K2 Pro bootstrap requires --branch k2-pro-support for the development menu.' >&2
    exit 1
fi

# Run install script from Entware if needed
if [ -x /opt/bin/opkg ] && [ -x /opt/bin/git ]; then
    echo "I: Entware already installed; skipping Entware install."
else
    echo "I: Installing Entware..."
    sh ./entware/install.sh
fi

mkdir -p /mnt/UDISK/root
sh "$CURDIR/repository-refresh.sh" \
    "$REPO_URL" \
    "$BRANCH" \
    /mnt/UDISK/root/k2-improvements \
    /mnt/UDISK/root/.k2-improvements/bootstrap-recovery \
    /opt/bin/git

START_MENU="no"

for ARG in "$@"; do
    case "$ARG" in
        --menu)
            START_MENU="yes"
            ;;
        --no-menu)
            START_MENU="no"
            ;;
    esac
done

if [ "$START_MENU" = "yes" ]; then
    if [ -t 0 ] || [ -t 1 ]; then
        echo ""
        echo "Start the K2 Improvements installer menu after better-root completes? [y/N]"
        printf "> "
        if read ANSWER </dev/tty; then
            case "$ANSWER" in
                y|Y|yes|YES)
                    START_MENU="yes"
                    ;;
                *)
                    START_MENU="no"
                    ;;
            esac
        else
            echo "W: unable to read menu choice; continuing without the menu."
            START_MENU="no"
        fi
    else
        START_MENU="no"
    fi
fi

if [ "$START_MENU" = "yes" ]; then
    export K2_SKIP_BETTER_ROOT_LOGOUT=1
fi

cd "$CURDIR"

# Run install script from better-root
sh ./better-root/install.sh

if [ "$START_MENU" = "yes" ]; then
    export HOME=/mnt/UDISK/root
    export PATH=/opt/bin:/opt/sbin:/mnt/UDISK/root/bin:$PATH

    cd /mnt/UDISK/root/k2-improvements
    sh ./menu.sh
fi
