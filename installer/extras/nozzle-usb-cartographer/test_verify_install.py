import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('verify_usb_install',HERE/'verify_install.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class VerifyInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.custom=root/'config/custom';self.klipper=root/'klipper';self.system=root/'system'
        self.preferences=root/'preferences.json'
        for path in (self.custom,self.klipper/'klippy/extras',self.system/'usr/bin',self.system/'etc/init.d',self.system/'etc/rc.d'):
            path.mkdir(parents=True)
        (self.custom/'main.cfg').write_text('[include k2_nozzle_camera_guard.cfg]\n')
        (self.custom/'k2_nozzle_camera_guard.cfg').write_text('# k2-improvements: nozzle-camera replacement\n# usb_power_hold: 1\n[k2_nozzle_camera_guard]\n')
        shutil.copyfile(HERE/'k2_nozzle_camera_guard.py',self.klipper/'klippy/extras/k2_nozzle_camera_guard.py')
        self.preferences.write_text(json.dumps(dict(ai_control=dict(wasteSwitch=0,flowDetect=0,flowEmDetect=0,enclosure=1))))
        for dest,source in [('usr/bin/nozzle_cam_power.sh','nozzle-power.sh'),('etc/init.d/k2-nozzle-usb','nozzle-usb.init'),('etc/rc.d/S53k2-nozzle-usb','nozzle-usb.init')]:
            shutil.copyfile(HERE/source,self.system/dest)
        (self.system/'usr/bin/nozzle_cam_power.sh.k2-factory').write_text('factory backup')
        (self.system/'etc/init.d/klipper').write_text('DEPEND=fstab,mcu_update,k2-nozzle-usb\n    /etc/init.d/k2-nozzle-usb start || return 1\n')

    def tearDown(self): self.temp.cleanup()

    def verify(self): return module.verify(self.custom,self.klipper,self.system,self.preferences)

    def test_current_install_verified_without_writes(self):
        paths=[p for p in Path(self.temp.name).rglob('*') if p.is_file()]
        before={str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
        self.assertTrue(self.verify())
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})

    def test_broken_install_keeps_repair_visible(self):
        target=self.system/'etc/init.d/klipper'
        target.write_text('DEPEND=fstab,mcu_update\n')
        self.assertFalse(self.verify())

    def test_changed_module_or_preferences_not_accepted(self):
        self.preferences.write_text(json.dumps(dict(ai_control=dict(wasteSwitch=1,flowDetect=0,flowEmDetect=0))))
        self.assertFalse(self.verify())
        self.preferences.write_text(json.dumps(dict(ai_control=dict(wasteSwitch=0,flowDetect=0,flowEmDetect=0))))
        (self.klipper/'klippy/extras/k2_nozzle_camera_guard.py').write_text('old implementation')
        self.assertFalse(self.verify())

    def test_ai_only_does_not_require_power_files(self):
        p=self.custom/'k2_nozzle_camera_guard.cfg'
        p.write_text(p.read_text().replace('usb_power_hold: 1','usb_power_hold: 0'))
        (self.system/'etc/init.d/k2-nozzle-usb').unlink()
        self.assertTrue(self.verify())

    def test_missing_or_bad_metadata_fails_closed(self):
        self.preferences.write_text('{}')
        self.assertFalse(self.verify())
        self.preferences.unlink()
        self.assertFalse(self.verify())
