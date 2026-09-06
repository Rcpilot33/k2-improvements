# FAQ

## Can I install this on a Creality K2 Pro or another K2 model?

No. This project supports and has been validated on the **Creality K2 Plus
only**. Its scripts and patches depend on K2 Plus-specific Klipper components,
service paths, homing behavior, motor controllers, and printer configuration.
Do not run the installer on a K2 Pro or any other K2-series printer.

## Can I still use the automatic calibration features?

No. K2 Improvements uses the documented manual calibration, mesh, and tuning
workflows. Do not enable Creality Print's **Print Calibration** option or the
printer's automatic print-calibration workflow when sending a print.

That Creality-controlled pre-print sequence runs before this project's
`START_PRINT`. On firmware `1.1.5.5`, a reproduced 100 C bed request entered a
600-second stabilization period, set the chamber-fan target to 30 C, and later
sent `WAIT_BED_STABLE_END`. K2 Improvements does not provide that command, so
Klipper rejects it after the delay. The fan can also remove chamber heat while
the bed is stabilizing. Disable **Print Calibration**, reslice or resend as
needed, and let `START_PRINT` perform the supported mesh and Cartographer
workflow.

## Fluidd is installed, but the camera does not appear

Older reports found that Firefox could display Creality's WebRTC camera when a
Chromium-based browser could not. This has not been revalidated across the
current browser and firmware combinations, so treat it as a troubleshooting
step rather than a confirmed current limitation.

## I see homing or temperature-display problems on old `1.1.2.x` firmware

Reports of the bed moving into the bottom, homing toward the back, or the
touchscreen withholding temperatures until homing were observed on stock
`1.1.2.x` firmware. Those releases are outside the currently validated firmware
matrix. Use one of the versions listed in [VALIDATION.md](./VALIDATION.md).

## Why can the first homing move after `SAVE_CONFIG` run in the wrong direction?

On affected K2 Plus stock-probe and Cartographer installations, Klipper's
ordinary host-only restart can leave the motor controllers in their previous
runtime state. `FIRMWARE_RESTART` reloads configuration, resets the connected
MCUs, and restores correct homing, but does not reload Python modules already
cached by the Klippy host process.

The shared SAVE_CONFIG protection therefore makes `SAVE_CONFIG` request a
firmware-level restart directly after writing the configuration. This preserves
the normal save operation while including the MCU reset that the K2 Plus needs.
The shared restart helper also waits for the K2 motor-controller startup to
finish after Moonraker first reports Klipper ready. This has been validated on
both the stock PR Touch and Cartographer paths. If the helper reports a failure,
fully power-cycle the printer before attempting to home.

Installers that replace Klippy Python modules use a separate protected helper:
it starts a fresh Klippy process, waits for controller initialization, requests
the required firmware reset, and then performs the same stabilization check.
It permits two attempts normally and three on firmware `1.1.3.13`, where two
consecutive recovery failures have been observed. Never home between those
stages.

## I updated the installer. Are the changes already active?

Not necessarily. `git pull` updates the repository, but it does not reload an
active macro or an already imported Klippy Python module. Rerun the affected
item under **Maintenance and recovery -> Core component installer**, or
reinstall the affected item under **Optional extras**. Then wait for its
protected restart to finish before homing. Macro-only changes need the
firmware restart; Python-backed features such as Cartographer's Klipper patches
or the prime-tower scanner need the protected Klippy host reload and
firmware-reset recovery performed by their installer.

If the updated file is already connected to the printer by its existing
symlink and the commit did not add installation wiring, use **Maintenance and
recovery -> Apply macro or printer-setting updates** for `.cfg` changes or
**Apply Klipper feature-code updates** for Python changes. Reinstall the
component when the update adds an include, module, generated copy, or other
installation step.

## When I print from the side spool, the printer still acts like I am using the CFS

This is a legacy, unconfirmed report. If it still occurs, first verify the
selected filament source and inspect the generated machine-start G-code. As a
diagnostic test, older configurations removed this tool-selection line from a
dedicated side-spool printer profile:

```text
T[initial_no_support_extruder]
```

## Fluidd seems to hang at 99% even though the print appears to have finished

This has been associated with Creality Print not placing a final newline at the
end of the sliced G-code. The print itself may already be complete.

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
