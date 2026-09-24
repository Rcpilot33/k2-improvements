#!/usr/bin/env python3

import copy
import unittest
from unittest import mock

import configure_fluidd_layout as layout


class FluiddLayoutTests(unittest.TestCase):
    def test_wiped_printer_creates_missing_fluidd_namespace(self):
        created = {"result": {"value": {}}}
        with mock.patch.object(
            layout, "_request_json", side_effect=[None, created]
        ) as request_json:
            self.assertTrue(layout.configure("http://127.0.0.1:7125"))

        self.assertTrue(request_json.call_args_list[0].kwargs["allow_missing"])
        post = request_json.call_args_list[1]
        self.assertEqual(post.kwargs["method"], "POST")
        self.assertEqual(post.kwargs["body"]["namespace"], "fluidd")
        self.assertEqual(post.kwargs["body"]["key"], "macros")
        self.assertEqual(len(post.kwargs["body"]["value"]["stored"]), 1)

    def test_creates_category_and_editor_metadata(self):
        source = {"theme": {"isDark": True}, "macros": {"stored": [], "categories": []}}
        result = layout.merge_layout(source)
        category = result["macros"]["categories"][0]
        item = result["macros"]["stored"][0]

        self.assertEqual(category["name"], "Z Offsets")
        self.assertEqual(item["name"], "GLOBAL_Z_OFFSETS_CARTO")
        self.assertEqual(item["alias"], "Global_Z_Offsets_Carto")
        self.assertEqual(item["categoryId"], category["id"])
        self.assertEqual(item["color"], "#2196F3")
        self.assertTrue(item["disabledWhilePrinting"])
        self.assertEqual(result["theme"], source["theme"])

    def test_preserves_user_alias_and_valid_category(self):
        source = {
            "macros": {
                "categories": [{"id": "mine", "name": "My offsets"}],
                "stored": [
                    {
                        "name": "global_z_offsets_carto",
                        "alias": "My editor",
                        "categoryId": "mine",
                        "visible": False,
                    }
                ],
            }
        }
        result = layout.merge_layout(source)
        item = result["macros"]["stored"][0]
        self.assertEqual(item["alias"], "My editor")
        self.assertEqual(item["categoryId"], "mine")
        self.assertFalse(item["visible"])
        self.assertEqual(item["color"], "#2196F3")
        self.assertTrue(item["disabledWhilePrinting"])

    def test_is_idempotent(self):
        first = layout.merge_layout({"macros": {}})
        second = layout.merge_layout(copy.deepcopy(first))
        self.assertEqual(second, first)

    def test_renames_existing_legacy_category(self):
        source = {
            "macros": {
                "categories": [{"id": "legacy", "name": "Global Touch offsets"}],
                "stored": [
                    {
                        "name": "GLOBAL_Z_OFFSETS_CARTO",
                        "categoryId": "legacy",
                    }
                ],
            }
        }
        result = layout.merge_layout(source)
        self.assertEqual(
            result["macros"]["categories"],
            [{"id": "legacy", "name": "Z Offsets"}],
        )
        self.assertEqual(result["macros"]["stored"][0]["categoryId"], "legacy")

    def test_renames_intermediate_category(self):
        source = {
            "macros": {
                "categories": [{"id": "intermediate", "name": "Just Z Offsets"}],
                "stored": [
                    {
                        "name": "GLOBAL_Z_OFFSETS_CARTO",
                        "categoryId": "intermediate",
                    }
                ],
            }
        }
        result = layout.merge_layout(source)
        self.assertEqual(
            result["macros"]["categories"],
            [{"id": "intermediate", "name": "Z Offsets"}],
        )
        self.assertEqual(result["macros"]["stored"][0]["categoryId"], "intermediate")

    def test_moves_editor_out_of_named_uncategorized_category(self):
        source = {
            "macros": {
                "categories": [{"id": "generic", "name": "Uncategorized"}],
                "stored": [
                    {
                        "name": "GLOBAL_Z_OFFSETS_CARTO",
                        "categoryId": "generic",
                    }
                ],
            }
        }
        result = layout.merge_layout(source)
        target = next(
            item for item in result["macros"]["categories"] if item["name"] == "Z Offsets"
        )
        self.assertEqual(result["macros"]["stored"][0]["categoryId"], target["id"])

    def test_rejects_malformed_state(self):
        with self.assertRaises(layout.LayoutError):
            layout.merge_layout({"macros": {"categories": {}, "stored": []}})


if __name__ == "__main__":
    unittest.main()
