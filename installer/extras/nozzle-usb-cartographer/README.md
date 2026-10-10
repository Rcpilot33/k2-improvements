# JimmyV nozzle-camera replacement

Choose **Optional extras -> JimmyV nozzle-camera replacement** after selecting
a JimmyV mount. The factory nozzle camera must already be removed. This is not
a camera-stream installer and does not configure a 3DO or enclosure camera.

Choose AI-only if Cartographer uses another USB connection. Choose USB power
protection only if Cartographer is physically wired to the switched stock
nozzle-camera connector. This wiring choice is never inferred from the mount.

The option disables only `wasteSwitch`, `flowDetect`, and `flowEmDetect` in
Creality's saved AI preferences. A small Klipper helper clamps waste-camera AI
off at every preference command and blocks its camera capture/detection/test
commands. The enclosure-camera AI switch and other settings remain unchanged.
Use manual flow/pressure-advance calibration: the removed nozzle camera cannot
perform those factory calibrations. Do not re-enable camera calibration in the
screen/slicer. The closed-source application caches preferences; power-cycle
after initial installation so it reloads them. Its UI is not rewritten, and
saved preference protection does not intercept every proprietary camera API.

USB protection retains the original `nozzle_cam_power.sh` beside it as
`.k2-factory` and replaces it with a wrapper that maps both on/off requests to
power-on. The startup hook explicitly depends on `board_init`, and a narrow
managed edit adds that hook to Klipper's existing boot dependencies. Numeric
priorities alone are not sufficient: Tina runs boot scripts in parallel.
Klipper also calls the hook before starting its host and refuses to launch
unless the rail reads on and the Cartographer runtime USB device is detected.
USB enumeration is checked for at most nine seconds at startup, not by a
background worker. No `rc.local` replacement,
polling daemon, USB reset, or unrelated power-rail change is installed.
Whole USB-host shutdown/reset remains a hardware shutdown operation; do not
restart `board_init` or run `usb_host_5v.sh disable` while Klipper is connected.

Refreshes preserve the chosen wiring mode. Removal restores the factory power
script, removes the managed Klipper dependency/preflight and hook/module/config,
and restores only the original
camera flags that are still disabled; it never actively turns the rail off.
Rewire Cartographer to another powered USB port or remove it before restoring
factory camera power management. Switching mounts alone does not remove this
explicit wiring option; remove it here before refitting the stock camera.

The installer requires an idle printer, validates the expected factory AI API
and power-script shape, retains config/preference recovery backups, and uses
the protected Klippy-code restart. No SSH login, password, or remote service
is part of installation. Firmware upgrades may replace the factory wrapper;
reinstall and verify after an upgrade, before homing or printing.

The v2 boot-dependency migration repairs earlier opted-in installations even
when `nozzle-usb-cartographer-protection-v1` is already recorded as completed.
Refresh also turns the rail on and checks USB before the protected restart.

Printer validation still required: cold boot without manual `on`, Cartographer
enumeration/connection before homing, factory `off` request with no USB
disconnect, AI preference requests with `WASTE_SWITCH=1` still reporting zero,
and enclosure-camera AI behavior. Run power-cycle tests only while idle.
