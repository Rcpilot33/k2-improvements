#!/bin/ash
set -e

cd $(dirname $0)
CURDIR=$(pwd)

# Run install script from entware
sh ./entware/install.sh

mkdir -p /mnt/UDISK/root
cd /mnt/UDISK/root
/opt/bin/git clone https://github.com/Jacob10383/k2-improvements.git

cd $CURDIR
# Run install script from better-root
sh ./better-root/install.sh
