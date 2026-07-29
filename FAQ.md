# FAQ

## Can I still use the auto calibrate features?

A: Unfortunately, at this time they are not supported. No.

## I've installed the Fluidd update, but the camera doesn't show up

A: Have you tried using Firefox?  As far as we can tell this is due to an odd interaction between Creality's WebRTC implementation and Chrome based browsers.

## My bed crashes into the bottom! What did you do?

A: This has nothing to do with the K2 improvements.  Sadly, many of us have seen this with the stock 1.1.2.x series firmware.

## Why is the printer homing to the back and erroring? What did you do?

A: See above, this is a bug with the 1.1.2.x firmware.

## My touch screen doesn't show temperatures until I home my printer! What did you do?

A: See above, this is a bug with the 1.1.2.x firmware.

## When I print from the side spool, the printer still acts like I'm using the CFS

A: This is an issue with the k2-improvements.  We suspect it has something to do with the moonraker update and are investigating.

For now an a work around is to remove this line from your machine start g-code when using the side spool:

```raw
T[initial_no_support_extruder]
```

## Fluidd seems to hang at 99% even though the print appears to have finished

A: It apepars that this is an issue with Creality Print not placing a newline at the end of the sliced gcode.

## What should I do if the touchscreen reports XS3002 after reinstalling firmware?

`XS3002` only indicates that Klipper entered an error state; it does not identify
the underlying failure. A printer firmware reinstall may leave persistent
configuration or modified files under `/mnt/UDISK`, so reinstalling or changing
firmware may not clear an incompatible installation.

If SSH is available, inspect the actual error first:

```sh
tail -n 100 /mnt/UDISK/printer_data/logs/klippy.log
grep -nEi "error|unable|include|not found|exception|traceback" \
  /mnt/UDISK/printer_data/logs/klippy.log | tail -n 40
```

One confirmed recovery involved stock `prtouch_v3_wrapper.py` starting against
an incompatible `bed_mesh.py` interface after firmware was reinstalled. The log
contained:

```text
AttributeError: 'BedMeshCalibrate' object has no attribute 'probe_helper'
```

A confirmed recovery followed this sequence:

1. The menu's `factory-reset-improved` workflow was attempted under firmware
   `1.1.5.2`.
2. A live directory removal appears to have failed with a
   `Directory not empty` error. The script stopped before displaying
   `Begin factory reset...`, so `wipe.sock all` was not reached.
3. Firmware `1.1.5.5` was installed without a completed factory wipe.
4. The printer entered XS3002 with the incompatible
   `prtouch_v3_wrapper.py`/`bed_mesh.py` interface shown above.
5. Running the plain Creality reset command under `1.1.5.5` recovered the
   printer:

   ```sh
   echo "all" | /usr/bin/nc -U /var/run/wipe.sock
   ```

This sequence does not establish a cross-firmware reset defect because the
first reset never reached Creality's wipe service. A successful menu reset
displays `Begin factory reset...`, receives `ok`, and then terminates the SSH
session as the printer resets. The menu now reports directory-removal or socket
failures prominently instead of continuing as though the reset was sent.

> [!WARNING]
> The reset is destructive. Back up configuration, macros, meshes, logs,
> calibration data, and anything else you need before running it.

After the reset, complete the entire stock touchscreen setup and self-check.
Confirm that the stock printer and Fluidd reach a ready state before
reinstalling K2 Improvements. Do not restore individual Klipper Python files
unless the log proves that is still necessary and the replacement comes from
the exact matching K2 Plus firmware or a known-good backup from that printer.

## Why did Cartographer keep using the previous or default model after I pressed a plate selector?

A: The `A11` through `A15` buttons select a profile for the shared actions; they
do not load it immediately. After selecting the plate, press
`A23_CARTO_LOAD_SELECTED` to load both its saved Scan and Touch models.

For calibration, select the plate and then press
`A21_CARTO_SCAN_SELECTED` or `A22_CARTO_TOUCH_SELECTED`. The selection resets to
`default` after a Klipper restart.
