"""Read-only verification of the two released camera/USB migrations.

Never runs a service, changes GPIO, writes preferences, or acknowledges future
migrations. A failed/missing check keeps the repair recommendation visible.
"""
import json
import os
from pathlib import Path
import re
import sys


def verify(custom, klipper, system, preferences, source=None):
    source=source or Path(__file__).resolve().parent
    try:
        guard=(custom/'k2_nozzle_camera_guard.cfg').read_text()
        if '# k2-improvements: nozzle-camera replacement' not in guard:
            return False
        if '[include k2_nozzle_camera_guard.cfg]' not in (custom/'main.cfg').read_text().splitlines():
            return False
        module='k2_nozzle_camera_guard.py'
        if (klipper/'klippy/extras'/module).read_text() != (source/module).read_text():
            return False
        control=json.loads(preferences.read_text())['ai_control']
        if any(control.get(key) != 0 for key in ('wasteSwitch','flowDetect','flowEmDetect')):
            return False
        if '# usb_power_hold: 0' in guard.splitlines():
            return True
        if '# usb_power_hold: 1' not in guard.splitlines():
            return False
        if not (system/'usr/bin/nozzle_cam_power.sh.k2-factory').is_file():
            return False
        for remote, expected in [('usr/bin/nozzle_cam_power.sh','nozzle-power.sh'),
                                  ('etc/init.d/k2-nozzle-usb','nozzle-usb.init'),
                                  ('etc/rc.d/S53k2-nozzle-usb','nozzle-usb.init')]:
            if (system/remote).read_text() != (source/expected).read_text():
                return False
        service=(system/'etc/init.d/klipper').read_text()
        return bool(re.search(r'^DEPEND=.*[,=]k2-nozzle-usb(?:,|$)',service,re.M)
                    and '    /etc/init.d/k2-nozzle-usb start || return 1' in service.splitlines())
    except (OSError,ValueError,KeyError,TypeError):
        return False


if __name__=='__main__':
    sys.exit(0 if verify(
        Path(os.environ.get('PRINTER_CFG_DIR','/mnt/UDISK/printer_data/config'))/'custom',
        Path(os.environ.get('KLIPPER_DIR','/usr/share/klipper')),
        Path(os.environ.get('K2_SYSTEM_ROOT') or '/'),
        Path(os.environ.get('K2_CAMERA_PREFERENCES','/mnt/UDISK/creality/userdata/config/user_print_refer.json')))
        else 1)
