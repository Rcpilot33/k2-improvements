# K2 Cartographer Setup

## Firmware

Use the full firmware by default; it has been tested to work well with the new Cartographer plugin and the new USB bridge.

It runs at 2x the sampling rate of K1/lite, so it is generally the better option.

K1/lite is still available as a fallback if you see timing issues (for example TRSYNC errors/timeouts), or if you just want a more conservative setup.

Flashing instructions are available [here](./firmware/README.md).

## Print Mount and spacers for K2

The mount and spacers required for the cartographer installation have been provided by stranula, [here](https://www.printables.com/model/1198696-k2-plus-cartographer-mount-shroud-and-spacers). We recommend printing these at a minimum in PETG, but ABS, ASA or any other high glass transition temp filament is preferred.

The files are provided in the desired printing orientation, use a setting that you are comfortable with for functional parts with reasonable tolerances

## Current installation options for routing the carto USB cable:

Option 1. use a top glass riser like this from [Stranula](https://www.printables.com/model/1093082-k2-plus-cfs-riser-ventilation-and-storage)

Option 2. Route the cable through the gasket in the back of the machine where the PTFE tube exits:

  Step 1: Remove the circled ptfe clip from the back of the machine and disconnect the the ptfe tube going inside the machine.

  ![image](https://github.com/user-attachments/assets/d4c46722-546d-46ac-a046-1106c9abd11c)

  Step 2: Pull the PTFE tube and the rubber gasket from inside the k2 chamber.

 ![image](https://github.com/user-attachments/assets/eff4dc8f-c873-4c33-a054-5e4368c0f09f)

 ![image](https://github.com/user-attachments/assets/2259ba4b-8122-4bf1-89c8-61adad2841f7)

 Step 3: Run the Carto USB cable JST connector from outside of the back of the machine to inside.

 Step 4: Either shove the gasket back in place as best you can or cut a small piece from the bottom left corner of the gasket (facing the back of the machine) to accomodate the cable.

 Step 5: Secure the USB cable to the hotend cable chain with either zip ties or cable chain hooks and ensure enough slack for full movement of the toolhead without and tugging and rubbing on the USB cable.

 Step 6: plug the USB end of the cable into the external usb port and secure to the outside.

 ![image](https://github.com/user-attachments/assets/9e3648f0-b428-4a4d-b647-1a996f420530)

 ![image](https://github.com/user-attachments/assets/3b00fb9d-981c-4f1a-8497-1a4a6e8cef47)

## Calibration

Follow steps 1-6 in the [scan calibration guide](https://docs.cartographer3d.com/cartographer-probe/installation-and-setup/software-configuration/scan-calibration), then complete steps 1-4 in the [touch calibration guide](https://docs.cartographer3d.com/cartographer-probe/installation-and-setup/software-configuration/touch-calibration).

If the optional Cartographer plate workflow is installed, use its shared
selector/action buttons for each physical plate:

1. Select `default`, `textured_pei`, `epoxy`, `high_temp`, or `custom` with
   `A11` through `A15`.
2. Run `A21_CARTO_SCAN_SELECTED`.
3. Run `A22_CARTO_TOUCH_SELECTED`.
4. Run `SAVE_CONFIG`.
5. After Klipper restarts and the printer is power-cycled, select the profile
   again and run `A23_CARTO_LOAD_SELECTED`.

Selection by itself does not load a model. Full button names, fallback
behavior, and validation results are in the
[Cartographer macro guide](../../installer/extras/cartographer-macros/README.md).

Touch calibration chooses and verifies the model's detection threshold and
speed. Its initial `z_offset` is not the final print-tuned Z height. Complete a
first-layer print, adjust live Z as needed, and save that result to establish
the final print Z for the selected Touch model.
