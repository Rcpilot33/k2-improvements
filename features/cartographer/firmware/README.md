# Cartographer Firmware

A flashing script is included for Cartographer V3 and V4 probes connected to
the K2 Plus or K2 Pro by USB. With this repository installed, run:

```sh
python3 /mnt/UDISK/root/k2-improvements/features/cartographer/firmware/flash.py
```

The main installer menu also provides this under **Cartographer tools → Normal
USB/Katapult firmware flash**. Connect only the probe you intend to flash and
follow the prompts. The flasher detects V3 or V4 hardware and offers only the
matching bundled Full and Lite firmware.

### V3 firmware choices

For V3, Enter selects **1 (6.1.0 Full)**, the recommended current firmware.
Option **2 (6.1.0 Lite)** is the current conservative choice for installations
that prefer the lower sampling rate. Options **4 (5.1.0 Full)** and
**5 (5.1.0 Lite)** remain available as legacy rollback choices; option 3
aborts.
This does not change the bundled DFU recovery images.

Before upgrading, back up the printer configuration and calibration models.
After flashing, use the established K2 protected restart procedure before
homing, and redo Scan and Touch calibration for the new firmware. Validate
normal probing, meshing and printing before relying on it for routine use.
V3 6.1.0 Full and Lite completed calibration, repeatability, normal-print,
disconnect, and recovery testing on this K2 setup. This does not establish
compatibility with every printer configuration.

The V3 6.1.0 USB application images (8 KiB bootloader offset, **not** combined
DFU images) come from official `Cartographer3D/cartographer_firmware` commit
`e5c2b17dbe04ec1f747af5d81b2215949a0a9f8e`, directory
`firmware/v2-v3/survey/6.1.0`. They are bundled for offline flashing and their
SHA-256 digests are checked before selection returns to the flash operation:

| Image | SHA-256 |
| --- | --- |
| `CartographerV3_6.1.0_USB_full_8kib_offset.bin` | `450f618396c837932c83b403a76d1bd912c04af68fdb543eb9fc11f1257847b4` |
| `CartographerV3_6.1.0_USB_lite_8kib_offset.bin` | `461cd887cf31aecc0d7ec959d99b6df3901b43e8ad6e326a9a58064a6ca3e262` |

### V4 firmware choices

For V4, Enter selects **1 (6.2.0 Full)**, the recommended current firmware.
Option **2 (6.2.0 Lite)** is the current conservative choice for installations
that prefer the lower sampling rate. Options **4 (6.0.0 Full)** and
**5 (6.0.0 Lite)** remain available as legacy rollback choices; option 3
aborts. All DFU recovery images are unchanged.

Upstream requires plugin 1.6.0 support. Our K2 integration at `8478ed2` already
contains upstream release `6e11435`, including `CARTOGRAPHER_SENSOR_FREQ_DIVISOR`
handling, despite its retained `1.5.0+k2.upstream...` version label.
Before entering USB/Katapult mode, the normal flasher checks the managed plugin
source. If it is missing or fails the audit, it offers to download/fast-forward
only the plugin checkout using the safe plugin installer. This works before
Cartographer setup is installed: it does not enable the probe, write printer
configuration, install Klipper links, or restart services. A fresh checkout can
be prepared before Moonraker is installed; refreshing an existing checkout
requires an idle printer verified through Moonraker. Dirty, divergent, or unrecognized
checkouts are preserved and refused; network or audit failures stop before USB
mode changes. Already-audited checkouts need no download or refresh.

The flasher checks the SHA-256 of the audited plugin's
`/mnt/UDISK/root/cartographer3d-plugin/src/cartographer/mcu/constants.py`
(the same path used by the Klipper shim, normalizing CRLF to
LF): `5d413961b8daa0ae14ed2dbc78688d01c8e5f9421a0b44608c1cc5d1cc47bea1`.
Missing or different code blocks 6.2 selection. This conservative check covers
the required frequency conversion, not every aspect of plugin correctness.
Other plugin locations or future source changes require a fresh audit; the
version label alone is not accepted as proof of compatibility.

Prerequisite errors print the source path and, for a hash mismatch, both hashes
on the normal terminal so the message survives the flasher's alternate-screen
UI. `flash.py --check-plugin` performs only this read-only check; it does not
prepare software, query USB, stop services, or flash. Explicit legacy firmware
file paths do not require the V4 6.2 prerequisite. V4 6.2 `--firmware` paths
still undergo the compatibility check.

A later selection refusal exits Katapult without writing firmware and keeps
the explanation visible until acknowledged. The installer distinguishes that
refusal from an actual write/communication failure: it does not suggest DFU or
request a protected restart. If exiting Katapult fails, it advises unplugging
and reconnecting the probe or power-cycling before continuing. DFU remains a
separate recovery action. Successful flashing uses the protected Klippy host
reload followed by firmware reset, so a prepared plugin cannot leave old Python
modules resident in an existing Cartographer setup. It requires Scan and Touch
recalibration. Installer update tracking reports
these tools as a manual firmware-workflow update, not a component reinstall or
an automatic firmware flash.

The official USB application images below are pinned to firmware repository
commit `e5c2b17dbe04ec1f747af5d81b2215949a0a9f8e`, under
`firmware/v4/firmware/6.2.0`. These are **8 KiB-offset application images**, not
combined bootloader/DFU images. The flasher verifies their SHA-256 before use.

| Image | SHA-256 |
| --- | --- |
| `CartographerV4_6.2.0_USB_full_8kib_offset.bin` | `b0c059dc063ff0f6ae0a4bdaa284073598647c27082d0106771f1a5cf9caf383` |
| `CartographerV4_6.2.0_USB_lite_8kib_offset.bin` | `45d4e6f8b520ecb5412fadb358e15974012e6b9935236bfe612af1bf63a532c4` |

Back up configuration/models before flashing. Afterward, complete the K2
protected firmware restart and recalibrate Scan and Touch. V4 6.2 Full and
Lite completed calibration, repeatability, normal-print, disconnect, and
recovery testing on this K2 setup; V4 6.0 remains available for legacy
rollback. Changing the menu recommendation alone does not flash or restart the
printer.
The installer update tracker reports the new manual firmware choices when the
recorded update changes either 6.2 bundle; it never marks the probe as flashed.

## Legacy USB rollback images

The bundled rollback files match Git blobs at the same upstream commit as the
recommended firmware. The V3 files come from `firmware/v2-v3/survey/5.1.0`.
The V4 rollback files come from `firmware/v4/firmware/6.0.0`. The older
V4 application image in the directory comes from `firmware/v4/firmware/5.1.0`.
The flasher checks these files even when selected by filename.
[Upstream firmware tree](https://github.com/Cartographer3D/cartographer_firmware/tree/e5c2b17dbe04ec1f747af5d81b2215949a0a9f8e/firmware)

| Image | SHA-256 |
|---|---|
| `Cartographer_V4_USB_8kib_offset.bin` | `e44bb359a1ae56e79a3ee3ba1f1564fc949702dab45234ee025ff2cd0ea8e351` |
| `CartographerV4_6.0.0_USB_full_8kib_offset.bin` | `6487e285e1186688cdad51387acf3da6f647a5f6355c0ad576e315cc2307df63` |
| `CartographerV4_6.0.0_USB_lite_8kib_offset.bin` | `efd76b888ef06ea1c3ae2ea6066f1b5f65a9bf65e6b433b9f675ab5b6415cf1e` |
| `Survey_Cartographer_K1_USB_8kib_offset.bin` | `bbe149dfd59512458e07d3b5a4936118d75cd52b0d850e8ad4446482f1e09aee` |
| `Survey_Cartographer_USB_8kib_offset.bin` | `a137f51457ea32601d8882bee437926618ee520b6dee8d709e6b98fe6e938fdb` |

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
