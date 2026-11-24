#!/bin/sh
# Detect the K2 Plus printer firmware version, or echo "unknown".

detect_installed_firmware() {
    local log="/mnt/UDISK/creality/userdata/log/upgrade-server.log"
    if [ -r "$log" ]; then
        grep -oE 'sys = [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' "$log" | tail -1 | awk '{print $3}'
    fi
}

detect_printer_fw() {
    local v
    v=$(detect_installed_firmware)
    if [ -z "$v" ]; then
        local img=$(ls /mnt/UDISK/creality/upgrade/CR0CN240110C10_ota_img_V*.img 2>/dev/null | tail -1)
        [ -n "$img" ] && v=$(echo "$img" | sed -nE 's/.*_V([0-9.]+)\.img$/\1/p')
    fi

    [ -n "$v" ] && echo "$v" || echo "unknown"
}

# Return success when a dotted numeric firmware version is at least the
# requested minimum. Unknown or malformed versions are never treated as new.
printer_fw_at_least() {
    awk -v current="$1" -v minimum="$2" 'BEGIN {
        current_count = split(current, current_parts, ".")
        minimum_count = split(minimum, minimum_parts, ".")
        count = current_count > minimum_count ? current_count : minimum_count
        for (i = 1; i <= count; i++) {
            current_value = i <= current_count ? current_parts[i] : 0
            minimum_value = i <= minimum_count ? minimum_parts[i] : 0
            if (current_value !~ /^[0-9]+$/ || minimum_value !~ /^[0-9]+$/)
                exit 1
            current_value += 0
            minimum_value += 0
            if (current_value > minimum_value)
                exit 0
            if (current_value < minimum_value)
                exit 1
        }
        exit 0
    }'
}
