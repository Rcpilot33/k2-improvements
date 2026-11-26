#!/bin/sh
# Read the installed printer firmware version from the upgrade log.

detect_installed_firmware() {
    local log="/mnt/UDISK/creality/userdata/log/upgrade-server.log"
    if [ -r "$log" ]; then
        grep -oE 'sys = [0-9]+(\.[0-9]+){3}[[:alnum:]_.+-]*' "$log" | tail -1 | awk '{print $3}'
    fi
}

detect_printer_fw() {
    local v model
    v=$(detect_installed_firmware)
    if [ -z "$v" ]; then
        model=${K2_PRINTER_MODEL:-$(get_sn_mac.sh model 2>/dev/null)} || model=
        if [ "$model" = F008 ]; then
            local img=$(ls /mnt/UDISK/creality/upgrade/CR0CN240110C10_ota_img_V*.img 2>/dev/null | tail -1)
            [ -n "$img" ] && v=$(echo "$img" | sed -nE 's/.*_V([0-9.]+)\.img$/\1/p')
        fi
    fi

    [ -n "$v" ] && echo "$v" || echo "unknown"
}

# Return success when a dotted numeric firmware version is at least the
# requested minimum. Unknown or malformed versions are never treated as new.
printer_fw_at_least() {
    awk -v current="$1" -v minimum="$2" 'BEGIN {
        if (current !~ /^[0-9]+(\.[0-9]+)*$/ || minimum !~ /^[0-9]+(\.[0-9]+)*$/)
            exit 1
        current_count = split(current, current_parts, ".")
        minimum_count = split(minimum, minimum_parts, ".")
        count = current_count > minimum_count ? current_count : minimum_count
        for (i = 1; i <= count; i++) {
            current_value = i <= current_count ? current_parts[i] : 0
            minimum_value = i <= minimum_count ? minimum_parts[i] : 0
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
