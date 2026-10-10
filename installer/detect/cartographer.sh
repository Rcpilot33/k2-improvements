#!/bin/sh
# Detect Cartographer hardware revision (V3/V4) and firmware build without
# changing the probe state. Prefer Moonraker's live MCU data, then fall back to
# bounded sections of Klipper's log when Moonraker or the probe is unavailable.

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

    local k=${K2_CARTO_VERSION_LOG:-/mnt/UDISK/printer_data/logs/klippy.log}
    [ -r "$k" ] || return 1
    # Scan bytes, not lines: a large MCU dump may be a single enormous line.
    # Seek to the recent tail first, then the startup header where the MCU
    # identification normally appears. Never scan the intervening print log.
    version=$(tail -c 262144 "$k" 2>/dev/null |
        grep -oiE 'CARTOGRAPHER( K1| V[34])? [0-9]+\.[0-9]+\.[0-9]+( lite)?' | tail -1)
    if [ -z "$version" ]; then
        version=$(head -c 262144 "$k" 2>/dev/null |
            grep -oiE 'CARTOGRAPHER( K1| V[34])? [0-9]+\.[0-9]+\.[0-9]+( lite)?' | tail -1)
    fi
    [ -n "$version" ] || return 1
    printf '%s\n' "$version"
}

detect_carto_hw() {
    # Match the firmware's lowercase v directly; do not depend on tr's
    # character-class conversion support on the printer's BusyBox build.
    # Panels pass a single shared lookup, including an empty/unknown result.
    # No argument retains the detector's standalone behavior.
    local version
    if [ "$#" -gt 0 ]; then
        version=$1
    else
        version=$(_detect_carto_version_string || true)
    fi
    case "$version" in
        *'CARTOGRAPHER '[Vv]3*|*'CARTOGRAPHER K1 5.'*|*'CARTOGRAPHER 5.'*) echo "V3" ;;
        *'CARTOGRAPHER '[Vv]4*|*'CARTOGRAPHER 6.'*)                    echo "V4" ;;
        *)                                                          echo "unknown" ;;
    esac
}

detect_carto_fw() {
    local version
    if [ "$#" -gt 0 ]; then
        version=$1
    else
        version=$(_detect_carto_version_string || true)
    fi
    local fw=$(printf '%s\n' "$version" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | tail -1)
    [ -n "$fw" ] || { echo "unknown"; return; }
    case "$version" in
        *[Ll][Ii][Tt][Ee]*|*'CARTOGRAPHER K1 '*) echo "$fw (Lite)" ;;
        *CARTOGRAPHER*) echo "$fw (Full)" ;;
        *) echo "$fw" ;;
    esac
}
