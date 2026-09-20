"""Run the reconnect/ADC ordering with production methods and fake hardware."""
import ast
import logging
import math
from pathlib import Path
import unittest
from unittest.mock import Mock

PATCHES = Path(__file__).with_name("patches")


def load_class(filename, name, methods=None):
    tree = ast.parse((PATCHES / filename).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    if methods is not None:
        node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in methods]
    module = ast.Module(body=[node], type_ignores=[])
    namespace = dict(logging=logging, math=math, SAMPLE_TIME=.001, SAMPLE_COUNT=8,
                     REPORT_TIME=.3, RANGE_CHECK_COUNT=4)
    exec(compile(module, filename, "exec"), namespace)
    return namespace[name]


class TemperatureReconnectTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.handlers = {}
        self.callbacks = []
        self.commands = []
        self.mcu = Mock()
        self.mcu.is_non_critical = True
        self.mcu.non_critical_disconnected = True
        self.mcu.get_name.return_value = "cartographer"
        self.mcu.get_constants.return_value = {"MCU": "stm32f042x6"}
        self.mcu.get_constant_float.return_value = 4095.
        self.mcu.create_oid.return_value = 0
        self.mcu.get_query_slot.return_value = 100
        self.mcu.seconds_to_clock.side_effect = lambda value: int(value * 48000000)
        self.mcu.register_config_callback.side_effect = self.callbacks.append
        self.mcu.add_config_cmd.side_effect = lambda cmd, **kw: self.commands.append(cmd)
        query = self.mcu.lookup_query_command.return_value
        query.send.side_effect = lambda args: {"val": 1800 if args[1] == 0x1FFFF7B8 else 1300}
        adc_class = load_class("mcu.py", "MCU_adc")
        self.adc = adc_class(self.mcu, {"pin": "ADC_TEMPERATURE"})
        printer = Mock()
        printer.get_start_args.return_value = {}
        printer.lookup_object.return_value.setup_pin.return_value = self.adc
        printer.register_event_handler.side_effect = self.handlers.__setitem__
        config = Mock()
        config.get_printer.return_value = printer
        config.get.side_effect = lambda key, default=None: "cartographer" if key == "sensor_mcu" else default
        config.getfloat.side_effect = lambda key, default=None, **kw: default
        sensor_class = load_class("temperature_mcu.py", "PrinterTemperatureMCU")
        self.sensor = sensor_class(config)
        self.sensor.setup_minmax(0, 105)
        self.sensor.setup_callback(Mock())
        self.mcu._name = "cartographer"
        self.mcu._get_status_info = {}
        self.mcu._non_critical_reconnect_event_name = "non_critical_mcu_cartographer:reconnected"
        self.mcu._mcu_identify.return_value = True
        self.mcu._printer = printer
        printer.send_event.side_effect = self.event
        self.mcu._connect.side_effect = self.configure
        self.reconnect = load_class("mcu.py", "MCU", {"recon_mcu"}).recon_mcu

    def event(self, name):
        self.events.append(name)
        if name in self.handlers:
            self.handlers[name]()

    def configure(self):
        self.events.append("configure")
        for callback in self.callbacks:
            callback()

    def test_unplugged_start_then_connect_configures_temperature(self):
        self.sensor._mcu_identify()
        self.assertEqual(self.adc._sample_count, 0)
        self.assertTrue(self.reconnect(self.mcu))
        self.assertEqual(self.events, ["non_critical_mcu_cartographer:identified", "configure",
                                      "non_critical_mcu_cartographer:reconnected"])
        self.assertEqual(self.adc._sample_count, 8)
        self.assertTrue(any(cmd.startswith("query_analog_in ") for cmd in self.commands))
        self.sensor.adc_callback(1., .4)
        self.sensor.temperature_callback.assert_called_once()

    def test_already_initialized_sensor_is_configured_on_reconnect(self):
        self.mcu.non_critical_disconnected = False
        self.sensor._mcu_identify()
        expected = (self.sensor.base_temperature, self.sensor.slope)
        self.mcu.non_critical_disconnected = True
        self.assertTrue(self.reconnect(self.mcu))
        self.assertEqual((self.sensor.base_temperature, self.sensor.slope), expected)
        self.assertEqual(len([c for c in self.commands if c.startswith("query_analog_in ")]), 1)

    def test_sensor_failure_prevents_success_and_configuration(self):
        self.mcu.lookup_query_command.side_effect = RuntimeError("sensor unavailable")
        with self.assertLogs(level="ERROR"):
            self.assertFalse(self.reconnect(self.mcu))
        self.mcu._connect.assert_not_called()
        self.assertTrue(self.mcu.non_critical_disconnected)
        self.assertFalse(self.mcu._reconnecting)
        self.assertNotIn("non_critical_mcu_cartographer:reconnected", self.events)

    def test_failed_identification_does_not_initialize_sensor(self):
        self.mcu._mcu_identify.return_value = False
        self.assertFalse(self.reconnect(self.mcu))
        self.assertEqual(self.events, [])
        self.mcu.lookup_query_command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
