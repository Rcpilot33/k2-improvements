# Bounded touch-disconnect diagnostic (opt-in, not hardware validated)

This is a temporary Klipper extra, not a normal calibration macro. It tests
one real Cartographer touch-armed homing move using the selected touch model's
threshold, 2 mm/s speed, and 100 mm/s² acceleration. It does not change normal
probing code, trigger timeouts, calibration models, or installer defaults.

It positions Z at 150 and commands an endpoint of Z50 in **native toolhead
coordinates**, with no XY movement. These must represent real nozzle-to-bed
clearances. A wrong Z origin, skipped steps, an object on the bed, or an
obstructed travel window defeats that assumption. Remove prints and verify
the whole travel window independently. Do not use `SET_KINEMATIC_POSITION`,
forced moves, or fake homing to satisfy the preconditions.

The software endpoint is not an independent hardware limit. Keep Emergency
Stop accessible. Do not reach into the machine or disturb moving cables;
disconnect only at an accessible stationary connector.

## Manual installation, printer idle only

After this file is available in the printer's repository checkout, copy
`carto_touch_window_test.py` into the active Klipper `klippy/extras/` directory
as `carto_touch_window_test.py`. Do not overwrite another extra. Add this
section to a loaded configuration file:

```ini
[carto_touch_window_test]
```

Use the established K2 protected host restart procedure. If restart reports
the known motor-initialization error, recover before any homing. This extra
is not installed automatically by the Cartographer refresh.

## Preconditions and operation

1. Finish/cancel all prints. Cool the nozzle below 50°C, target zero. Remove
   the printed part and clear the travel window.
2. With Cartographer connected, accurately home XYZ and load the existing
   touch model. Position XY within its touch boundaries (normally center).
3. Position Z at verified clearance of at least 50 mm. Independently confirm
   that native Z150 through Z50 is physically clear. No offsets or coordinates
   should have been manually redefined after homing.
4. Run `CARTO_TOUCH_WINDOW_TEST CONFIRM=CLEAR_WINDOW` from the console.
5. It first moves to Z150 at 5 mm/s. **Do not disconnect during positioning.**
   After its approach message AND visible approach movement, disconnect at
   the stationary connector. Do not reconnect during the test.
6. Observe actual bed movement. The approach has a fixed Z50 endpoint and
   takes roughly 50 seconds if uninterrupted. Stop with Emergency Stop if
   clearance or behavior is unexpected. Do not wait for a console error as
   proof that physical movement stopped.

When the call returns or raises, this diagnostic deliberately invokes Klipper
shutdown. There is no automatic retract or retry. A communication fault might
prevent the call returning promptly, so shutdown at the end is not the active
move's stopping mechanism. During the move we intentionally retain production
trigger-sync behavior; adding a disconnect-triggered emergency shutdown here
would mask the behavior being tested.

Save `klippy.log` and record physical stopping behavior, approximate elapsed
time after unplugging, and whether it stopped well before Z50. The displayed
commanded Z is not reliable evidence of physical stopping distance after a
homing error. A normal completion or false trigger alone is not a disconnect
test pass. A full-window traversal after unplugging fails the prompt-stop
criterion even though the chosen window should prevent nozzle contact.

After collecting evidence, reconnect, remove the config section and temporary
extra, use the protected restart/recovery process, and rehome before further
motion. Existing calibration models are not modified by this diagnostic.

Unit tests establish bounds and control flow only; they do not certify MCU
timeout propagation, physical stopping distance, or safety on the printer.
