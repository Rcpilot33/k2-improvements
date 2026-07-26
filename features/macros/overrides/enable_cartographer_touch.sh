#!/bin/sh
# Add the user-editable Cartographer Touch defaults to the shared overrides
# file. Preserve an existing section and any user-selected value.

set -eu

CFG="${1:-${HOME}/printer_data/config/custom/overrides.cfg}"

[ -f "$CFG" ] || exit 0

if grep -qE '^[[:space:]]*\[cartographer touch\][[:space:]]*$' "$CFG"; then
    if awk '
        /^[[:space:]]*\[cartographer touch\][[:space:]]*$/ { in_section=1; next }
        in_section && /^[[:space:]]*\[/ { in_section=0 }
        in_section && /^[[:space:]]*max_noisy_samples[[:space:]]*:/ { found=1 }
        END { exit(found ? 0 : 1) }
    ' "$CFG"; then
        exit 0
    fi

    sed -i '/^[[:space:]]*\[cartographer touch\][[:space:]]*$/a max_noisy_samples: 2' "$CFG"
else
    {
        printf '\n[cartographer touch]\n'
        printf 'max_noisy_samples: 2\n'
    } >> "$CFG"
fi

echo "I: ensured Cartographer Touch max_noisy_samples override in $CFG"
