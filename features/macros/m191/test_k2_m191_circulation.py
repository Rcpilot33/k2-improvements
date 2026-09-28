import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "k2_m191_circulation", HERE / "k2_m191_circulation.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FakeGcode:
    def __init__(self):
        self.commands = {}
        self.scripts = []
        self.responses = []

    def register_command(self, name, callback, desc=None):
        self.commands[name] = callback

    def run_script_from_command(self, script):
        self.scripts.append(script)

    def respond_raw(self, message):
        self.responses.append(message)


class FakeSensor:
    def __init__(self, temperatures):
        self.temperatures = list(temperatures)
        self.index = 0

    def get_temp(self, eventtime):
        temperature = self.temperatures[min(self.index, len(self.temperatures) - 1)]
        self.index += 1
        return temperature, 0.0


class FakeTemperatureFan:
    def __init__(self, speed):
        self.speed = speed

    def get_status(self, eventtime):
        return {"speed": self.speed}


class FakeToolhead:
    def get_last_move_time(self):
        return 0.0


class FakeHeaters:
    heaters = {}

    def _get_temp(self, eventtime):
        return "B:105.0 /105.0 T0:140.0 /140.0"


class FakeReactor:
    def __init__(self):
        self.on_pause = None

    def monotonic(self):
        return 0.0

    def pause(self, waketime):
        if self.on_pause is not None:
            self.on_pause()
        return waketime


class FakeFastStop:
    def __init__(self, active=False):
        self.active = active

    def is_cancel_pending(self):
        return self.active


class FakePrinter:
    def __init__(self, sensor):
        self.gcode = FakeGcode()
        self.reactor = FakeReactor()
        self.objects = {
            "gcode": self.gcode,
            "heaters": FakeHeaters(),
            "temperature_sensor chamber_temp": sensor,
            "toolhead": FakeToolhead(),
        }

    def get_reactor(self):
        return self.reactor

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)

    def get_start_args(self):
        return {}

    def is_shutdown(self):
        return False


class FakeConfig:
    def __init__(self, printer):
        self.printer = printer

    def get_printer(self):
        return self.printer


class FakeCommand:
    def __init__(self, **params):
        self.params = params
        self.messages = []

    def get(self, name):
        return self.params[name]

    def get_int(self, name, minval=None, maxval=None):
        value = int(self.params[name])
        if minval is not None and value < minval:
            raise ValueError(name)
        if maxval is not None and value > maxval:
            raise ValueError(name)
        return value

    def get_float(
        self, name, default=None, above=None, minval=None, maxval=None
    ):
        value = float(self.params.get(name, default))
        if above is not None and value <= above:
            raise ValueError(name)
        if minval is not None and value < minval:
            raise ValueError(name)
        if maxval is not None and value > maxval:
            raise ValueError(name)
        return value

    def error(self, message):
        return ValueError(message)

    def respond_info(self, message):
        self.messages.append(message)


class CirculationWaitTests(unittest.TestCase):
    def test_chamber_fan_resync_forces_off_on_then_restores_target(self):
        sensor = FakeSensor([35.0])
        printer = FakePrinter(sensor)
        chamber_fan = FakeTemperatureFan(1.0)
        printer.objects["temperature_fan chamber_fan"] = chamber_fan
        controller = module.K2M191Circulation(FakeConfig(printer))

        def apply_latest_target():
            target = float(printer.gcode.scripts[-1].rsplit("=", 1)[1])
            chamber_fan.speed = 0.0 if target == 80.0 else 1.0

        printer.reactor.on_pause = apply_latest_target
        controller.cmd_chamber_fan_resync(FakeCommand(TARGET=32))

        self.assertEqual(
            printer.gcode.scripts,
            [
                "SET_TEMPERATURE_FAN_TARGET "
                "TEMPERATURE_FAN=chamber_fan TARGET=80.000000",
                "SET_TEMPERATURE_FAN_TARGET "
                "TEMPERATURE_FAN=chamber_fan TARGET=1.000000",
                "SET_TEMPERATURE_FAN_TARGET "
                "TEMPERATURE_FAN=chamber_fan TARGET=32.000000",
            ],
        )

    def test_chamber_fan_resync_restores_target_after_timeout(self):
        sensor = FakeSensor([35.0])
        printer = FakePrinter(sensor)
        printer.objects["temperature_fan chamber_fan"] = FakeTemperatureFan(1.0)
        controller = module.K2M191Circulation(FakeConfig(printer))

        with self.assertRaisesRegex(ValueError, "did not transition off"):
            controller.cmd_chamber_fan_resync(FakeCommand(TARGET=32))

        self.assertEqual(
            printer.gcode.scripts[-1],
            "SET_TEMPERATURE_FAN_TARGET "
            "TEMPERATURE_FAN=chamber_fan TARGET=32.000000",
        )

    def test_chamber_fan_resync_rejects_target_above_configured_maximum(self):
        printer = FakePrinter(FakeSensor([35.0]))
        printer.objects["temperature_fan chamber_fan"] = FakeTemperatureFan(1.0)
        controller = module.K2M191Circulation(FakeConfig(printer))

        with self.assertRaises(ValueError):
            controller.cmd_chamber_fan_resync(FakeCommand(TARGET=81))

        self.assertEqual(printer.gcode.scripts, [])

    def test_cycles_low_high_low_and_stops_when_target_is_reached(self):
        sensor = FakeSensor([20.0, 20.0, 20.0, 20.0, 50.0])
        printer = FakePrinter(sensor)
        controller = module.K2M191Circulation(FakeConfig(printer))
        command = FakeCommand(
            SENSOR="temperature_sensor chamber_temp",
            MINIMUM=50,
            MAXIMUM=55,
            LOW_PWM=38,
            HIGH_PWM=255,
            LOW_SECONDS=2,
            HIGH_SECONDS=1,
            CYCLE_FANS=1,
            REPORT_ID="C",
            REPORT_TARGET=50,
        )

        controller.cmd_wait(command)

        self.assertEqual(
            printer.gcode.scripts,
            [
                "M106 S38\nM106 P2 S38",
                "M106 S255\nM106 P2 S255",
                "M106 S38\nM106 P2 S38",
                "M106 S0\nM106 P2 S0",
            ],
        )
        self.assertEqual(
            command.messages,
            [
                "Bed assist circulation changed to high fan speed",
                "Bed assist circulation changed to low fan speed",
            ],
        )
        self.assertEqual(
            printer.gcode.responses,
            ["B:105.0 /105.0 T0:140.0 /140.0 C:20.0 /50.0"] * 4,
        )

    def test_immediate_target_still_leaves_both_fans_off(self):
        sensor = FakeSensor([50.0])
        printer = FakePrinter(sensor)
        controller = module.K2M191Circulation(FakeConfig(printer))
        command = FakeCommand(
            SENSOR="temperature_sensor chamber_temp",
            MINIMUM=50,
            MAXIMUM=55,
            LOW_PWM=38,
            HIGH_PWM=255,
            LOW_SECONDS=45,
            HIGH_SECONDS=20,
            CYCLE_FANS=1,
            REPORT_ID="C",
            REPORT_TARGET=50,
        )

        controller.cmd_wait(command)

        self.assertEqual(
            printer.gcode.scripts,
            ["M106 S38\nM106 P2 S38", "M106 S0\nM106 P2 S0"],
        )
        self.assertEqual(printer.gcode.responses, [])

    def test_wait_without_circulation_reports_chamber_and_leaves_fans_unchanged(self):
        sensor = FakeSensor([36.3, 55.0])
        printer = FakePrinter(sensor)
        controller = module.K2M191Circulation(FakeConfig(printer))
        command = FakeCommand(
            SENSOR="temperature_sensor chamber_temp",
            MINIMUM=55,
            MAXIMUM=60,
            LOW_PWM=38,
            HIGH_PWM=255,
            LOW_SECONDS=45,
            HIGH_SECONDS=20,
            CYCLE_FANS=0,
            REPORT_ID="C",
            REPORT_TARGET=55,
        )

        controller.cmd_wait(command)

        self.assertEqual(printer.gcode.scripts, [])
        self.assertEqual(
            printer.gcode.responses,
            ["B:105.0 /105.0 T0:140.0 /140.0 C:36.3 /55.0"],
        )

    def test_active_fast_stop_ends_wait_and_turns_off_circulation_fans(self):
        sensor = FakeSensor([20.0])
        printer = FakePrinter(sensor)
        fast_stop = FakeFastStop()
        printer.objects["k2_start_print_fast_stop"] = fast_stop
        printer.reactor.on_pause = lambda: setattr(fast_stop, "active", True)
        controller = module.K2M191Circulation(FakeConfig(printer))
        command = FakeCommand(
            SENSOR="temperature_sensor chamber_temp",
            MINIMUM=50,
            MAXIMUM=55,
            LOW_PWM=38,
            HIGH_PWM=255,
            LOW_SECONDS=45,
            HIGH_SECONDS=20,
            CYCLE_FANS=1,
            REPORT_ID="C",
            REPORT_TARGET=50,
        )

        controller.cmd_wait(command)

        self.assertEqual(
            printer.gcode.scripts,
            ["M106 S38\nM106 P2 S38", "M106 S0\nM106 P2 S0"],
        )
        self.assertEqual(
            command.messages,
            ["Chamber wait stopped by print cancellation"],
        )
        self.assertEqual(
            printer.gcode.responses,
            ["B:105.0 /105.0 T0:140.0 /140.0 C:20.0 /50.0"],
        )

    def test_cancel_flag_cannot_change_wait_without_gated_helper(self):
        sensor = FakeSensor([20.0, 50.0])
        printer = FakePrinter(sensor)
        printer.gcode.cancel_pending = True
        controller = module.K2M191Circulation(FakeConfig(printer))
        command = FakeCommand(
            SENSOR="temperature_sensor chamber_temp",
            MINIMUM=50,
            MAXIMUM=55,
            LOW_PWM=38,
            HIGH_PWM=255,
            LOW_SECONDS=45,
            HIGH_SECONDS=20,
            CYCLE_FANS=0,
            REPORT_ID="C",
            REPORT_TARGET=50,
        )

        controller.cmd_wait(command)

        self.assertEqual(
            printer.gcode.responses,
            ["B:105.0 /105.0 T0:140.0 /140.0 C:20.0 /50.0"],
        )
        self.assertEqual(command.messages, [])


if __name__ == "__main__":
    unittest.main()
