"""Dual-slicer selectors, saved preferences, and shared profile contracts."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import configure_fluidd_layout as layout


class PlateWorkflowTests(unittest.TestCase):
    def test_color_upgrade_preserves_each_slicer_mode(self):
        for mode in ("creality", "orca", "both"):
            old = layout.merge_layout({}, True, mode)
            for item in old["macros"]["stored"]:
                if item["name"] in layout.ORCA_SELECTOR_NAMES:
                    item["color"] = "#1AED07"
            updated = layout.merge_layout(old, True, mode)
            for before, after in zip(old["macros"]["stored"], updated["macros"]["stored"]):
                name = after["name"]
                self.assertEqual(before["visible"], after["visible"])
                self.assertEqual(before["alias"], after["alias"])
                if name in layout.ORCA_SELECTOR_NAMES:
                    self.assertEqual(after["color"], "#AB47BC")
                elif name in layout.CP_SELECTOR_NAMES or name == "A11_CARTO_SELECT_DEFAULT":
                    self.assertEqual(after["color"], "#1AED07")
                else:
                    self.assertEqual(before["color"], after["color"])
            self.assertEqual(layout.merge_layout(updated, True, mode), updated)

    def test_each_mode_is_repeatable_and_preserves_unrelated_metadata(self):
        state = {"theme": {"name": "custom"}}
        for mode in ("creality", "orca", "both", "orca", "creality"):
            state = layout.merge_layout(state, True, mode)
            visible = {item["name"] for item in state["macros"]["stored"]
                       if item["visible"] and item["name"] in layout.PLATE_SELECTOR_NAMES}
            self.assertEqual(visible, layout.visible_selectors(mode))
            self.assertEqual(layout.merge_layout(state, True, mode), state)
            self.assertEqual(state["theme"], {"name": "custom"})

    def test_legacy_aliases_updated_but_user_aliases_preserved(self):
        state = {"macros": {"stored": [
            {"name": "A14_CARTO_SELECT_HIGH_TEMP", "alias": "HIGH_TEMP"},
            {"name": "A12_CARTO_SELECT_TEXTURED_PEI", "alias": "My PEI"},
        ]}}
        stored = layout.merge_layout(state, True, "both")["macros"]["stored"]
        self.assertEqual(stored[0]["alias"], "High Temp (Creality Print)")
        self.assertEqual(stored[1]["alias"], "My PEI")

    def test_numbered_order_and_macro_definitions_match_layout(self):
        names = [row[0] for row in layout.MACRO_LAYOUT]
        self.assertEqual(names, sorted(names))
        import re
        config = Path(__file__).with_name("cartographer_macros.cfg").read_text()
        selectors = re.findall(r"\[gcode_macro (A\d+_CARTO_SELECT[^\]]*)\]", config)
        self.assertEqual(selectors, names[:11])
        self.assertEqual(len(layout.CP_SELECTOR_NAMES), 4)
        self.assertEqual(len(layout.ORCA_SELECTOR_NAMES), 6)

    def test_cli_choice_survives_update_without_choice_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "custom").mkdir()
            with mock.patch.dict(os.environ, {"PRINTER_CFG_DIR": directory}), \
                    mock.patch.object(layout, "configure", return_value=True) as configure:
                self.assertEqual(layout.read_plate_slicers(), "creality")
                with mock.patch("sys.argv", ["layout", "--show-plate-selectors", "--plate-slicers", "both"]):
                    self.assertEqual(layout.main(), 0)
                self.assertEqual(json.loads(layout.preference_path().read_text()), {"slicers": "both"})
                with mock.patch("sys.argv", ["layout", "--show-plate-selectors"]):
                    self.assertEqual(layout.main(), 0)
                self.assertEqual(configure.call_args.kwargs["plate_slicers"], "both")

    def test_failed_database_update_does_not_save_new_preference(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "custom").mkdir()
            with mock.patch.dict(os.environ, {"PRINTER_CFG_DIR": directory}), \
                    mock.patch.object(layout, "configure", side_effect=layout.LayoutError("offline")), \
                    mock.patch("sys.argv", ["layout", "--plate-slicers", "orca"]):
                self.assertEqual(layout.main(), 1)
                self.assertFalse(layout.preference_path().exists())


if __name__ == "__main__":
    unittest.main()
