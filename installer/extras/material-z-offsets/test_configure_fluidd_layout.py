#!/usr/bin/env python3

import copy
import importlib.util
import pathlib
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).with_name("configure_fluidd_layout.py")
SPEC = importlib.util.spec_from_file_location("material_layout", MODULE_PATH)
LAYOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAYOUT)


class FluiddLayoutTests(unittest.TestCase):
    def test_wiped_printer_creates_missing_fluidd_namespace(self):
        created = {"result": {"value": {}}}
        with mock.patch.object(
            LAYOUT, "_request_json", side_effect=[None, created]
        ) as request_json:
            self.assertTrue(LAYOUT.configure("http://127.0.0.1:7125"))

        self.assertTrue(request_json.call_args_list[0].kwargs["allow_missing"])
        post = request_json.call_args_list[1]
        self.assertEqual(post.kwargs["method"], "POST")
        self.assertEqual(post.kwargs["body"]["namespace"], "fluidd")
        self.assertEqual(post.kwargs["body"]["key"], "macros")
        self.assertEqual(len(post.kwargs["body"]["value"]["stored"]), 1)

    def test_creates_orange_macro_in_z_offsets(self):
        result = LAYOUT.merge_layout({"macros": {}})
        category = result["macros"]["categories"][0]
        item = result["macros"]["stored"][0]
        self.assertEqual(category["name"], "Z Offsets")
        self.assertEqual(item["name"], "MATERIAL_Z_OFFSETS")
        self.assertEqual(item["alias"], "Material_Z_Offsets")
        self.assertEqual(item["color"], "#FF9800")
        self.assertEqual(item["categoryId"], category["id"])
        self.assertTrue(item["disabledWhilePrinting"])

    def test_reuses_existing_z_offsets_category(self):
        source = {"macros": {"categories": [{"id": "z", "name": "Z Offsets"}], "stored": []}}
        result = LAYOUT.merge_layout(source)
        self.assertEqual(result["macros"]["stored"][0]["categoryId"], "z")

    def test_preserves_user_alias_and_visibility(self):
        source = {"macros": {"categories": [{"id": "z", "name": "Z Offsets"}], "stored": [{
            "name": "material_z_offsets", "alias": "Mine", "visible": False, "categoryId": "z"
        }]}}
        item = LAYOUT.merge_layout(source)["macros"]["stored"][0]
        self.assertEqual(item["alias"], "Mine")
        self.assertFalse(item["visible"])
        self.assertEqual(item["color"], "#FF9800")

    def test_is_idempotent(self):
        first = LAYOUT.merge_layout({"macros": {}})
        self.assertEqual(LAYOUT.merge_layout(copy.deepcopy(first)), first)

    def test_rejects_malformed_macro_metadata(self):
        with self.assertRaises(LAYOUT.LayoutError):
            LAYOUT.merge_layout({"macros": {"categories": {}, "stored": []}})


if __name__ == "__main__":
    unittest.main()
