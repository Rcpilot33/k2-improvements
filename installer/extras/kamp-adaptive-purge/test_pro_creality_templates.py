"""Check the K2 Pro purge paths across the four Creality Print presets."""
from pathlib import Path
import unittest


TEMPLATES = Path(__file__).with_name("slicer-templates") / "k2-pro"


class ProCrealityTemplates(unittest.TestCase):
    def test_multicolor_and_standard_paths(self):
        files = sorted(TEMPLATES.glob("creality-start-material-*.gcode"))
        self.assertEqual(len(files), 4)
        for path in files:
            with self.subTest(template=path.name):
                header, branches = path.read_text().split("{if multicolor_method}")
                cfs, direct = branches.strip().removesuffix("{endif}").split("{else}")
                starts = [line for line in header.splitlines() if line.startswith("START_PRINT ")]
                self.assertTrue(starts)
                for line in starts:
                    self.assertIn('MATERIAL="{filament_type[initial_tool]}"', line)
                    self.assertIn("CHAMBER_TEMP=[overall_chamber_temperature]", line)
                    self.assertEqual("SURFACE=" in line, "surface-profiles" in path.stem)

                preparation, cfs_exit = cfs.split("M8200 O")
                self.assertEqual(preparation.count("; FLUSH_START"), 3)
                self.assertEqual(preparation.count("G0 X157 Y327"), 3)
                self.assertIn("G0 X124 Y329", preparation.split("; FLUSH_END")[-1])
                self.assertLess(cfs_exit.index("G1 Z3 F600"), cfs_exit.index("G1 X149 F12000"))
                self.assertNotIn("M8200", direct)
                for branch in (cfs, direct):
                    self.assertEqual(branch.count("T[initial_no_support_extruder]"), 1)
                    self.assertNotIn("Y-1", branch)
                    kamp = path.stem.endswith("-kamp")
                    self.assertEqual(branch.count("LINE_PURGE"), int(kamp))
                    self.assertEqual(branch.count("G1 X0 Y0 E9 "), int(not kamp))
                    self.assertEqual(branch.count("G1 X150 Y0 E9 "), int(not kamp))
                    purge = "LINE_PURGE" if kamp else "G1 X0 Y0 E9 "
                    self.assertLess(branch.index("M83"), branch.index(purge))
                    if kamp:
                        self.assertLess(branch.index("M109 S[nozzle_temperature_initial_layer]"), branch.index(purge))


if __name__ == "__main__":
    unittest.main()
