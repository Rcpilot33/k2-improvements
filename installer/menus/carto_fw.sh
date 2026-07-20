#!/bin/sh
# Cartographer probe firmware tools sub-menu.
#
# Normal firmware flashing uses the bundled flash.py:
#   features/cartographer/firmware/flash.py
#
# flash.py uses the normal USB/Katapult path:
#   - detects Cartographer runtime USB device 1d50:614e
#   - enters Katapult bootloader automatically
#   - detects V3/V4 hardware
#   - presents bundled firmware choices
#   - flashes and verifies
#
# This is excluded from "Install all" because firmware flashing should only be
# done by explicit user choice.
#
# DFU should be used as recovery-only and is not handled by flash.py. True STM32 DFU appears
# as 0483:df11 and requires dfu-util plus manual BOOT0/RESET pad access.

menu_carto_fw() {
    while :; do
        clear
        local usb_state
        usb_state="$(detect_carto_usb_state)"

        printf '\n=== Cartographer firmware tools ===\n\n'
        printf '  USB status : %s\n\n' "${usb_state:-unknown}"

        printf '%s\n' "$(c_yellow 'Firmware flashing is manual/explicit only. It is not part of Install All.')"
        printf '%s\n' "$(c_dim 'Normal flashing uses bundled flash.py and the USB/Katapult path.')"
        printf '%s\n\n' "$(c_dim 'DFU should be used as recovery-only if normal USB/Katapult flashing cannot communicate with the probe.')"

        printf '  1. Show normal USB/Katapult flashing notes\n'
        printf '  2. Launch flash.py using normal USB/Katapult path\n'
        printf '  3. Show DFU recovery notes\n'
        printf '  b. Back\n\n'
        printf 'Choose: '
        read -r c
        case "$c" in
            1) carto_fw_show_katapult_notes ;;
            2) carto_fw_launch ;;
            3) carto_fw_show_dfu_notes ;;
            b|B|q|Q) return ;;
            *) ;;
        esac
    done
}

detect_carto_usb_state() {
    if command -v lsusb >/dev/null 2>&1; then
        if lsusb | grep -qi '1d50:614e'; then
            echo "Cartographer runtime USB detected (1d50:614e)"
            return
        fi

        if lsusb | grep -qi '1d50:6177'; then
            echo "Katapult bootloader detected (1d50:6177)"
            return
        fi

        if lsusb | grep -qi '0483:df11'; then
            echo "STM32 DFU recovery mode detected (0483:df11)"
            return
        fi
    fi

    echo "not detected"
}

carto_fw_show_katapult_notes() {
    clear
    cat <<'EOF'

=== Cartographer normal firmware flash: USB/Katapult ===

This is the normal firmware flashing path for this installer.

The bundled flash.py does not require the Cartographer to be manually placed
into STM32 DFU mode. It starts from the normal Cartographer USB runtime device
or from Katapult bootloader mode.

Expected USB states:

  Normal Cartographer runtime : 1d50:614e
  Katapult bootloader         : 1d50:6177

Tested behavior:

  1. Connect the Cartographer to the K2 by USB.
  2. Launch flash.py from this menu.
  3. flash.py detects the Cartographer runtime USB device.
  4. flash.py enters Katapult bootloader automatically.
  5. flash.py detects V3/V4 hardware.
  6. flash.py presents bundled firmware choices.
  7. flash.py flashes and verifies the selected firmware.
  8. The probe should return to normal runtime mode.

After flashing, verify the probe is visible:

  lsusb | grep -i cartographer

If the probe does not reappear, unplug/replug the Cartographer USB or
power-cycle the printer.

K2 Plus restart note:
After SAVE_CONFIG, FIRMWARE_RESTART, or installer changes that restart Klipper,
power-cycle the printer before the next G28.

EOF
    press_enter
}

carto_fw_show_dfu_notes() {
    clear
    cat <<'EOF'

=== Cartographer DFU recovery notes ===

DFU should be used as recovery-only.

Use DFU only if the normal USB/Katapult flash path cannot communicate with the
probe.

The bundled flash.py does not flash true STM32 DFU mode.

True STM32 DFU appears in lsusb as:

  0483:df11 STMicroelectronics STM Device in DFU Mode

Entering DFU mode requires physical access to the probe BOOT0/RESET pads or
BOOT0/3V3 pads depending on the Cartographer version.

Once the probe is manually placed into DFU mode, the rest of the recovery flash
can be automated with dfu-util, but that is a separate recovery path from
flash.py.

Current status:
  - Normal USB/Katapult flash path: tested
  - DFU recovery flash path: not implemented in this menu yet

EOF
    press_enter
}

carto_fw_launch() {
    local flash_py="$INSTALLER_DIR/features/cartographer/firmware/flash.py"

    if [ ! -f "$flash_py" ]; then
        warn "flash.py not found: $flash_py"
        press_enter
        return
    fi

    clear
    printf '\n%s\n' "$(c_yellow 'Final check — is the Cartographer connected by USB?')"
    printf '  flash.py will detect the probe and enter Katapult bootloader automatically when possible.\n'
    printf '  Only connect one Cartographer or similar Klipper/OpenMoko USB device while flashing.\n\n'

    local usb_state
    usb_state="$(detect_carto_usb_state)"

    printf 'Current USB status: %s\n\n' "$usb_state"

    if [ "$usb_state" = "not detected" ]; then
        warn "No Cartographer USB device detected."
        printf '\n'
        printf 'Connect the Cartographer by USB and try again.\n\n'
        press_enter
        return
    fi

    if ! confirm "Is the Cartographer connected and ready to flash firmware?"; then
        return
    fi

    info "running $flash_py"
    ensure_path

    if python3 "$flash_py"; then
        printf '\n%s\n' "$(c_green 'flash.py exited cleanly.')"
        printf '\n'
        printf 'Verify the probe returned to normal USB runtime mode:\n\n'
        printf '  lsusb | grep -i cartographer\n\n'
        printf 'If the probe does not reappear, unplug/replug the Cartographer USB or power-cycle the printer.\n\n'
        printf 'K2 Plus restart note:\n'
        printf 'After SAVE_CONFIG, FIRMWARE_RESTART, or installer changes that restart Klipper,\n'
        printf 'power-cycle the printer before the next G28.\n\n'
    else
        warn "flash.py exited non-zero"
        printf '\n'
        printf 'Firmware was not flashed or was not verified successfully.\n'
        printf 'Do not continue with Cartographer setup until the firmware flash completes cleanly.\n\n'
        printf 'Check that the Cartographer is connected by USB and try again.\n\n'
    fi

    press_enter
}