import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).with_name("k2_cartographer_touchscreen.py")
SPEC = importlib.util.spec_from_file_location("k2_cartographer_touchscreen", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeModel:
    def __init__(self, z_offset):
        self.z_offset = z_offset


class FakeMode:
    def __init__(self, z_offset, homing_time=0.0, has_model=True):
        self.model = FakeModel(z_offset)
        self.last_homing_time = homing_time
        self._has_model = has_model

    def has_model(self):
        return self._has_model

    def get_model(self):
        return self.model


class FakeCartographer:
    def __init__(self):
        self.scan_mode = FakeMode(1.25, homing_time=10.0)
        self.touch_mode = FakeMode(-0.10, homing_time=20.0)


class FakeOrigin:
    def __init__(self, z):
        self.z = z


class FakeGCodeMove:
    def __init__(self, z_offset=0.0):
        self.z_offset = z_offset

    def get_status(self, eventtime):
        del eventtime
        return {"homing_origin": FakeOrigin(self.z_offset)}


class FakeProbe:
    def get_status(self, eventtime):
        return {"name": "cartographer", "eventtime": eventtime}


class FakeGCode:
    def __init__(self):
        self.commands = {}

    def register_command(self, name, callback, desc=None):
        self.commands[name] = (callback, desc)


class FakePrinter:
    def __init__(self, objects):
        self.objects = {"gcode": FakeGCode(), **objects}
        self.handlers = {}

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def register_event_handler(self, event, callback):
        self.handlers[event] = callback


class FakeConfig:
    def __init__(self, printer):
        self.printer = printer

    def get_printer(self):
        return self.printer


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.carto = FakeCartographer()
        self.probe = FakeProbe()
        self.gcode_move = FakeGCodeMove(-0.03)
        self.printer = FakePrinter(
            {
                "cartographer": self.carto,
                "probe": self.probe,
                "gcode_move": self.gcode_move,
            }
        )
        self.compat = MODULE.K2CartographerTouchscreen(FakeConfig(self.printer))
        self.printer.handlers["klippy:ready"]()

    def test_adds_live_offset_without_removing_standard_fields(self):
        status = self.probe.get_status(12.5)
        self.assertEqual(status["name"], "cartographer")
        self.assertEqual(status["eventtime"], 12.5)
        self.assertEqual(status["z_offset"], -0.03)

    def test_status_tracks_fluidd_live_offset_without_commands(self):
        self.assertEqual(self.probe.get_status(0)["z_offset"], -0.03)
        self.gcode_move.z_offset = -0.04
        self.carto.touch_mode.model = FakeModel(-0.13)
        self.assertEqual(self.probe.get_status(1)["z_offset"], -0.04)

    def test_saved_model_change_does_not_change_displayed_live_offset(self):
        self.carto.touch_mode.model = FakeModel(-0.50)
        self.assertEqual(self.probe.get_status(0)["z_offset"], -0.03)

    def test_stays_inactive_without_cartographer(self):
        printer = FakePrinter(
            {"probe": FakeProbe(), "gcode_move": FakeGCodeMove()}
        )
        compat = MODULE.K2CartographerTouchscreen(FakeConfig(printer))
        printer.handlers["klippy:ready"]()
        self.assertFalse(compat.get_status(0)["installed"])

    def test_registers_status_command(self):
        self.assertIn(
            "K2_CARTOGRAPHER_TOUCHSCREEN_STATUS",
            self.printer.objects["gcode"].commands,
        )
        self.assertEqual(self.compat.get_status(0)["z_offset"], -0.03)


if __name__ == "__main__":
    unittest.main()
