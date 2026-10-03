import importlib.util
import pathlib
import tempfile
import unittest


HERE = pathlib.Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "k2_m191_settings_editor", HERE / "k2_m191_settings_editor.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def sample_text():
    return """# user values\n[gcode_macro _START_PRINT_VARS]\nvariable_heat_soak: 4\ngcode:\n\n[gcode_macro _M191_VARS]\nvariable_bed_assist_enabled: 1\nvariable_bed_assist_trigger_delta: 3.0\nvariable_bed_assist_bed_target: 105.0\nvariable_bed_assist_degrees_above_commanded: 0.0\nvariable_bed_assist_z_height: 195.0\nvariable_circulation_fan_speed: 15.0\nvariable_circulation_fan_high_speed: 100.0\nvariable_circulation_fan_low_seconds: 45.0\nvariable_circulation_fan_high_seconds: 20.0\nvariable_bed_restore_z_height: 30.0\nvariable_bed_restore_side_fan_speed: 100.0\nvariable_chamber_fan_margin: 2.0\nvariable_bed_restore_tolerance: 5.0\nvariable_chamber_wait_max_delta: 5.0\ngcode:\n\n[other]\nvalue: keep\n"""


class ParseAndRewriteTests(unittest.TestCase):
    def test_parses_all_settings(self):
        values = MODULE.parse_settings(sample_text())
        self.assertEqual(values["bed_assist_enabled"], 1.0)
        self.assertEqual(values["bed_assist_z_height"], 195.0)
        self.assertEqual(values["circulation_fan_speed"], 15.0)
        self.assertEqual(values["circulation_fan_high_seconds"], 20.0)
        self.assertEqual(values["heat_soak"], 4.0)

    def test_rewrites_only_m191_values(self):
        values = MODULE.parse_settings(sample_text())
        values["bed_assist_enabled"] = 0
        values["bed_assist_z_height"] = 220
        values["circulation_fan_speed"] = 40
        values["heat_soak"] = 10
        updated = MODULE.rewrite_settings(sample_text(), values)
        self.assertIn("variable_bed_assist_enabled: 0\n", updated)
        self.assertIn("variable_bed_assist_z_height: 220.0\n", updated)
        self.assertIn("variable_circulation_fan_speed: 40.0\n", updated)
        self.assertIn("variable_heat_soak: 10.0\n", updated)
        self.assertIn("[other]\nvalue: keep\n", updated)

    def test_enforces_exclusive_and_inclusive_ranges(self):
        self.assertEqual(MODULE.validate_value("bed_assist_trigger_delta", 0), 0)
        with self.assertRaises(ValueError):
            MODULE.validate_value("bed_restore_tolerance", 0)
        with self.assertRaises(ValueError):
            MODULE.validate_value("bed_assist_z_height", 331)
        with self.assertRaises(ValueError):
            MODULE.validate_value("bed_assist_enabled", 0.5)
        with self.assertRaises(ValueError):
            MODULE.validate_value("circulation_fan_low_seconds", 0)
        with self.assertRaises(ValueError):
            MODULE.validate_value("heat_soak", 121)

    def test_heat_soak_is_only_read_from_start_print_section(self):
        duplicate = sample_text().replace(
            "variable_chamber_wait_max_delta: 5.0\n",
            "variable_chamber_wait_max_delta: 5.0\nvariable_heat_soak: 99\n",
        )
        values = MODULE.parse_settings(duplicate)
        self.assertEqual(values["heat_soak"], 4.0)

    def test_high_circulation_speed_cannot_be_below_low_speed(self):
        values = MODULE.parse_settings(sample_text())
        values["circulation_fan_high_speed"] = 10
        with self.assertRaisesRegex(ValueError, "must be at least"):
            MODULE.rewrite_settings(sample_text(), values)

    def test_formats_integer_and_fractional_values(self):
        self.assertEqual(MODULE.format_value("bed_assist_z_height", 195), "195.0")
        self.assertEqual(MODULE.format_value("bed_assist_z_height", 195.5), "195.5")

    def test_atomic_write_replaces_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "overrides.cfg"
            path.write_text(sample_text())
            MODULE.write_atomic(str(path), "replacement\n")
            self.assertEqual(path.read_text(), "replacement\n")


class FakeCommand:
    def __init__(self):
        self.messages = []

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.messages.append(message)


class FakeGcode:
    def __init__(self):
        self.commands = {}
        self.actions = []
        self.scripts = []

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler

    def respond_raw(self, message):
        self.actions.append(message)

    def run_script_from_command(self, script):
        self.scripts.append(script)


class FakeMacro:
    def __init__(self, variables):
        self.variables = variables


class FakePrinter:
    def __init__(self, objects):
        self.objects = objects

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)


class FakeConfig:
    def __init__(self, printer, path):
        self.printer = printer
        self.path = path

    def get_printer(self):
        return self.printer

    def get(self, name, default=None):
        return str(self.path) if name == "overrides_path" else default


class LiveSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = pathlib.Path(self.directory.name) / "overrides.cfg"
        self.path.write_text(sample_text())
        self.gcode = FakeGcode()
        values = MODULE.parse_settings(sample_text())
        self.m191 = FakeMacro({key: value for key, value in values.items() if key != "heat_soak"})
        self.start_print = FakeMacro({"heat_soak": values["heat_soak"]})
        self.printer = FakePrinter({
            "gcode": self.gcode,
            MODULE.SECTION_NAME: self.m191,
            MODULE.START_PRINT_SECTION_NAME: self.start_print,
        })
        self.editor = MODULE.K2M191SettingsEditor(FakeConfig(self.printer, self.path))
        self.command = FakeCommand()
        self.editor.cmd_open(self.command)

    def change(self, key, value):
        next(item for item in self.editor.settings if item["key"] == key)["current"] = value

    def test_save_updates_both_live_macros_and_file_without_restart(self):
        self.change("bed_assist_bed_target", 110.0)
        self.change("heat_soak", 8.0)
        self.editor.cmd_save(self.command)
        self.assertEqual(self.m191.variables["bed_assist_bed_target"], 110.0)
        self.assertEqual(self.start_print.variables["heat_soak"], 8.0)
        self.assertEqual(MODULE.parse_settings(self.path.read_text())["heat_soak"], 8.0)
        self.assertEqual(MODULE.parse_settings(self.path.read_text())["bed_assist_bed_target"], 110.0)
        self.assertEqual(self.gcode.scripts, [])
        self.assertIn("no restart needed", self.command.messages[-1])

    def test_missing_live_variable_does_not_write_file(self):
        self.change("heat_soak", 8.0)
        del self.start_print.variables["heat_soak"]
        with self.assertRaisesRegex(RuntimeError, "nothing was saved"):
            self.editor.cmd_save(self.command)
        self.assertEqual(self.path.read_text(), sample_text())

    def test_external_change_prevents_file_and_live_update(self):
        self.change("bed_assist_bed_target", 110.0)
        self.path.write_text(sample_text() + "# external change\n")
        with self.assertRaisesRegex(RuntimeError, "changed while the editor was open"):
            self.editor.cmd_save(self.command)
        self.assertEqual(self.m191.variables["bed_assist_bed_target"], 105.0)

    def test_no_changes_close_without_restart(self):
        self.editor.cmd_save(self.command)
        self.assertIsNone(self.editor.settings)
        self.assertEqual(self.gcode.scripts, [])

    def test_invalid_combination_does_not_write_or_update(self):
        self.change("circulation_fan_high_speed", 10.0)
        with self.assertRaisesRegex(RuntimeError, "must be at least"):
            self.editor.cmd_save(self.command)
        self.assertEqual(self.path.read_text(), sample_text())
        self.assertEqual(self.m191.variables["circulation_fan_high_speed"], 100.0)


if __name__ == "__main__":
    unittest.main()
