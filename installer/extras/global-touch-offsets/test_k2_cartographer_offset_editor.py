#!/usr/bin/env python3

import importlib.util
import pathlib
import unittest
from dataclasses import dataclass


MODULE_PATH = pathlib.Path(__file__).with_name("k2_cartographer_offset_editor.py")
SPEC = importlib.util.spec_from_file_location("k2_cartographer_offset_editor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeGCode:
    def __init__(self):
        self.commands = {}
        self.responses = []
        self.scripts = []

    def register_command(self, name, handler, desc=None):
        self.commands[name] = handler

    def respond_raw(self, message):
        self.responses.append(message)

    def run_script_from_command(self, script):
        self.scripts.append(script)


class FakeConfigFile:
    def __init__(self):
        self.raw_config = {
            "cartographer touch_model custom": {"z_offset": "-0.070"},
            "cartographer scan_model default": {"z_offset": "0"},
            "cartographer touch_model default": {"z_offset": "-0.060"},
            "cartographer touch_model textured_pei": {"z_offset": "-0.050"},
        }
        self.saved = []

    def get_status(self, eventtime):
        return {"config": self.raw_config}

    def set(self, section, option, value):
        self.saved.append((section, option, value))


@dataclass(frozen=True)
class FakeTouchModel:
    name: str
    z_offset: float


class FakeTouchMode:
    def __init__(self, models):
        self._models = models
        self._loaded_model = models["default"]

    def has_model(self):
        return self._loaded_model is not None

    def get_model(self):
        return self._loaded_model

    def load_model(self, name):
        self._loaded_model = self._models[name]


class FakeCartographer:
    def __init__(self):
        self.config = type("Config", (), {})()
        self.config.touch = type("Touch", (), {})()
        self.config.touch.models = {
            name: FakeTouchModel(name, value)
            for name, value in (("default", -0.060), ("textured_pei", -0.050), ("custom", -0.070))
        }
        self.touch_mode = FakeTouchMode(self.config.touch.models)


class FakePrintStats:
    def __init__(self, state="standby"):
        self.state = state

    def get_status(self, eventtime):
        return {"state": self.state}


class FakePrinter:
    def __init__(self, state="standby"):
        self.gcode = FakeGCode()
        self.configfile = FakeConfigFile()
        self.print_stats = FakePrintStats(state)
        self.cartographer = FakeCartographer()

    def lookup_object(self, name, default=None):
        return getattr(self, name, default)


class FakeConfig:
    def __init__(self, printer):
        self.printer = printer

    def get_printer(self):
        return self.printer


class FakeGCmd:
    def __init__(self, **params):
        self.params = params
        self.info = []

    def get_int(self, name, minval=None, maxval=None):
        value = int(self.params[name])
        if minval is not None and value < minval:
            raise self.error("below minimum")
        if maxval is not None and value > maxval:
            raise self.error("above maximum")
        return value

    def get_float(self, name, minval=None, maxval=None):
        value = float(self.params[name])
        if minval is not None and value < minval:
            raise self.error("below minimum")
        if maxval is not None and value > maxval:
            raise self.error("above maximum")
        return value

    def error(self, message):
        return RuntimeError(message)

    def respond_info(self, message):
        self.info.append(message)


class OffsetEditorTests(unittest.TestCase):
    def make_editor(self, state="standby"):
        printer = FakePrinter(state)
        return MODULE.K2CartographerOffsetEditor(FakeConfig(printer)), printer

    def test_discovers_touch_models_and_emits_live_editor_rows(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())

        self.assertEqual(
            [model["name"] for model in editor.models],
            ["default", "textured_pei", "custom"],
        )
        output = "\n".join(printer.gcode.responses)
        self.assertIn("// action:global_touch_offsets_begin", output)
        self.assertIn("// action:global_touch_offsets_model DEFAULT|-0.060|0", output)
        self.assertIn("TEXTURED_PEI|-0.050|1", output)
        self.assertNotIn("scan_model", output)

    def test_stage_is_cached_and_cancel_discards_all_changes(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=0, VALUE=-0.135))

        self.assertEqual(editor.models[0]["current"], -0.135)
        cancel = FakeGCmd()
        editor.cmd_cancel(cancel)
        self.assertIsNone(editor.models)
        self.assertEqual(printer.configfile.saved, [])
        self.assertEqual(printer.gcode.scripts, [])

    def test_stage_rejects_positive_touch_offsets(self):
        editor, _printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        with self.assertRaisesRegex(RuntimeError, "above maximum"):
            editor.cmd_stage(FakeGCmd(INDEX=0, VALUE=0.005))

    def test_save_writes_changed_model_and_activates_without_restart(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=-0.075))
        editor.cmd_save(FakeGCmd())

        self.assertEqual(
            printer.configfile.saved,
            [("cartographer touch_model textured_pei", "z_offset", "-0.075")],
        )
        self.assertEqual(
            printer.gcode.scripts,
            ["CXSAVE_CONFIG"],
        )
        self.assertEqual(printer.cartographer.config.touch.models["textured_pei"].z_offset, -0.075)
        self.assertEqual(printer.cartographer.touch_mode.get_model().z_offset, -0.060)
        self.assertNotIn("\nSAVE_CONFIG", "\n".join(printer.gcode.scripts))
        self.assertIsNone(editor.models)

        editor.cmd_open(FakeGCmd())
        self.assertEqual(editor.models[1]["current"], -0.075)

    def test_save_refreshes_currently_loaded_model(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=0, VALUE=-0.100))
        editor.cmd_save(FakeGCmd())
        self.assertEqual(printer.cartographer.touch_mode.get_model().z_offset, -0.100)

    def test_missing_live_models_prevents_save(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=0, VALUE=-0.100))
        printer.cartographer = None
        with self.assertRaisesRegex(RuntimeError, "nothing was saved"):
            editor.cmd_save(FakeGCmd())
        self.assertEqual(printer.configfile.saved, [])
        self.assertEqual(printer.gcode.scripts, [])

    def test_unchanged_save_closes_without_restart(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        save = FakeGCmd()
        editor.cmd_save(save)
        self.assertEqual(printer.gcode.scripts, [])
        self.assertEqual(save.info, ["No Global Carto Touch Z Offset changes to save"])

    def test_open_and_save_are_blocked_during_print(self):
        editor, printer = self.make_editor("printing")
        with self.assertRaisesRegex(RuntimeError, "during a print"):
            editor.cmd_open(FakeGCmd())

        printer.print_stats.state = "standby"
        editor.cmd_open(FakeGCmd())
        printer.print_stats.state = "paused"
        with self.assertRaisesRegex(RuntimeError, "during a print"):
            editor.cmd_save(FakeGCmd())

    def test_reports_when_no_touch_models_exist(self):
        editor, printer = self.make_editor()
        printer.configfile.raw_config = {}
        with self.assertRaisesRegex(RuntimeError, "No saved"):
            editor.cmd_open(FakeGCmd())


if __name__ == "__main__":
    unittest.main()
