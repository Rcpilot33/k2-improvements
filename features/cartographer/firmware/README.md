# Cartographer Firmware

A flashing script is included for Cartographer V3 and V4 probes connected to
the K2 Plus by USB. With this repository installed, run:

```sh
python3 /mnt/UDISK/root/k2-improvements/features/cartographer/firmware/flash.py
```

The main installer menu also provides this under **Cartographer tools → Normal
USB/Katapult firmware flash**. Connect only the probe you intend to flash and
follow the prompts. The flasher detects V3 or V4 hardware and offers only the
matching bundled Full and Lite firmware.

### V3 6.1.0 opt-in testing

For V3, options **4 (6.1.0 Full)** and **5 (6.1.0 Lite)** are explicit
testing choices. Enter still selects 5.1.0 Full; option 3 still aborts.
V4 choices are unchanged. Keep 5.1.0 available as the known-working rollback.
This does not change the bundled DFU recovery images.

Before upgrading, back up the printer configuration and calibration models.
After flashing, use the established K2 protected restart procedure before
homing, and redo Scan and Touch calibration for the new firmware. Validate
normal probing, meshing and printing before relying on it for routine use.
The new firmware has not yet been hardware-validated on this K2 setup.

The V3 6.1.0 USB application images (8 KiB bootloader offset, **not** combined
DFU images) come from official `Cartographer3D/cartographer_firmware` commit
`e5c2b17dbe04ec1f747af5d81b2215949a0a9f8e`, directory
`firmware/v2-v3/survey/6.1.0`. They are bundled for offline flashing and their
SHA-256 digests are checked before selection returns to the flash operation:

| Image | SHA-256 |
| --- | --- |
| `CartographerV3_6.1.0_USB_full_8kib_offset.bin` | `450f618396c837932c83b403a76d1bd912c04af68fdb543eb9fc11f1257847b4` |
| `CartographerV3_6.1.0_USB_lite_8kib_offset.bin` | `461cd887cf31aecc0d7ec959d99b6df3901b43e8ad6e326a9a58064a6ca3e262` |

## Bundled DFU recovery

Use DFU recovery only when normal USB/Katapult flashing cannot communicate with
or write to the probe. V3 and V4 both appear as `0483:df11` in true STM32 DFU
mode, so you must select the hardware version manually.

From the installer menu, choose **Cartographer tools → DFU recovery flash**.
The recovery path:

- Uses checksum-verified combined images bundled with this repository
- Does not download firmware while recovering the probe
- Writes both Katapult and Cartographer firmware at `0x08000000`
- Requires the physical DFU pads to put the probe into true DFU mode

Selecting the wrong hardware image requires reflashing the correct image.

> [!NOTE]
> Some Cartographer V3 / Survey boards may fail during a normal USB/Katapult
> write until their bootloader and firmware have been restored. Run the bundled
> V3 DFU recovery first, unplug/replug the probe or power-cycle the printer, and
> then rerun the normal flasher to verify communication. Use
> STM32CubeProgrammer from another computer only if bundled recovery also fails.

Without bootstrap, copy the complete `firmware` directory to the printer so
that the flasher, DFU writer, dependencies, and bundled images remain together.

For the upstream flashing guide, see the
[official Cartographer documentation](https://docs.cartographer3d.com/cartographer-probe/firmware/updating-firmware).
