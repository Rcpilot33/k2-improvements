#!/bin/ash
set -e

export HOME=/mnt/UDISK/root
export PATH=/opt/bin:/opt/sbin:/mnt/UDISK/root/bin:$PATH

REPO_DIR="/mnt/UDISK/root/k2-improvements"
cd "$REPO_DIR"

pause_menu() {
    echo ""
    printf "Press Enter to return to the menu..."
    read _
}

while true; do
    clear
    echo "========================================"
    echo " K2 Improvements Installer"
    echo " Firmware 1.1.5.5 Compatibility Branch"
    echo "========================================"
    echo ""
    echo "1) Show installed options"
    echo "2) No-Carto Setup"
    echo "3) Cartographer Firmware Flash"
    echo "4) Gimme the Jamin Setup"
    echo "5) R3MEN printer.cfg changes"
    echo "Q) Quit"
    echo ""

    printf "Select an option: "
    read CHOICE

    case "$CHOICE" in
        1)
            echo ""
            echo "Installed option markers:"
            echo ""

            echo "better-init:          $([ -f /tmp/better-init ] && echo installed || echo not installed)"
            echo "skip-setup:           $([ -f /tmp/skip-setup ] && echo installed || echo not installed)"
            echo "moonraker:            $([ -f /tmp/moonraker ] && echo installed || echo not installed)"
            echo "fluidd:               $([ -f /tmp/fluidd ] && echo installed || echo not installed)"
            echo "screws_tilt_adjust:   $([ -f /tmp/screws_tilt_adjust ] && echo installed || echo not installed)"
            echo "abort_homing:         $([ -f /tmp/abort_homing ] && echo installed || echo not installed)"
            echo "bed_mesh macro:       $([ -f /tmp/macros/bed_mesh ] && echo installed || echo not installed)"
            echo "m191 macro:           $([ -f /tmp/macros/m191 ] && echo installed || echo not installed)"
            echo "start_print macro:    $([ -f /tmp/macros/start_print ] && echo installed || echo not installed)"
            echo "overrides macro:      $([ -f /tmp/macros/overrides ] && echo installed || echo not installed)"

            pause_menu
            ;;
        2)
            echo ""
            echo "Installing Stock Probe / No-Cartographer Setup..."
            echo ""
            cd "$REPO_DIR"
            sh ./no-carto.sh
            echo ""
            echo "Stock Probe / No-Cartographer install finished."
            pause_menu
            ;;
        3)
            echo ""
            echo "Flashing Cartographer Firmware..."
            echo ""
            cd "$REPO_DIR"
            python3 ./features/cartographer/firmware/flash.py
            echo ""
            echo "Cartographer firmware flash finished."
            pause_menu
            ;;
        4)
            echo ""
            echo "Installing Cartographer Setup..."
            echo ""
            cd "$REPO_DIR"
            sh ./gimme-the-jamin.sh
            echo ""
            echo "Cartographer install finished."
            pause_menu
            ;;
        5)
            echo ""
            echo "R3MEN printer.cfg changes are not wired in yet."
            echo "This menu option is a placeholder."
            pause_menu
            ;;
        q|Q)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo ""
            echo "Invalid option. Please select 1, 2, 3, 4, 5, or Q."
            pause_menu
            ;;
    esac
done