"""Exercise ATC's live native status and compensation without Klipper hardware."""

import pathlib
import types
import unittest


SOURCE = pathlib.Path(__file__).with_name('axis_twist_compensation.py')
module = types.ModuleType('axis_twist_test')
exec(compile(SOURCE.read_text(encoding='utf-8').replace(
    'from . import manual_probe, bed_mesh, probe', ''), str(SOURCE), 'exec'),
    module.__dict__)


class NativeStatus:
    def __init__(self):
        self.status = {'on_turb': False, 'g28_nacc': 0, 'future_field': 7}
        self.eventtime = None

    def get_status(self, eventtime):
        self.eventtime = eventtime
        return self.status


class StatusTests(unittest.TestCase):
    def make_compensation(self, native=None):
        compensation = module.AxisTwistCompensation.__new__(
            module.AxisTwistCompensation)
        objects = {} if native is None else {'k2_prtouch_axis_twist_status': native}
        compensation.printer = types.SimpleNamespace(
            lookup_object=lambda name, default: objects.get(name, default))
        return compensation

    def test_native_status_changes_are_forwarded_without_mutation(self):
        native = NativeStatus()
        compensation = self.make_compensation(native)
        for index, probing in enumerate((False, True, False)):
            native.status.update(on_turb=probing, g28_nacc=index)
            status = compensation.get_status(12.5 + index)
            self.assertEqual(status, native.status)
            self.assertEqual(native.eventtime, 12.5 + index)
            status['on_turb'] = 'changed by consumer'
            self.assertIs(native.status['on_turb'], probing)

    def test_without_native_probe_does_not_invent_suppression(self):
        self.assertEqual(self.make_compensation().get_status(1.), {})

    def test_status_forwarding_preserves_xy_compensation(self):
        module.bed_mesh = types.SimpleNamespace(
            constrain=lambda value, low, high: max(low, min(value, high)),
            lerp=lambda fraction, start, end: start + fraction * (end - start))
        compensation = self.make_compensation(NativeStatus())
        compensation.z_compensations = [0., .2]
        compensation.zy_compensations = [0., .4]
        compensation.compensation_start_x = compensation.compensation_start_y = 0.
        compensation.compensation_end_x = compensation.compensation_end_y = 100.
        compensation.get_status(1.)
        position = [50., 25., 1.]
        compensation._update_z_compensation_value(position)
        self.assertAlmostEqual(position[2], 1.2)


if __name__ == '__main__':
    unittest.main()
