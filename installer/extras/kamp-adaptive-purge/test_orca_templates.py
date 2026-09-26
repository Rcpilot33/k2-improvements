"""Static contracts for the captured Orca 2.4.2 plate names and start paths.

These are not a substitute for slicing or physical printer validation.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = Path(__file__).with_name("slicer-templates")
PLATES = [
    ("Cool Plate", "orca_cool_plate"),
    ("Engineering Plate", "orca_engineering"),
    ("High Temp Plate", "high_temp"),
    ("Textured PEI Plate", "textured_pei"),
    ("Textured Cool Plate", "orca_textured_cool"),
    ("Supertack Plate", "orca_supertack"),
]


class OrcaTemplateTests(unittest.TestCase):
    def test_four_variants_have_correct_material_temperature_and_purge_contract(self):
        files = sorted(TEMPLATES.glob("orca-start-material-*.gcode"))
        self.assertEqual(len(files), 4)
        for path in files:
            code = path.read_text()
            kamp = path.stem.endswith("-kamp")
            surface = "surface-profiles" in path.stem
            with self.subTest(template=path.name):
                starts = [line for line in code.splitlines() if line.startswith("START_PRINT ")]
                self.assertEqual(len(starts), 7 if surface else 1)
                for line in starts:
                    self.assertIn("CHAMBER_TEMP=[overall_chamber_temperature]", line)
                    self.assertIn("MATERIAL={filament_type[initial_tool]}", line)
                    self.assertEqual("SURFACE=" in line, surface)
                self.assertNotIn("multicolor_method", code)
                self.assertEqual(code.count("T[initial_no_support_extruder]"), 1)
                self.assertEqual(code.count("LINE_PURGE"), int(kamp))
                self.assertEqual("G1 X150 Y0 E15 F6000" in code, not kamp)
                purge = "LINE_PURGE" if kamp else "G1 X0 Y0 E15 F6000"
                self.assertLess(code.index("M109 S[nozzle_temperature_initial_layer]"), code.index(purge))
                self.assertLess(code.index("M83"), code.index(purge))

    def test_both_surface_variants_use_exact_captured_names_and_default(self):
        for path in TEMPLATES.glob("orca-start-material-surface-profiles*.gcode"):
            code = path.read_text()
            mapping = re.findall(r'\{(?:if|elsif) curr_bed_type == "([^"]+)"\}\nSTART_PRINT [^\n]* SURFACE=(\w+)', code)
            self.assertEqual(mapping, PLATES)
            self.assertRegex(code, r"\{else\}\nSTART_PRINT [^\n]* SURFACE=default\n\{endif\}")

    def test_selectors_use_same_model_names_as_templates(self):
        config = (ROOT / "installer/extras/cartographer-macros/cartographer_macros.cfg").read_text()
        for index, (_plate, model) in enumerate(PLATES, 1):
            section = re.search(r"\[gcode_macro A16_CARTO_SELECT_ORCA_0" + str(index) + r"_[^\]]+\]([^\[]+)", config)
            self.assertIsNotNone(section)
            self.assertIn("VALUE=\"'" + model + "'\"", section[1])

    def test_no_carto_profile_contract_has_no_plate_allowlist(self):
        code = (ROOT / "features/macros/bed_mesh/bed_mesh.cfg").read_text()
        for name in ("_CREATE_MESH", "MESH_IF_NEEDED"):
            section = code.split("[gcode_macro " + name + "]", 1)[1].split("[gcode_macro", 1)[0]
            self.assertIn("params.SURFACE|default('')|string|lower", section)
            self.assertIn("PROFILE_NAME = SURFACE + '_' + BED_TEMP|string + 'c_' + CHAMBER_TEMP|string + 'c'", section)
        start = (ROOT / "features/macros/start_print/start_print.cfg").read_text()
        self.assertIn("SURFACE={SURFACE}", start)
        wrapper = (ROOT / "installer/extras/surface-selection-wrapper/install.sh").read_text()
        self.assertIn("CARTOGRAPHER_SCAN_MODEL LOAD={SURFACE}", wrapper)
        self.assertIn("CARTOGRAPHER_TOUCH_MODEL LOAD={SURFACE}", wrapper)


if __name__ == "__main__":
    unittest.main()
