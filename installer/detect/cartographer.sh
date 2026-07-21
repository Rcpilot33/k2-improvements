#!/bin/sh
# Detect Cartographer hardware revision (V3/V4) and firmware build without
# changing the probe state. Prefer Moonraker's live MCU data, then fall back to
# Klipper's log when Moonraker or the probe is unavailable.

_detect_carto_version_string() {
    local json="" version="" curl_bin=""

    if command -v curl >/dev/null 2>&1; then
        curl_bin=$(command -v curl)
    elif [ -x /opt/bin/curl ]; then
        curl_bin=/opt/bin/curl
    fi

    if [ -n "$curl_bin" ] && command -v jq >/dev/null 2>&1; then
        json=$("$curl_bin" -fsS --max-time 2 \
            'http://127.0.0.1:7125/printer/objects/query?mcu%20cartographer=' \
            2>/dev/null || true)
        version=$(printf '%s' "$json" | jq -r \
            '.result.status["mcu cartographer"].mcu_version // empty' \
            2>/dev/null || true)
        [ -n "$version" ] && { printf '%s\n' "$version"; return; }
    fi

    local k=/mnt/UDISK/printer_data/logs/klippy.log
    [ -r "$k" ] || return 1
    grep -oE 'CARTOGRAPHER( K1| V[34])? [0-9]+\.[0-9]+\.[0-9]+' "$k" 2>/dev/null | tail -1
}

detect_carto_hw() {
    local version=$(_detect_carto_version_string)
    case "$version" in
        *'CARTOGRAPHER V3'*|*'CARTOGRAPHER K1 5.'*|*'CARTOGRAPHER 5.'*) echo "V3" ;;
        *'CARTOGRAPHER V4'*|*'CARTOGRAPHER 6.'*)                    echo "V4" ;;
        *)                                                          echo "unknown" ;;
    esac
}

detect_carto_fw() {
    local version=$(_detect_carto_version_string)
    local fw=$(printf '%s\n' "$version" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | tail -1)
    [ -n "$fw" ] && echo "$fw" || echo "unknown"
}
