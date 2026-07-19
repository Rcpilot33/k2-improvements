#!/bin/ash
set -e

cd $(dirname $0)
CURDIR=$(pwd)

# Run install script from Entware
sh ./entware/install.sh

mkdir -p /mnt/UDISK/root
cd /mnt/UDISK/root

/opt/bin/git clone -b k2-1155-compat https://github.com/Rcpilot33/k2-1155-Jacob-Fork.git k2-improvements

START_MENU="no"

if [ -t 0 ]; then
    echo ""
    echo "Start the K2 Improvements installer menu after better-root completes? [y/N]"
    printf "> "
    read ANSWER

    case "$ANSWER" in
        y|Y|yes|YES)
            START_MENU="yes"
            export K2_SKIP_BETTER_ROOT_LOGOUT=1
            ;;
    esac
fi

cd "$CURDIR"

# Run install script from better-root
sh ./better-root/install.sh

if [ "$START_MENU" = "yes" ]; then
    export HOME=/mnt/UDISK/root
    export PATH=/opt/bin:/opt/sbin:/mnt/UDISK/root/bin:$PATH

    cd /mnt/UDISK/root/k2-improvements
    sh ./installer/menus/main.sh
fi