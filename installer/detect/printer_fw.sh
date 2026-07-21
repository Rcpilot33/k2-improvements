#!/bin/sh
# Detect the K2 Plus printer firmware version, or echo "unknown".

detect_printer_fw() {
    local v=""
    local log="/mnt/UDISK/creality/userdata/log/upgrade-server.log"

    if [ -r "$log" ]; then
        v=$(grep -oE 'sys = [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' "$log" | tail -1 | awk '{print $3}')
    fi

    if [ -z "$v" ]; then
        local img=$(ls /mnt/UDISK/creality/upgrade/CR0CN240110C10_ota_img_V*.img 2>/dev/null | tail -1)
        [ -n "$img" ] && v=$(echo "$img" | sed -nE 's/.*_V([0-9.]+)\.img$/\1/p')
    fi

    [ -n "$v" ] && echo "$v" || echo "unknown"
}
