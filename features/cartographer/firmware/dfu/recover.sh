#!/bin/ash
# Cartographer V3/V4 STM32 DFU recovery using bundled combined images.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIRMWARE_DIR="$SCRIPT_DIR/firmware"
DFU_ID="0483:df11"

confirm() {
    printf '%s [y/N]: ' "$1"
    read -r answer
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

dfu_count() {
    command -v lsusb >/dev/null 2>&1 || { echo 0; return; }
    lsusb 2>/dev/null | grep -ic "$DFU_ID"
}

verify_image() {
    command -v sha256sum >/dev/null 2>&1 || {
        echo "E: sha256sum is required to verify the recovery image."
        return 1
    }
    [ -f "$IMAGE" ] || { echo "E: image not found: $IMAGE"; return 1; }
    actual_hash=$(sha256sum "$IMAGE" | awk '{print $1}')
    [ "$actual_hash" = "$EXPECTED_HASH" ] || {
        echo "E: recovery image checksum mismatch."
        echo "   expected: $EXPECTED_HASH"
        echo "   actual:   $actual_hash"
        return 1
    }
}

wait_for_dfu() {
    count=$(dfu_count)
    [ "$count" -eq 1 ] 2>/dev/null && return 0
    echo ""
    echo "Put the Cartographer into true STM32 DFU mode:"
    echo "  1. Connect the Cartographer by USB."
    echo "  2. Bridge and hold the BOOT0 pads."
    echo "  3. Briefly bridge the RESET pads, then release both."
    echo "  4. No probe LEDs should remain lit in DFU mode."
    echo ""
    echo "Expected USB ID: $DFU_ID"
    printf '\nPress Enter after entering DFU mode...'
    read -r _
    count=$(dfu_count)
    [ "$count" -eq 1 ] 2>/dev/null || {
        echo "E: expected exactly one $DFU_ID device; detected $count."
        return 1
    }
}

echo ""
echo "=== Cartographer bundled DFU recovery ==="
echo ""
echo "WARNING: DFU overwrites the probe bootloader and firmware."
echo "Selecting the wrong hardware requires reflashing the correct image."
echo ""
echo "  1. Cartographer V3 - STM32F042"
echo "  2. Cartographer V4 - STM32G431"
echo "  0. Cancel"
echo ""
printf 'Choose hardware [0-2]: '
read -r hardware_choice
case "$hardware_choice" in
    1) HARDWARE="v3"; LABEL="Cartographer V3"; MCU="STM32F042" ;;
    2) HARDWARE="v4"; LABEL="Cartographer V4"; MCU="STM32G431" ;;
    *) exit 0 ;;
esac

echo ""
echo "Selected hardware: $LABEL ($MCU)"
confirm "Confirm the connected probe is $LABEL?" || exit 0
echo ""
echo "  1. Full - recommended for K2 (2x sampling rate)"
echo "  2. Lite - conservative fallback for timing issues"
echo "  0. Cancel"
echo ""
printf 'Choose firmware [0-2]: '
read -r firmware_choice

case "$HARDWARE:$firmware_choice" in
    v3:1)
        VARIANT="Full"
        IMAGE="$FIRMWARE_DIR/V3_5.1.0_USB_full_combined.bin"
        EXPECTED_HASH="192498b341a81bfa28f67b13828ee43bcaeb2ae7460be979a972d3a5af5da98a" ;;
    v3:2)
        VARIANT="Lite"
        IMAGE="$FIRMWARE_DIR/V3_5.1.0_USB_lite_combined.bin"
        EXPECTED_HASH="5aa3c63b74cf3a59fc3c63dcd3203d912264458b693d036566d6217ccecff434" ;;
    v4:1)
        VARIANT="Full"
        IMAGE="$FIRMWARE_DIR/V4_6.0.0_USB_full_combined.bin"
        EXPECTED_HASH="dc0b9e936270590dd18bbae67feab69573c7bcc2fe1658dd46011b2eb5cc06c2" ;;
    v4:2)
        VARIANT="Lite"
        IMAGE="$FIRMWARE_DIR/V4_6.0.0_USB_lite_combined.bin"
        EXPECTED_HASH="fec0c7c54d10b71da32f06b658c5c28ec616701f084334874ffc1c3291a9936c" ;;
    *) exit 0 ;;
esac

verify_image || exit 1
command -v python3 >/dev/null 2>&1 || {
    echo "E: python3 is required; nothing was written."
    exit 1
}

echo ""
echo "Final recovery selection:"
echo "  Hardware : $LABEL ($MCU)"
echo "  Variant  : $VARIANT"
echo "  Image    : $(basename "$IMAGE")"
echo "  Address  : 0x08000000"
echo ""
echo "This writes both Katapult and the tested Cartographer firmware."
confirm "Flash this exact image to $LABEL?" || exit 0
wait_for_dfu || exit 1

echo "I: flashing $(basename "$IMAGE") via STM32 DFU"
if python3 "$SCRIPT_DIR/pydfu.py" --vid 0x0483 --pid 0xdf11 \
        --binary "$IMAGE" --address 0x08000000; then
    echo ""
    echo "I: DFU recovery flash completed successfully."
    echo "Unplug/replug the probe USB cable or power-cycle the printer."
    echo "Then run the normal USB/Katapult flash to verify communication."
else
    echo "E: the Python DFU writer exited non-zero."
    echo "Do not choose the other hardware unless you confirm the probe model."
    exit 1
fi
