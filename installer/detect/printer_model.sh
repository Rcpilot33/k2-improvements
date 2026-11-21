#!/bin/sh
# Route the public setup and menu entry points before they modify printer state.
check_installer_model() {
    local model
    model=$(get_sn_mac.sh model 2>/dev/null) || model=
    case "$model" in
        F008) return 0 ;;
        F012)
            if [ "$1" = menu ]; then
                echo 'K2 Pro (F012) read-only diagnostics'
                exec python3 -B "$SCRIPT_DIR/scripts/printer_baseline.py"
            fi
            echo 'K2 Pro (F012). Use menu.sh for read-only diagnostics.' >&2
            return 1 ;;
        *) echo "Unsupported printer model: ${model:-unknown}" >&2; return 1 ;;
    esac
}
