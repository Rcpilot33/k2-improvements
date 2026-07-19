#!/bin/ash
set -e

REPO_DIR="/mnt/UDISK/root/k2-improvements"

while true; do
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
            echo ""
            cd "$REPO_DIR"
            sh ./no-carto.sh
            echo ""
            echo "Stock Probe / No-Cartographer install finished."
            echo ""
            printf "Press Enter to return to the menu..."
            read _
            ;;
        2)
            echo ""
            echo "Installing Cartographer Setup..."
            echo ""
            cd "$REPO_DIR"
            sh ./gimme-the-jamin.sh
            echo ""
            echo "Cartographer install finished."
            echo ""
            printf "Press Enter to return to the menu..."
            read _
            ;;
        q|Q)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo ""
            echo "Invalid option. Please select 1, 2, or Q."
            echo ""
            printf "Press Enter to return to the menu..."
            read _
            ;;
    esac
done