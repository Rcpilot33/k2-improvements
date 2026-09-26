#!/usr/bin/env python3

import copy
from pathlib import Path
import re
import unittest
from unittest import mock
import urllib.error

import configure_fluidd_layout as layout


class FluiddLayoutTests(unittest.TestCase):
    def test_wiped_printer_creates_missing_fluidd_namespace(self):
        created = {
            "result": {
                "namespace": "fluidd",
                "key": "macros",
                "value": {},
            }
        }
        with mock.patch.object(
            layout,
            "_request_json",
            side_effect=[None, created],
        ) as request_json:
            self.assertTrue(layout.configure("http://127.0.0.1:7125"))

        first = request_json.call_args_list[0]
        self.assertTrue(first.kwargs["allow_missing"])
        second = request_json.call_args_list[1]
        self.assertEqual(second.kwargs["method"], "POST")
        self.assertEqual(second.kwargs["body"]["namespace"], "fluidd")
        self.assertEqual(second.kwargs["body"]["key"], "macros")
        self.assertEqual(len(second.kwargs["body"]["value"]["stored"]), 17)

    def test_only_get_404_may_be_treated_as_missing(self):
        missing = urllib.error.HTTPError(
            "http://127.0.0.1:7125/server/database/item",
            404,
            "Namespace fluidd not found",
            None,
            None,
        )
        with mock.patch.object(layout.urllib.request, "urlopen", side_effect=missing):
            self.assertIsNone(
                layout._request_json(
                    "http://127.0.0.1:7125/server/database/item",
                    allow_missing=True,
                )
            )
            with self.assertRaises(layout.LayoutError):
                layout._request_json(
                    "http://127.0.0.1:7125/server/database/item",
                    method="POST",
                    allow_missing=True,
                )

    def test_setup_checklist_uses_fluidd_button_labels(self):
        workflow = (Path(__file__).resolve().parents[2] / "menus" / "workflows.sh").read_text()
        checklist = workflow.split("show_cartographer_setup_checklist() {", 1)[1].split(
            "run_protected_firmware_restart() {", 1
        )[0]
        for name, alias, _color in layout.MACRO_LAYOUT:
            if name.startswith(("A1", "A2")):
                self.assertIn(alias, checklist)
        self.assertIsNone(re.search(r"\bA\d{2}\b", checklist))

    def test_creates_category_and_all_aliases_without_renaming_macros(self):
        source = {
            "theme": {"isDark": True},
            "macros": {
                "stored": [{"name": "OTHER", "alias": "Mine", "visible": False}],
                "categories": [{"id": "other", "name": "Utilities"}],
                "expanded": [0],
            },
        }

        result = layout.merge_layout(source)
        category = next(
            item
            for item in result["macros"]["categories"]
            if item["name"] == layout.CATEGORY_NAME
        )
        targets = {
            item["name"]: item
            for item in result["macros"]["stored"]
            if item["name"].startswith("A")
        }

        self.assertEqual(
            list(targets), [name for name, _alias, _color in layout.MACRO_LAYOUT]
        )
        self.assertEqual(
            [targets[name]["alias"] for name, _alias, _color in layout.MACRO_LAYOUT],
            [alias for _name, alias, _color in layout.MACRO_LAYOUT],
        )
        self.assertEqual(
            [targets[name]["color"] for name, _alias, _color in layout.MACRO_LAYOUT],
            [color for _name, _alias, color in layout.MACRO_LAYOUT],
        )
        self.assertTrue(all(item["categoryId"] == category["id"] for item in targets.values()))
        self.assertTrue(all(not item["disabledWhilePrinting"] for item in targets.values()))
        self.assertTrue(targets["A11_CARTO_SELECT_DEFAULT"]["visible"])
        for name in layout.PLATE_SELECTOR_NAMES:
            self.assertFalse(targets[name]["visible"])
        self.assertEqual(result["macros"]["expanded"], [0])
        self.assertEqual(result["theme"], {"isDark": True})
        self.assertEqual(result["macros"]["stored"][0], source["macros"]["stored"][0])

    def test_reuses_named_category_and_preserves_user_customizations(self):
        source = {
            "macros": {
                "categories": [
                    {"id": "carto-user-id", "name": "Cartographer Calibration"},
                    {"id": "favorites", "name": "Favorites"},
                ],
                "stored": [
                    {
                        "name": "a11_carto_select_default",
                        "alias": "My Default Plate",
                        "categoryId": "favorites",
                        "visible": False,
                        "color": "#123456",
                        "order": 9,
                    },
                    {
                        "name": "A12_CARTO_SELECT_TEXTURED_PEI",
                        "alias": "",
                        "categoryId": "0",
                        "visible": True,
                    },
                ],
            }
        }

        result = layout.merge_layout(source, show_plate_selectors=True)
        categories = result["macros"]["categories"]
        self.assertEqual(len(categories), 2)
        first = result["macros"]["stored"][0]
        self.assertEqual(first["name"], "a11_carto_select_default")
        self.assertEqual(first["alias"], "My Default Plate")
        self.assertEqual(first["categoryId"], "favorites")
        self.assertFalse(first["visible"])
        self.assertEqual(first["color"], "#1AED07")
        self.assertEqual(first["order"], 9)
        second = result["macros"]["stored"][1]
        self.assertEqual(second["alias"], "Textured PEI (Creality Print)")
        self.assertEqual(second["color"], "#1AED07")
        self.assertEqual(second["categoryId"], "carto-user-id")
        self.assertTrue(second["visible"])

    def test_optional_workflow_reveals_all_named_plate_selectors(self):
        source = layout.merge_layout({"macros": {}})

        result = layout.merge_layout(source, show_plate_selectors=True, plate_slicers="both")
        targets = {item["name"]: item for item in result["macros"]["stored"]}

        for name in layout.PLATE_SELECTOR_NAMES:
            self.assertTrue(targets[name]["visible"])

    def test_core_layout_hides_previously_visible_plate_selectors(self):
        source = layout.merge_layout({"macros": {}}, show_plate_selectors=True)

        result = layout.merge_layout(source)
        targets = {item["name"]: item for item in result["macros"]["stored"]}

        for name in layout.PLATE_SELECTOR_NAMES:
            self.assertFalse(targets[name]["visible"])

    def test_normalizes_all_target_colors(self):
        source = {
            "macros": {
                "categories": [],
                "stored": [
                    {"name": "A11_CARTO_SELECT_DEFAULT", "color": "#1aed07"},
                    {"name": "A21_CARTO_SCAN_SELECTED", "color": "warning"},
                    {"name": "A23_CARTO_LOAD_SELECTED", "color": "primary"},
                ],
            }
        }

        result = layout.merge_layout(source)
        targets = {item["name"]: item for item in result["macros"]["stored"]}
        self.assertEqual(targets["A11_CARTO_SELECT_DEFAULT"]["color"], "#1AED07")
        self.assertEqual(targets["A21_CARTO_SCAN_SELECTED"]["color"], "#FF9800")
        self.assertEqual(targets["A23_CARTO_LOAD_SELECTED"]["color"], "#2196F3")

    def test_repairs_orphaned_category_assignment(self):
        source = {
            "macros": {
                "categories": [],
                "stored": [
                    {
                        "name": "A63_CARTO_INFO",
                        "alias": "",
                        "categoryId": "deleted-category",
                    }
                ],
            }
        }

        result = layout.merge_layout(source)
        category = result["macros"]["categories"][0]
        item = result["macros"]["stored"][0]
        self.assertEqual(item["categoryId"], category["id"])
        self.assertEqual(item["alias"], "CARTO_INFO")
        self.assertEqual(item["color"], "#2196F3")

    def test_repairs_named_uncategorized_assignment(self):
        source = {
            "macros": {
                "categories": [{"id": "generic", "name": "Uncategorized"}],
                "stored": [
                    {
                        "name": "A63_CARTO_INFO",
                        "alias": "CARTO_INFO",
                        "categoryId": "generic",
                    }
                ],
            }
        }

        result = layout.merge_layout(source)
        target_category = next(
            item
            for item in result["macros"]["categories"]
            if item["name"] == layout.CATEGORY_NAME
        )
        item = result["macros"]["stored"][0]
        self.assertEqual(item["categoryId"], target_category["id"])

    def test_is_idempotent(self):
        first = layout.merge_layout({"macros": {}})
        second = layout.merge_layout(copy.deepcopy(first))
        self.assertEqual(second, first)

    def test_rejects_malformed_fluidd_state(self):
        with self.assertRaises(layout.LayoutError):
            layout.merge_layout({"macros": {"categories": {}, "stored": []}})
        with self.assertRaises(layout.LayoutError):
            layout.merge_layout({"macros": {"categories": [], "stored": {}}})


if __name__ == "__main__":
    unittest.main()
