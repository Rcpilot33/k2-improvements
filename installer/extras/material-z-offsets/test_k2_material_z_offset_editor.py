#!/usr/bin/env python3

import importlib.util
import pathlib
import tempfile
import unittest
import configparser
from types import SimpleNamespace
from unittest.mock import patch


MODULE_PATH = pathlib.Path(__file__).with_name("k2_material_z_offset_editor.py")
INSTALL_PATH = pathlib.Path(__file__).with_name("install.sh")
SPEC = importlib.util.spec_from_file_location("k2_material_z_offset_editor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


BASE_CONFIG = """# user overrides

[gcode_macro _START_PRINT_VARS]
variable_offset_PLA: -0.010
variable_heat_soak: 4
variable_offset_PETG: 0.075 # keep value
variable_offset_DEFAULT: 0.050
gcode:

[bed_mesh]
probe_count: 19,19
"""


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


class FakeMacro:
    def __init__(self):
        self.variables = {"offset_pla": -0.01, "offset_petg": 0.075, "offset_default": 0.05}

    def get_status(self, eventtime):
        return self.variables


class FakePrintStats:
    def __init__(self, state="standby"):
        self.state = state

    def get_status(self, eventtime):
        return {"state": self.state}


class FakePrinter:
    def __init__(self, state="standby"):
        self.objects = {
            "gcode": FakeGCode(),
            "print_stats": FakePrintStats(state),
            "gcode_macro _START_PRINT_VARS": FakeMacro(),
        }

    def lookup_object(self, name, default=None):
        return self.objects.get(name, default)


class FakeConfig:
    def __init__(self, printer, path):
        self.printer = printer
        self.path = path

    def get_printer(self):
        return self.printer

    def get(self, name, default=None):
        return self.path if name == "overrides_path" else default


class FakeGCmd:
    def __init__(self, **params):
        self.params = params
        self.info = []

    def get(self, name, default=None):
        return self.params.get(name, default)

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


class MaterialEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temporary.name, "overrides.cfg")
        self.path.write_text(BASE_CONFIG, encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def make_editor(self, state="standby"):
        printer = FakePrinter(state)
        editor = MODULE.K2MaterialZOffsetEditor(FakeConfig(printer, str(self.path)))
        return editor, printer

    def test_parser_preserves_order_and_places_default_last(self):
        offsets = MODULE.parse_material_offsets(BASE_CONFIG)
        self.assertEqual(offsets, [("PLA", -0.01), ("PETG", 0.075), ("DEFAULT", 0.05)])

    def test_rewriter_places_all_offsets_at_section_top(self):
        result = MODULE.rewrite_material_offsets(BASE_CONFIG, [
            ("PLA", -0.02), ("PETG", 0.08), ("TPU_95A", 0.0), ("DEFAULT", 0.04)
        ])
        section = result.split("[gcode_macro _START_PRINT_VARS]", 1)[1].split("[bed_mesh]", 1)[0]
        lines = [line for line in section.strip().splitlines() if line]
        self.assertEqual(lines[:4], [
            "variable_offset_PLA: -0.020",
            "variable_offset_PETG: 0.080",
            "variable_offset_TPU_95A: 0.000",
            "variable_offset_DEFAULT: 0.040",
        ])
        self.assertIn("variable_heat_soak: 4", section)
        self.assertEqual(result.count("variable_offset_"), 4)

    def test_normalize_file_is_idempotent(self):
        self.assertTrue(MODULE.normalize_file(str(self.path)))
        first = self.path.read_text(encoding="utf-8")
        self.assertFalse(MODULE.normalize_file(str(self.path)))
        self.assertEqual(self.path.read_text(encoding="utf-8"), first)

    def test_open_emits_materials_with_default_last(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        output = "\n".join(printer.objects["gcode"].responses)
        self.assertIn("material_z_offsets_material PLA|-0.010|0", output)
        self.assertIn("material_z_offsets_material DEFAULT|0.050|2", output)
        self.assertTrue(output.endswith("material_z_offsets_show"))

    def test_save_writes_file_and_activates_without_restart(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=0.1))
        editor.cmd_save(FakeGCmd())
        self.assertIn("variable_offset_PETG: 0.100", self.path.read_text(encoding="utf-8"))
        self.assertEqual(printer.objects["gcode"].scripts, [])
        self.assertEqual(printer.objects["gcode_macro _START_PRINT_VARS"].variables["offset_petg"], 0.1)
        editor.cmd_apply(FakeGCmd(MATERIAL="PETG"))
        self.assertEqual(printer.objects["gcode"].scripts, ["SET_GCODE_OFFSET Z=0.100"])

    def test_save_discards_only_pending_global_z_and_restores_staged_disk_value(self):
        editor, printer = self.make_editor()
        section = 'cartographer touch_model default'
        def parser(data):
            p = configparser.RawConfigParser()
            p.read_string(data)
            return p
        saved = '[%s]\nz_offset = -0.150\nsoftware_version = same\n' % section
        primary = self.path.with_name('printer.cfg')
        primary.write_text('SAVE_MARKER' + saved)
        staged = parser(saved)
        staged.set(section, 'z_offset', '-0.175')
        staged.add_section('bed_mesh new')
        staged.set('bed_mesh new', 'points', 'new calibration')
        config = SimpleNamespace(autosave=SimpleNamespace(fileconfig=staged),
            status_save_pending={section: {'z_offset': '-0.175', 'software_version': 'same'},
                                 'bed_mesh new': {'points': 'new calibration'}},
            save_config_pending=True,
            _read_config_file=lambda filename: pathlib.Path(filename).read_text(),
            _find_autosave_data=lambda raw: raw.split('SAVE_MARKER'),
            _build_config_wrapper=lambda data, filename: SimpleNamespace(fileconfig=parser(data)))
        printer.objects['configfile'] = config
        printer.get_start_args = lambda: {'config_file': str(primary)}
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=0.1))
        editor.cmd_save(FakeGCmd())
        self.assertEqual(config.autosave.fileconfig.get(section, 'z_offset'), '-0.150')
        self.assertEqual(config.status_save_pending, {'bed_mesh new': {'points': 'new calibration'}})
        self.assertTrue(config.save_config_pending)
        self.assertEqual(primary.read_text(), 'SAVE_MARKER' + saved)
        self.assertEqual(printer.objects['gcode'].scripts, [])
        # If only global Z remains, the prompt is cleared without touching disk.
        config.status_save_pending = {section: {'z_offset': '-0.175'}}
        config.autosave.fileconfig.set(section, 'z_offset', '-0.175')
        editor._discard_pending_global_z()
        self.assertFalse(config.save_config_pending)
        self.assertEqual(config.status_save_pending, {})
        self.assertEqual(config.autosave.fileconfig.get(section, 'z_offset'), '-0.150')

        # New models with no saved baseline must never lose their calibration.
        new_section = 'cartographer scan_model new'
        config.autosave.fileconfig.add_section(new_section)
        config.autosave.fileconfig.set(new_section, 'z_offset', '0')
        config.status_save_pending = {new_section: {'z_offset': '0'}}
        config.save_config_pending = True
        editor._discard_pending_global_z()
        self.assertEqual(config.status_save_pending, {new_section: {'z_offset': '0'}})
        self.assertTrue(config.save_config_pending)

        # Calibration changes in the same model are unrelated and stay pending.
        config.status_save_pending = {section: {'z_offset': '-0.175', 'threshold': '2500'}}
        config.autosave.fileconfig.set(section, 'threshold', '2500')
        editor._discard_pending_global_z()
        self.assertEqual(config.status_save_pending, {section: {'threshold': '2500'}})
        self.assertTrue(config.save_config_pending)
        self.assertEqual(config.autosave.fileconfig.get(section, 'threshold'), '2500')

        # A saved regular/include option must not be reintroduced into autosave.
        primary.write_text(saved + 'SAVE_MARKER')
        config.status_save_pending = {section: {'z_offset': '-0.175'}}
        editor._discard_pending_global_z()
        self.assertFalse(config.autosave.fileconfig.has_option(section, 'z_offset'))
        self.assertFalse(config.save_config_pending)
        self.assertEqual(primary.read_text(), saved + 'SAVE_MARKER')

    def test_pending_save_failure_reports_material_values_already_persisted(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=0.1))
        command = FakeGCmd()
        with patch.object(editor, "_discard_pending_global_z", side_effect=RuntimeError("disk error")):
            with self.assertRaisesRegex(RuntimeError, "were saved and are active.*disk error"):
                editor.cmd_save(command)
        self.assertIn("variable_offset_PETG: 0.100", self.path.read_text())
        self.assertEqual(printer.objects["gcode_macro _START_PRINT_VARS"].variables["offset_petg"], 0.1)
        self.assertIsNone(editor.materials)
        self.assertEqual(command.info, [])

    def test_cancel_and_unchanged_save_do_not_discard_pending_config(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_save(FakeGCmd())
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=0.1))
        editor.cmd_cancel(FakeGCmd())
        self.assertEqual(printer.objects["gcode"].scripts, [])
        self.assertEqual(self.path.read_text(), BASE_CONFIG)

    def test_missing_live_macro_prevents_save(self):
        editor, printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        editor.cmd_stage(FakeGCmd(INDEX=1, VALUE=0.1))
        printer.objects.pop("gcode_macro _START_PRINT_VARS")
        with self.assertRaisesRegex(RuntimeError, "nothing was saved"):
            editor.cmd_save(FakeGCmd())
        self.assertEqual(self.path.read_text(encoding="utf-8"), BASE_CONFIG)

    def test_save_refuses_to_clobber_external_edit(self):
        editor, _printer = self.make_editor()
        editor.cmd_open(FakeGCmd())
        self.path.write_text(BASE_CONFIG + "# changed elsewhere\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "changed while"):
            editor.cmd_save(FakeGCmd())

    def test_known_material_applies_active_value_without_writing(self):
        editor, printer = self.make_editor()
        editor.cmd_apply(FakeGCmd(MATERIAL="PETG"))
        self.assertEqual(printer.objects["gcode"].scripts, ["SET_GCODE_OFFSET Z=0.075"])
        self.assertEqual(self.path.read_text(encoding="utf-8"), BASE_CONFIG)

    def test_unknown_material_uses_default_and_is_saved_before_default(self):
        editor, printer = self.make_editor()
        command = FakeGCmd(MATERIAL="PETG-CF")
        editor.cmd_apply(command)
        text = self.path.read_text(encoding="utf-8")
        self.assertLess(text.index("variable_offset_PETG_CF"), text.index("variable_offset_DEFAULT"))
        self.assertIn("variable_offset_PETG_CF: 0.000", text)
        self.assertEqual(printer.objects["gcode"].scripts, ["SET_GCODE_OFFSET Z=0.050"])
        self.assertEqual(printer.objects["gcode_macro _START_PRINT_VARS"].variables["offset_petg_cf"], 0.0)
        self.assertIn("current print still uses DEFAULT", command.info[0])

    def test_saved_material_missing_from_memory_becomes_active_for_next_print(self):
        text = BASE_CONFIG.replace(
            "variable_offset_DEFAULT: 0.050",
            "variable_offset_PETG_CF: 0.025\nvariable_offset_DEFAULT: 0.050",
        )
        self.path.write_text(text, encoding="utf-8")
        editor, printer = self.make_editor()
        editor.cmd_apply(FakeGCmd(MATERIAL="PETG-CF"))
        self.assertEqual(printer.objects["gcode"].scripts, ["SET_GCODE_OFFSET Z=0.050"])
        self.assertEqual(
            printer.objects["gcode_macro _START_PRINT_VARS"].variables["offset_petg_cf"],
            0.025,
        )
        editor.cmd_apply(FakeGCmd(MATERIAL="PETG-CF"))
        self.assertEqual(printer.objects["gcode"].scripts[-1], "SET_GCODE_OFFSET Z=0.025")

    def test_editor_is_blocked_while_printing_but_apply_is_allowed(self):
        editor, printer = self.make_editor("printing")
        with self.assertRaisesRegex(RuntimeError, "during a print"):
            editor.cmd_open(FakeGCmd())
        editor.cmd_apply(FakeGCmd(MATERIAL="PLA"))
        self.assertEqual(printer.objects["gcode"].scripts, ["SET_GCODE_OFFSET Z=-0.010"])

    def test_installer_refreshes_start_print_handoff(self):
        installer = INSTALL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'START_PRINT_SOURCE="$INSTALLER_BASE/features/macros/start_print/start_print.cfg"',
            installer,
        )
        self.assertIn(
            'ln -sfn "$START_PRINT_SOURCE" "$CUSTOM/start_print.cfg"',
            installer,
        )
        capture = installer.index("HAD_SURFACE_WRAPPER=1")
        refresh = installer.index(
            'ln -sfn "$START_PRINT_SOURCE" "$CUSTOM/start_print.cfg"'
        )
        restore = installer.index("surface-selection-wrapper/install.sh")
        self.assertLess(capture, refresh)
        self.assertLess(refresh, restore)


if __name__ == "__main__":
    unittest.main()
