# R3MEN bed thermistor profile

This feature is only for Creality K2 Plus printers with the R3MEN graphite bed installed. Do not use this feature on a stock K2 Plus bed.

## What this feature changes
This feature edits:
/mnt/UDISK/printer_data/config/printer.cfg

It adds the custom R3MEN bed thermistor table:
```ini
[thermistor R3men_bed]
temperature1: 25
resistance1: 100000
temperature2: 97
resistance2: 1385
temperature3: 248
resistance3: 165
```

It updates the `[heater_bed]` section:
```ini
sensor_type: R3men_bed
# sensor_type: EPCOS 100K B57560G104F
max_power: 0.8
```

`max_power: 0.8` limits bed heater output. This is mainly for 110V users, where the lower voltage can require higher current draw. 220V users may not need this limit and can tune/remove it if appropriate for their setup.

## Backup
Before making changes, the installer creates a timestamped backup:
/mnt/UDISK/printer_data/config/printer.cfg.r3men-bed.YYYYMMDD-HHMMSS.bak

## After install
Run:
```gcode
FIRMWARE_RESTART
```

Do not run `SAVE_CONFIG` before restarting Klipper. The installer edits `printer.cfg` directly; `FIRMWARE_RESTART` is needed so Klipper reloads the updated bed heater configuration.

Before heating the bed, confirm that the bed temperature reading is reasonable at room temperature.

## Recommended validation
After `FIRMWARE_RESTART`, confirm the bed temperature still reads normally.

Low-temperature heat test:
```gcode
SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET=40
```

If the bed temperature rises normally and stabilizes, run bed PID calibration before normal printing.

If your printer has the Creality `BEDPID` macro, run:
```gcode
BEDPID
```

Otherwise run:
```gcode
PID_CALIBRATE HEATER=heater_bed TARGET=100
SAVE_CONFIG
```

After Klipper restarts, test the bed at your normal operating temperature before starting a print.