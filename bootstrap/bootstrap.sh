#!/bin/ash
set -e

cd $(dirname $0)
CURDIR=$(pwd)

# Run install script from Entware if needed
if [ -x /opt/bin/opkg ] && [ -x /opt/bin/git ]; then
    echo "I: Entware already installed; skipping Entware install."
else
    echo "I: Installing Entware..."
    sh ./entware/install.sh
fi

mkdir -p /mnt/UDISK/root
cd /mnt/UDISK/root

if [ -d /mnt/UDISK/root/k2-improvements/.git ]; then
    echo "I: k2-improvements already exists; updating existing repo."
    cd /mnt/UDISK/root/k2-improvements
    /opt/bin/git fetch origin
    /opt/bin/git checkout k2-1155-compat
    /opt/bin/git pull --ff-only origin k2-1155-compat
else
    echo "I: Cloning k2-improvements..."
    cd /mnt/UDISK/root
    /opt/bin/git clone -b k2-1155-compat https://github.com/Rcpilot33/k2-1155-Jacob-Fork.git k2-improvements
fi

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
