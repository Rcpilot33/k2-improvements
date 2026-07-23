# K2 Plus Bed Flattening Guide

This optional process uses bed-mesh measurements and aluminium tape to reduce
a persistent valley or crown in the K2 Plus bed.

Thanks to [@JaminCollins](https://github.com/jamincollins) and
[@stranula](https://github.com/stranula) for the tools used by this workflow.

> This is a physical modification. Apply tape to the bed beneath the removable
> build plate, never to the printing surface. Proceed at your own risk.

## Before you begin

- Root the printer.
- Install `SCREWS_TILT_CALCULATE` support.
- Heat the bed to at least 60 C and allow it to soak for 10 minutes.
- Create a fresh bed mesh at that temperature.
- Install Python on the computer that will run `bed_leveling.py`.

## Level the bed screws

1. Home the printer.
2. Run `SCREWS_TILT_CALCULATE` in Fluidd.
3. Turn each bed knob in the reported direction. The values are clock
   positions: `00:30` means half a turn.
4. Repeat until the adjustments are approximately `00:00` to `00:05`.

## Configure the analysis script

Copy `bed_leveling.py` to your computer; do not run it on the printer.

1. Enter the bed-mesh values in the section identified near the top of the
   script.
2. Set `tape_thicknesses` to the measured tape thicknesses in millimetres. For
   example:

   ```python
   tape_thicknesses = [0.125, 0.300]
   ```

3. Run the script. It generates layer images showing where each tape layer
   should be placed.

Example output:

![Layer 1](layer_1.png)
![Layer 2](layer_2.png)
![Layer 3](layer_3.png)
![Layer 4](layer_4.png)

## Apply and verify

1. Cut tape strips approximately 41 mm wide and keep every layer flat.
2. Apply the layers to the bed beneath the removable build plate.
3. Reinstall the plate and create a new heat-soaked mesh.
4. Run `SCREWS_TILT_CALCULATE` again.
5. Verify the result with a first-layer test print.
