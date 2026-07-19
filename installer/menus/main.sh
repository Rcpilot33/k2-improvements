#!/bin/ash
set -e

REPO_DIR="/mnt/UDISK/root/k2-improvements"

clear
echo "========================================"
echo " K2 Improvements Installer"
echo " Firmware 1.1.5.5 Compatibility Branch"
echo "========================================"
echo ""
echo "1) Install Stock Probe / No-Cartographer Setup"
echo "2) Install Cartographer Setup"
echo "Q) Quit"
echo ""

printf "Select an option: "
read CHOICE

case "$CHOICE" in
    1)
        echo ""
        echo "Installing Stock Probe / No-Cartographer Setup..."
        cd "$REPO_DIR"
        sh ./no-carto.sh
        ;;
    2)
        echo ""
        echo "Installing Cartographer Setup..."
        cd "$REPO_DIR"
        sh ./gimme-the-jamin.sh
        ;;
    q|Q)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo "Invalid option."
        exit 1
        ;;
esac