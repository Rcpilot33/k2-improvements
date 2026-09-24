import importlib.util
import pathlib
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).parent
SPEC = importlib.util.spec_from_file_location(
    "configure_fluidd_layout", HERE / "configure_fluidd_layout.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LayoutTests(unittest.TestCase):
    def test_wiped_printer_creates_missing_fluidd_namespace(self):
        created = {"result": {"value": {}}}
        with mock.patch.object(
            MODULE, "_request_json", side_effect=[None, created]
        ) as request_json:
            self.assertTrue(MODULE.configure("http://127.0.0.1:7125"))

        self.assertTrue(request_json.call_args_list[0].kwargs["allow_missing"])
        post = request_json.call_args_list[1]
        self.assertEqual(post.kwargs["method"], "POST")
        self.assertEqual(post.kwargs["body"]["namespace"], "fluidd")
        self.assertEqual(post.kwargs["body"]["key"], "macros")
        self.assertEqual(len(post.kwargs["body"]["value"]["stored"]), 1)

    def test_adds_category_and_macro_metadata(self):
        updated = MODULE.merge_layout({"macros": {"categories": [], "stored": []}})
        category = updated["macros"]["categories"][0]
        macro = updated["macros"]["stored"][0]
        self.assertEqual(category["name"], "Chamber Heating")
        self.assertEqual(macro["name"], "BED_ASSIST")
        self.assertEqual(macro["alias"], "Bed_Assist")
        self.assertTrue(macro["visible"])
        self.assertTrue(macro["disabledWhilePrinting"])
        self.assertEqual(macro["categoryId"], category["id"])

    def test_reuses_existing_category_and_is_idempotent(self):
        source = {
            "macros": {
                "categories": [{"id": "chamber", "name": "Chamber Heating"}],
                "stored": [{"name": "BED_ASSIST", "alias": "Custom", "visible": False}],
            }
        }
        once = MODULE.merge_layout(source)
        twice = MODULE.merge_layout(once)
        self.assertEqual(once, twice)
        macro = once["macros"]["stored"][0]
        self.assertEqual(macro["alias"], "Custom")
        self.assertTrue(macro["visible"])
        self.assertEqual(macro["categoryId"], "chamber")


if __name__ == "__main__":
    unittest.main()
