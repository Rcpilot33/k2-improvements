#!/bin/sh
# Route the public setup and menu entry points before they modify printer state.
check_installer_model() {
    K2_PRINTER_MODEL=$(get_sn_mac.sh model 2>/dev/null) || K2_PRINTER_MODEL=
    case "$K2_PRINTER_MODEL" in
        F008) return 0 ;;
        F012)
            if [ "$1" = menu ]; then
                return 0
            fi
            echo 'K2 Pro (F012). Use menu.sh to open the installer.' >&2
            return 1 ;;
        *) echo "Unsupported printer model: ${K2_PRINTER_MODEL:-unknown}" >&2; return 1 ;;
    esac
}
