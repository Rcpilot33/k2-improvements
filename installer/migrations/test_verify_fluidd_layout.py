import copy
import unittest

import verify_fluidd_layout as verifier


def configured_namespace():
    categories = [
        {"id": "carto", "name": "Cartographer Calibration"},
        {"id": "chamber", "name": "Chamber Heating"},
        {"id": "offsets", "name": "Z Offsets"},
    ]
    stored = [
        {
            "name": name,
            "categoryId": "carto",
            "visible": name not in verifier.cartographer_layout.ORCA_SELECTOR_NAMES,
        }
        for name in verifier.CARTOGRAPHER_MACROS
    ]
    stored.extend(
        [
            {"name": "BED_ASSIST", "categoryId": "chamber"},
            {"name": "GLOBAL_Z_OFFSETS_CARTO", "categoryId": "offsets"},
            {"name": "MATERIAL_Z_OFFSETS", "categoryId": "offsets"},
        ]
    )
    return {"macros": {"categories": categories, "stored": stored}}


class VerifyFluiddLayoutTests(unittest.TestCase):
    def test_all_slicer_modes_match_installer_layout(self):
        for mode in ("creality", "orca", "both"):
            namespace = verifier.cartographer_layout.merge_layout({}, True, mode)
            verifier.verify_layout(namespace, "cartographer-plate-workflow", mode)

    def test_accepts_all_supported_component_layouts(self):
        namespace = configured_namespace()
        for component in verifier.COMPONENT_MACROS:
            verifier.verify_layout(namespace, component)

    def test_rejects_missing_stored_metadata(self):
        with self.assertRaisesRegex(
            verifier.VerificationError, "BED_ASSIST has no stored Fluidd metadata"
        ):
            verifier.verify_layout({"macros": {}}, "macros")

    def test_rejects_orphaned_category(self):
        namespace = configured_namespace()
        target = next(
            item
            for item in namespace["macros"]["stored"]
            if item["name"] == "MATERIAL_Z_OFFSETS"
        )
        target["categoryId"] = "missing"
        with self.assertRaisesRegex(verifier.VerificationError, "no valid"):
            verifier.verify_layout(namespace, "material-z-offsets")

    def test_rejects_named_uncategorized_category(self):
        namespace = configured_namespace()
        namespace["macros"]["categories"].append(
            {"id": "generic", "name": "Uncategorized"}
        )
        target = next(
            item
            for item in namespace["macros"]["stored"]
            if item["name"] == "GLOBAL_Z_OFFSETS_CARTO"
        )
        target["categoryId"] = "generic"
        with self.assertRaisesRegex(verifier.VerificationError, "remains in Uncategorized"):
            verifier.verify_layout(namespace, "global-touch-offsets")

    def test_plate_workflow_requires_visible_named_selectors(self):
        namespace = configured_namespace()
        hidden = copy.deepcopy(namespace)
        target = next(
            item
            for item in hidden["macros"]["stored"]
            if item["name"] == "A12_CARTO_SELECT_TEXTURED_PEI"
        )
        target["visible"] = False
        verifier.verify_layout(hidden, "cartographer")
        with self.assertRaisesRegex(verifier.VerificationError, "incorrect selector visibility"):
            verifier.verify_layout(hidden, "cartographer-plate-workflow")

    def test_rejects_unknown_component(self):
        with self.assertRaisesRegex(verifier.VerificationError, "unsupported"):
            verifier.verify_layout(configured_namespace(), "unknown")


if __name__ == "__main__":
    unittest.main()
