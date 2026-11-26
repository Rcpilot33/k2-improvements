#!/usr/bin/env python3
"""Static safety and installer-wiring checks for the stock nozzle camera."""

import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class NozzleCameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.install = (HERE / "install.sh").read_text(encoding="utf-8")
        cls.control = (HERE / "nozzle-camera.sh").read_text(encoding="utf-8")
        cls.config = (HERE / "nozzle_camera.cfg").read_text(encoding="utf-8")
        cls.readme = (HERE / "README.md").read_text(encoding="utf-8")
        cls.detect = (ROOT / "installer/detect/features.sh").read_text(
            encoding="utf-8"
        )
        cls.menu = (ROOT / "installer/menus/extras.sh").read_text(encoding="utf-8")
        cls.update = (ROOT / "installer/menus/update.sh").read_text(encoding="utf-8")

    def test_targets_only_the_factory_camera(self):
        self.assertIn("/usr/bin/nozzle_cam_power.sh", self.install)
        self.assertIn("/usr/bin/nozzle_cam_power.sh", self.control)
        self.assertIn("/dev/video2", self.control)

    def test_does_not_kill_unrelated_ffmpeg_processes(self):
        self.assertNotIn("killall ffmpeg", self.control)
        self.assertIn("PIDFILE=/var/run/k2-nozzle-camera.pid", self.control)
        self.assertIn('while [ "$attempt" -le 3 ]', self.control)

    def test_stream_allows_fluidd_cross_origin_access(self):
        self.assertIn("Access-Control-Allow-Origin: *", self.control)

    def test_has_manual_controls_and_ten_minute_shutdown(self):
        for command in ("NOZZLE_CAM_ON", "NOZZLE_CAM_OFF", "NOZZLE_CAM_STATUS"):
            self.assertIn("[gcode_macro %s]" % command, self.config)
        self.assertIn("K2_SET_CAMERA_SHUTOFF DURATION=600", self.config)
        self.assertIn("K2_SET_CAMERA_SHUTOFF DURATION=0", self.config)
        self.assertNotIn("UPDATE_DELAYED_GCODE", self.config)

    def test_installer_uses_firmware_aware_paths_and_protected_restart(self):
        self.assertIn('KLIPPER_ROOT="${KLIPPER_DIR:-/usr/share/klipper}"', self.install)
        self.assertIn("klippy_code_restart.sh", self.install)
        self.assertIn("ensure_included.py", self.install)

    def test_optional_extra_is_detectable_and_visible(self):
        self.assertIn("is_nozzle_camera()", self.detect)
        self.assertIn("nozzle-camera|is_nozzle_camera", self.menu)
        self.assertIn("Stock nozzle camera stream", self.menu)
        self.assertIn("2) run_extra_name nozzle-camera", self.menu)

    def test_updater_recognizes_the_new_component(self):
        self.assertIn("nozzle-camera) echo 'Stock nozzle camera stream'", self.update)
        self.assertIn("nozzle-camera) is_nozzle_camera", self.update)
        self.assertRegex(
            self.update,
            r"plate-aware-mesh nozzle-camera(?: [a-z0-9-]+)*; do",
        )

    def test_fluidd_uses_continuous_stream_mode(self):
        self.assertIn("choose **MJPEG Stream**", self.readme)
        self.assertIn("not\nMJPEG Adaptive", self.readme)
        self.assertIn("snapshot field", self.readme)


if __name__ == "__main__":
    unittest.main()
