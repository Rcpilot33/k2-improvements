# Stock Nozzle Camera Stream

This optional extra exposes the K2 Plus's factory nozzle/AI camera in Fluidd
without adding a USB camera, camera board, printed mount, or replacement
toolhead part.

The stock `XWF-1080p6` camera is normally powered only during Creality's
first-layer inspection. This extra uses Creality's own
`/usr/bin/nozzle_cam_power.sh` control, releases the factory `cam_sub_app`
process, and serves the camera as a 1280x720, 5 fps MJPEG stream on port 8081.

## Install

Choose **Optional extras -> Stock nozzle camera stream**. The installer:

- verifies that the factory camera power control exists;
- installs `ffmpeg` through Entware if needed;
- installs the Klipper camera macros; and
- reloads Klipper through the protected restart workflow when new Klipper
  code is required.

No aftermarket-camera files from the CampbellFabrications 3DO camera project
are installed.

## Use

Run these commands in the Fluidd console:

```text
NOZZLE_CAM_ON
NOZZLE_CAM_STATUS
NOZZLE_CAM_OFF
```

While the camera is on, open `http://PRINTER_IP:8081/`. To add it to Fluidd,
open **Settings -> Cameras -> Add Camera** and choose **MJPEG Stream** (not
MJPEG Adaptive). Enter `http://PRINTER_IP:8081/` as the stream URL. Fluidd
also requires its snapshot field to contain a URL, even though MJPEG Stream
mode does not use it; enter the same `http://PRINTER_IP:8081/` URL there.

The camera automatically turns off after 10 minutes. Run `NOZZLE_CAM_ON`
again to start another 10-minute viewing period.

## Safety and compatibility

- This supports only the stock K2 Plus nozzle camera.
- All JimmyV Cartographer mounts replace that camera. The optional-extra menu
  and direct installer refuse stock-camera streaming on those profiles.
- Selecting a JimmyV profile removes an installed managed stock-camera extra,
  cancels its automatic shutoff, and stops only its stream. The shared USB rail
  is not switched off. Existing JimmyV installations receive the same cleanup
  through **Update installer / apply updates**.
- Removal keeps recovery backups, shared shell-command support, and ffmpeg.
  Unfamiliar or modified camera files are not automatically deleted. Remove
  any manually added stock-camera entry from Fluidd's camera settings yourself.
- Switching back to Jamin/default makes the extra available again, but does
  not reinstall it automatically. Refit the factory camera before reinstalling.
- This compatibility cleanup does not yet disable Creality's camera-dependent
  AI features or keep the camera USB rail enabled at boot. Those are separate
  requirements when powering Cartographer through that connector.
- The camera LED becomes hot. The 10-minute shutdown is intentional.
- Creality's normal first-layer camera routine remains available when this
  stream is off.
- The script stops only the ffmpeg process recorded for this stream; it does
  not use a global `killall ffmpeg` command.
- The default device is `/dev/video2`, matching the powered factory camera.

## Credit

Adapted for the Rcpilot33 installer from the stock-camera streaming work in
[gmanrally/k2-improvements](https://github.com/gmanrally/k2-improvements/tree/main/features/nozzle-cam),
which continues work from
[CampbellFabrications/k2-improvements](https://github.com/CampbellFabrications/k2-improvements).
