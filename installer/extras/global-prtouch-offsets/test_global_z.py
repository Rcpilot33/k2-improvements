import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prtouch_global_z", HERE / "k2_prtouch_global_z.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Command:
    def __init__(self, **params):
        self.params, self.responses = params, []

    def get(self, key, default=None):
        return self.params.get(key, default)

    def get_float(self, key, **kwargs):
        return float(self.get(key))

    def get_int(self, key, minval=None, maxval=None):
        value = int(self.get(key))
        if minval is not None and value < minval or maxval is not None and value > maxval:
            raise self.error("out of bounds")
        return value

    def error(self, text):
        return RuntimeError(text)

    def respond_info(self, text):
        self.responses.append(text)


class Motion:
    def __init__(self):
        self.pos, self.moves = [175., 175., 3., 0.], []

    def get_position(self):
        return self.pos

    def move(self, pos, speed):
        self.pos = list(pos)
        self.moves.append((list(pos), speed))


class GCodeMove:
    def __init__(self, next_transform):
        self.transform = next_transform
        self.homing_origin_z = .100

    def set_move_transform(self, transform, force=False):
        assert force
        old, self.transform = self.transform, transform
        return old

    def reset_last_position(self):
        self.last_position = self.transform.get_position()


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "offsets.json"
        self.motion = Motion()
        self.move = GCodeMove(self.motion)
        self.raw = {"bed_mesh custom_sheet_70.0c_0.0c": {}}
        self.stats = SimpleNamespace(state="standby")
        self.stats.get_status = lambda time: {"state": self.stats.state}
        self.actions, self.commands = [], {}
        self.probe = SimpleNamespace(name="prtouch_v3", z_offset=-.020)
        self.objects = {
            "gcode": SimpleNamespace(register_command=lambda name, handler: self.commands.update({name: handler}),
                                     respond_raw=self.actions.append),
            "probe": self.probe,
            "k2_prtouch_touchscreen": SimpleNamespace(get_status=lambda time: {"transient_only": True}),
            "gcode_move": self.move, "print_stats": self.stats,
            "configfile": SimpleNamespace(get_status=lambda time: {"config": self.raw}),
            "virtual_sdcard": SimpleNamespace(print_file_name_path=None)}
        self.events = {}
        self.printer = SimpleNamespace(
            lookup_object=lambda name, default=None: self.objects.get(name, default),
            register_event_handler=lambda name, callback: self.events.update({name: callback}),
            config_error=RuntimeError, command_error=RuntimeError)
        self.config = SimpleNamespace(get_printer=lambda: self.printer,
                                      get=lambda key, default: str(self.path))
        self.helper = m.load_config(self.config)
        self.ready()

    def ready(self):
        self.events["klippy:ready"]()

    def cmd(self, name, **params):
        command = Command(**params)
        getattr(self.helper, "cmd_" + name)(command)
        return command

    def plate_aware(self):
        self.objects["gcode_macro _PLATE_AWARE_MESH"] = object()

    def values(self, **values):
        self.helper.values.update(values)

    def test_initial_default_is_minus_080_no_baseline_write_or_motion(self):
        self.assertEqual(self.helper.values, {"default": -.080})
        self.assertAlmostEqual(self.helper.delta, -.060)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.motion.moves, [])
        self.assertEqual(self.probe.z_offset, -.02)

    def test_fresh_zero_baseline_uses_initial_default_without_double_counting(self):
        self.helper.installed = False
        self.move.transform = self.motion
        self.probe.z_offset = 0.
        self.ready()
        self.assertEqual(self.helper.baseline, 0.)
        self.assertEqual(self.helper.active_value, -.080)
        self.assertAlmostEqual(self.helper.delta, -.080)
        self.assertEqual(self.motion.moves, [])
        self.assertFalse(self.path.exists())
        self.helper.move([100., 100., .200, 0.], 25)
        self.assertAlmostEqual(self.motion.pos[2], .280)
        self.assertEqual(self.move.homing_origin_z, .100)
        self.assertEqual(self.probe.z_offset, 0.)

    def test_existing_saved_offsets_survive_initial_default_change_and_baseline_reset(self):
        saved = {"default": -.025, "epoxy": -.045, "textured_pei": 0.}
        m.write_json(str(self.path), {"version": 1, "offsets": saved})
        before = self.path.read_bytes()
        self.helper.installed = False
        self.move.transform = self.motion
        self.probe.z_offset = 0.
        self.ready()
        self.assertEqual(self.helper.values, saved)
        self.assertAlmostEqual(self.helper.delta, -.025)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.motion.moves, [])

    def test_saved_zero_default_is_not_replaced_by_initial_default(self):
        m.write_json(str(self.path), {"version": 1, "offsets": {"default": 0.}})
        before = self.path.read_bytes()
        self.helper.installed = False
        self.move.transform = self.motion
        self.probe.z_offset = 0.
        self.ready()
        self.assertEqual(self.helper.values, {"default": 0.})
        self.assertEqual(self.helper.delta, 0.)
        self.assertEqual(self.path.read_bytes(), before)

    def test_initial_default_is_inherited_by_new_plates_and_missing_surface(self):
        self.plate_aware()
        for params in ({"SURFACE": "textured_pei"}, {"SURFACE": "epoxy"},
                       {"SURFACE": "new_sheet"}, {}):
            self.cmd("apply", **params)
            self.assertEqual(self.helper.active_value, -.080)
            self.assertAlmostEqual(self.helper.delta, -.060)
        self.assertEqual(self.helper.values, {"default": -.080})
        self.assertFalse(self.path.exists())

    def test_default_only_without_plate_extra_ignores_surface(self):
        self.values(default=-.030, textured_pei=-.010)
        self.cmd("apply", SURFACE="textured_pei")
        self.assertEqual(self.helper.active_surface, "default")
        self.assertEqual(self.helper.active_value, -.030)
        m.write_json(str(self.path), {"version": 1, "offsets": self.helper.values})
        self.cmd("open")
        self.assertEqual(self.helper.names, ["default"])

    def test_cp_orca_shared_and_distinct_plate_selection(self):
        self.plate_aware()
        self.values(high_temp=-.030, textured_pei=-.040, epoxy=-.050,
                    orca_cool_plate=-.060, orca_engineering=-.070)
        for name in ("high_temp", "textured_pei", "epoxy", "orca_cool_plate", "orca_engineering"):
            self.cmd("apply", SURFACE=name.upper())
            self.assertEqual(self.helper.active_surface, name)
            self.assertEqual(self.helper.active_value, self.helper.values[name])

    def test_missing_surface_empty_explicit_default_and_unknown_inherit(self):
        self.plate_aware()
        self.values(default=-.025, epoxy=-.060)
        self.cmd("apply", SURFACE="epoxy")
        for params in ({}, {"SURFACE": ""}, {"SURFACE": "default"}, {"SURFACE": "new_sheet"}):
            self.cmd("apply", **params)
            self.assertEqual(self.helper.active_value, -.025)
        self.assertNotIn("new_sheet", self.helper.values)
        self.assertFalse(self.path.exists())

    def test_transform_applies_delta_once_and_preserves_material_origin_xyz_e(self):
        self.values(default=-.010)
        self.cmd("apply")
        pos = [100., 90., .300, 4.]
        self.helper.move(pos, 50)
        self.assertEqual(pos, [100., 90., .300, 4.])
        actual = self.motion.moves[-1][0]
        self.assertAlmostEqual(actual[2], .290)
        self.assertEqual(actual[:2] + actual[3:], [100., 90., 4.])
        self.assertEqual(self.move.homing_origin_z, .100)
        self.assertEqual(self.probe.z_offset, -.020)
        self.assertEqual(self.helper.get_position(), pos)
        self.cmd("apply")
        self.assertAlmostEqual(self.helper.delta, .010)
        self.helper.move(pos, 50)
        self.assertEqual(actual, self.motion.moves[-1][0])

    def test_closer_and_farther_signs_and_existing_mesh_chain(self):
        for value, expected in ((-.010, .190), (-.030, .210)):
            self.values(default=value)
            self.cmd("apply")
            self.helper.move([100, 100, .200, 0], 25)
            self.assertAlmostEqual(self.motion.pos[2], expected)
        self.assertIs(self.helper.next_transform, self.motion)

    def test_homing_position_resync_uses_same_transform_without_changing_origin(self):
        self.values(default=-.010)
        self.cmd("apply")
        self.motion.pos[2] = 2.0  # direct native homing/probing is unchanged
        self.move.reset_last_position()
        self.assertAlmostEqual(self.move.last_position[2], 2.010)
        self.assertEqual(self.move.homing_origin_z, .100)

    def test_reset_discards_previous_plate_without_stacking_or_motion(self):
        self.plate_aware()
        self.values(epoxy=-.060)
        self.cmd("apply", SURFACE="epoxy")
        self.cmd("reset")
        self.assertEqual(self.helper.active_surface, "default")
        self.assertAlmostEqual(self.helper.delta, -.060)
        self.assertEqual(self.motion.moves, [])

    def test_prompt_lists_both_slicers_custom_profiles_and_inherited_values(self):
        self.plate_aware()
        self.objects["bed_mesh"] = SimpleNamespace(get_status=lambda time: {
            "profiles": {"unsaved_sheet_70.0c_0.0c": {}}})
        self.cmd("open")
        self.assertTrue(set(m.SURFACES) <= set(self.helper.names))
        self.assertIn("custom_sheet", self.helper.names)
        self.assertIn("unsaved_sheet", self.helper.names)
        self.assertTrue(any("prtouch_global_offsets_surface TEXTURED_PEI|-0.080|3|1" in action for action in self.actions))
        self.assertIn("// action:prtouch_global_offsets_show", self.actions)
        self.assertIn("// action:prtouch_global_offsets_begin 0|0.010", self.actions)
        self.assertFalse(any("prompt_button" in action or "global_carto_offsets_" in action for action in self.actions))
        self.assertFalse(self.path.exists())

    def test_cancel_drops_working_changes_no_stage_write_or_motion(self):
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        self.cmd("cancel")
        self.assertIsNone(self.helper.session)
        self.assertEqual(self.helper.values["default"], -.080)
        self.assertAlmostEqual(self.helper.delta, -.060)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.motion.moves, [])

    def test_save_default_is_durable_active_no_printer_config_staging(self):
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        self.cmd("save")
        values, digest = m.read_table(str(self.path), -.02)
        self.assertEqual(values["default"], -.030)
        self.assertIsNotNone(digest)
        self.assertAlmostEqual(self.helper.delta, -.010)
        self.assertEqual(self.motion.moves, [])
        self.assertEqual(self.move.homing_origin_z, .100)
        self.assertEqual(self.probe.z_offset, -.020)
        self.assertFalse(any("SAVE_CONFIG" in action for action in self.actions))
        self.helper.installed = False
        self.move.transform = self.motion  # simulate a fresh process
        self.ready()
        self.assertEqual(self.helper.active_value, -.030)

    def test_unchanged_save_does_not_create_file_or_freeze_inherited_plates(self):
        self.plate_aware()
        self.cmd("open")
        self.cmd("save")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.helper.values, {"default": -.080})

    def test_edit_default_updates_inheriting_plate_and_preserves_override(self):
        self.plate_aware()
        self.values(epoxy=-.060)
        m.write_json(str(self.path), {"version": 1, "offsets": self.helper.values})
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        self.assertEqual(self.helper._value("textured_pei"), -.030)
        self.assertEqual(self.helper._value("epoxy"), -.060)
        index = self.helper.names.index("epoxy")
        self.cmd("select", INDEX=index)
        self.cmd("inherit")
        self.cmd("save")
        self.assertNotIn("epoxy", self.helper.values)
        self.assertNotIn("textured_pei", self.helper.values)

    def test_explicit_plate_save_then_default_and_unknown_routing(self):
        self.plate_aware()
        self.cmd("open")
        self.cmd("stage", INDEX=self.helper.names.index("epoxy"), VALUE=-.045)
        self.cmd("save")
        self.cmd("apply", SURFACE="epoxy")
        self.assertEqual(self.helper.active_value, -.045)
        self.cmd("apply")
        self.assertEqual(self.helper.active_value, -.080)

    def test_idle_editor_refuses_printing_paused_unknown_and_missing_stats(self):
        for state in ("printing", "paused", None, "unknown"):
            self.stats.state = state
            for name in ("open", "save", "stage", "adjust", "select"):
                with self.assertRaises(RuntimeError):
                    self.cmd(name)
        self.assertFalse(self.path.exists())

    def test_print_started_after_open_save_and_adjust_refused(self):
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        self.stats.state = "printing"
        with self.assertRaises(RuntimeError):
            self.cmd("save")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.helper.values["default"], -.080)

    def test_external_file_change_is_not_overwritten(self):
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        m.write_json(str(self.path), {"version": 1, "offsets": {"default": -.040}})
        before = self.path.read_bytes()
        with self.assertRaises(RuntimeError):
            self.cmd("save")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.helper.active_value, -.080)

    def test_atomic_save_failure_keeps_old_file_and_active_value(self):
        m.write_json(str(self.path), {"version": 1, "offsets": self.helper.values})
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        before = self.path.read_bytes()
        with patch.object(m.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(RuntimeError):
                self.cmd("save")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.helper.active_value, -.080)
        self.assertEqual(list(self.path.parent.glob(".prtouch-global-z-*")), [])

    def test_invalid_offsets_surface_and_table_are_refused(self):
        self.cmd("open")
        for value in (float("nan"), float("inf"), -5.001, 5.001):
            with self.assertRaises(RuntimeError):
                self.cmd("stage", INDEX=0, VALUE=value)
        self.plate_aware()
        with self.assertRaises(RuntimeError):
            self.cmd("apply", SURFACE="bad;G28")
        for table in ({"version": 2}, {"version": 1, "offsets": {}},
                      {"version": 1, "offsets": {"default": True}}):
            self.path.write_text(json.dumps(table))
            with self.assertRaises(ValueError):
                m.read_table(str(self.path), -.02)

    def test_carto_exclusion_does_not_install_transform_or_change_probe(self):
        self.objects["cartographer"] = object()
        self.helper.installed = False
        self.move.transform = self.motion
        self.ready()
        self.assertIs(self.move.transform, self.motion)
        for name in ("open", "reset", "apply"):
            with self.assertRaises(RuntimeError):
                self.cmd(name)
        self.assertEqual(self.probe.z_offset, -.020)

    def test_requires_transient_only_compatibility(self):
        self.helper.installed = False
        self.objects["k2_prtouch_touchscreen"].get_status = lambda time: {"transient_only": False}
        with self.assertRaises(RuntimeError):
            self.ready()

    def test_invalid_native_baseline_never_installs_motion_transform(self):
        m.write_json(str(self.path), {"version": 1, "offsets": {"default": -.020}})
        self.helper.installed = False
        self.move.transform = self.motion
        self.probe.z_offset = float("nan")
        with self.assertRaisesRegex(RuntimeError, "Invalid PR Touch"):
            self.ready()
        self.assertIs(self.move.transform, self.motion)
        self.assertFalse(self.helper.installed)

    def test_recovery_field_preserves_native_offset_and_freezes_plate_value(self):
        self.plate_aware()
        self.values(epoxy=-.045)
        recovery = self.path.parent / "recovery.json"
        recovery.write_text(json.dumps({"SET_GCODE_OFFSET": -.125, "other": "keep"}))
        self.objects["virtual_sdcard"].print_file_name_path = str(recovery)
        self.stats.state = "printing"
        self.cmd("apply", SURFACE="epoxy")
        saved = json.loads(recovery.read_text())
        self.assertEqual(saved["SET_GCODE_OFFSET"], -.125)
        self.assertEqual(saved["other"], "keep")
        self.assertEqual(saved[m.RECOVERY_KEY]["offset"], -.045)
        self.values(epoxy=-.070)
        self.helper.delta = 0
        self.helper.recovery_path = None
        self.move.reset_last_position()  # native homing synchronizes before resume
        self.assertAlmostEqual(self.move.last_position[2], self.motion.pos[2] - .025)
        self.helper.move([100, 100, .200, 0], 25)
        self.assertEqual(self.helper.active_value, -.045)
        self.assertAlmostEqual(self.motion.pos[2], .225)

    def test_recovery_must_sync_position_before_changing_delta_for_a_move(self):
        recovery = self.path.parent / "recovery.json"
        recovery.write_text(json.dumps({m.RECOVERY_KEY: {
            "surface": "default", "offset": -.030, "baseline": -.020}}))
        self.objects["virtual_sdcard"].print_file_name_path = str(recovery)
        self.stats.state = "printing"
        with self.assertRaisesRegex(RuntimeError, "synchronize"):
            self.helper.move([100, 100, .200, 0], 25)
        self.assertAlmostEqual(self.helper.delta, -.060)
        self.assertEqual(self.motion.moves, [])
        self.move.reset_last_position()
        self.helper.move([100, 100, .200, 0], 25)
        self.assertAlmostEqual(self.motion.pos[2], .210)

    def test_malformed_recovery_fails_closed_before_motion(self):
        recovery = self.path.parent / "recovery.json"
        self.objects["virtual_sdcard"].print_file_name_path = str(recovery)
        self.stats.state = "printing"
        for data in ([], {m.RECOVERY_KEY: []}, {m.RECOVERY_KEY: {}}):
            recovery.write_text(json.dumps(data))
            with self.assertRaisesRegex(RuntimeError, "Cannot restore"):
                self.helper.move([100, 100, .200, 0], 25)
        self.assertEqual(self.motion.moves, [])

    def test_prompt_steps_and_directions_only_change_working_value(self):
        self.cmd("open")
        self.cmd("step", VALUE=.005)
        self.cmd("adjust", DIRECTION="up")
        self.assertEqual(self.helper.session["default"], -.075)
        self.assertIn("// action:prtouch_global_offsets_surface DEFAULT|-0.075|0|0", self.actions)
        self.assertIn("// action:prtouch_global_offsets_begin 0|0.005", self.actions)
        self.cmd("adjust", DIRECTION="down")
        self.assertEqual(self.helper.session["default"], -.080)
        self.assertEqual(self.helper.active_value, -.080)
        self.assertEqual(self.motion.moves, [])
        with self.assertRaises(RuntimeError):
            self.cmd("step", VALUE=.1)
        with self.assertRaises(RuntimeError):
            self.cmd("adjust", DIRECTION="sideways")

    def test_plate_workflow_change_blocks_saving_an_open_session(self):
        self.cmd("open")
        self.cmd("stage", INDEX=0, VALUE=-.030)
        self.plate_aware()
        with self.assertRaisesRegex(RuntimeError, "Plate workflow changed"):
            self.cmd("save")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.helper.active_value, -.080)

    def test_recovery_changed_baseline_or_missing_plate_workflow_blocks_motion(self):
        recovery = self.path.parent / "recovery.json"
        self.objects["virtual_sdcard"].print_file_name_path = str(recovery)
        self.stats.state = "printing"
        for entry in ({"surface": "default", "offset": -.030, "baseline": -.040},
                      {"surface": "epoxy", "offset": -.030, "baseline": -.020}):
            recovery.write_text(json.dumps({m.RECOVERY_KEY: entry}))
            self.helper.recovery_path = None
            with self.assertRaises(RuntimeError):
                self.helper.move([100, 100, .200, 0], 25)
        self.assertEqual(self.motion.moves, [])


if __name__ == "__main__":
    unittest.main()
