#!/bin/ash
set -e

cd $(dirname $0)
CURDIR=$(pwd)

# Run install script from entware
sh ./entware/install.sh

mkdir -p /mnt/UDISK/root
cd /mnt/UDISK/root

/opt/bin/git clone -b k2-1155-compat https://github.com/Rcpilot33/k2-1155-Jacob-Fork.git k2-improvements

cd $CURDIR

# Run install script from better-root
sh ./better-root/install.sh