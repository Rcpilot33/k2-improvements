#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.sh"
UPDATE_MENU = HERE.parent / "menus" / "update.sh"
MAIN_MENU = HERE.parent / "menus" / "main.sh"
FEATURE_DETECTORS = HERE.parent / "detect" / "features.sh"

KNOWN_COMPONENTS = {
    "cartographer",
    "macros",
    "save-config-restart",
    "abort_homing",
    "screws_tilt_adjust",
    "kamp-adaptive-purge",
    "r3men-bed",
    "axis_twist_compensation",
    "cartographer-plate-workflow",
    "plate-aware-mesh",
}

EXPECTED_DETECTORS = {
    "cartographer": "is_cartographer",
    "macros": "is_macros",
    "save-config-restart": "is_save_config_restart",
    "abort_homing": "is_abort_homing",
    "screws_tilt_adjust": "is_screws_tilt",
    "kamp-adaptive-purge": "is_kamp",
    "r3men-bed": "is_r3men_bed",
    "axis_twist_compensation": "is_axis_twist",
    "cartographer-plate-workflow": "is_carto_plate_workflow",
    "plate-aware-mesh": "is_plate_aware_mesh",
}


def entries():
    parsed = []
    for raw in CATALOG.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^[a-z0-9][^|]*\|", raw):
            continue
        migration_id, component, detector, reason = raw.split("|", 3)
        parsed.append((migration_id, component, detector, reason))
    return parsed


def recommended(installed, completed=frozenset()):
    return {
        component
        for migration_id, component, _detector, _reason in entries()
        if component in installed and migration_id not in completed
    }


class MigrationCatalogTests(unittest.TestCase):
    def test_ids_are_unique_and_entries_are_complete(self):
        catalog = entries()
        self.assertGreater(len(catalog), 20)
        ids = [item[0] for item in catalog]
        self.assertEqual(len(ids), len(set(ids)))
        for migration_id, component, detector, reason in catalog:
            self.assertTrue(migration_id)
            self.assertIn(component, KNOWN_COMPONENTS)
            self.assertEqual(detector, EXPECTED_DETECTORS[component])
            self.assertTrue(reason)

    def test_cartographer_legacy_install_filters_absent_extras(self):
        installed = {
            "cartographer",
            "macros",
            "save-config-restart",
            "abort_homing",
            "screws_tilt_adjust",
            "kamp-adaptive-purge",
            "r3men-bed",
        }
        self.assertEqual(recommended(installed), installed)
        self.assertNotIn("axis_twist_compensation", recommended(installed))
        self.assertNotIn("cartographer-plate-workflow", recommended(installed))
        self.assertNotIn("plate-aware-mesh", recommended(installed))

    def test_stock_install_includes_only_stock_applicable_extras(self):
        installed = {
            "macros",
            "save-config-restart",
            "abort_homing",
            "screws_tilt_adjust",
            "kamp-adaptive-purge",
            "plate-aware-mesh",
        }
        self.assertEqual(recommended(installed), installed)
        self.assertNotIn("cartographer", recommended(installed))
        self.assertNotIn("cartographer-plate-workflow", recommended(installed))

    def test_completed_ids_are_not_recommended_again(self):
        macro_ids = {
            migration_id
            for migration_id, component, _detector, _reason in entries()
            if component == "macros"
        }
        installed = {"macros", "save-config-restart"}
        self.assertEqual(
            recommended(installed, completed=macro_ids), {"save-config-restart"}
        )

    def test_integration_promotion_recommends_only_installed_changed_components(self):
        installed = {
            "cartographer",
            "macros",
            "save-config-restart",
            "abort_homing",
            "screws_tilt_adjust",
            "kamp-adaptive-purge",
            "r3men-bed",
        }
        completed_before_promotion = {
            migration_id
            for migration_id, _component, _detector, _reason in entries()
            if not migration_id.startswith("main-b0c7efe-")
        }
        self.assertEqual(
            recommended(installed, completed=completed_before_promotion),
            {
                "cartographer",
                "macros",
                "save-config-restart",
                "abort_homing",
                "screws_tilt_adjust",
                "kamp-adaptive-purge",
            },
        )

    def test_release_catalog_does_not_reuse_test_branch_ids(self):
        self.assertFalse(
            any(migration_id.startswith("integration-") for migration_id, *_ in entries())
        )

    def test_every_catalog_component_has_a_direct_dispatch_and_label(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        for component in KNOWN_COMPONENTS:
            self.assertIn(component, menu)

    def test_main_menu_surfaces_pending_update_actions(self):
        menu = MAIN_MENU.read_text(encoding="utf-8")
        self.assertIn("migration_pending_component_count", menu)
        self.assertIn("ACTION(S) PENDING", menu)
        self.assertIn("NO ACTIONS PENDING", menu)
        self.assertIn("Update installer / apply updates", menu)

    def test_update_plan_keeps_terminal_input_available_to_installers(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn("read -r component <&3", menu)
        self.assertIn('done 3< "$components_file"', menu)

    def test_cartographer_refresh_records_save_config_dependency(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn("migration_record_refreshed_component", menu)
        self.assertRegex(
            menu,
            r"cartographer\) dependency=save-config-restart",
        )

    def test_save_config_detector_recognizes_stock_restart_chain(self):
        detectors = FEATURE_DETECTORS.read_text(encoding="utf-8")
        match = re.search(
            r"is_save_config_restart\(\) \{(?P<body>.*?)\n\}",
            detectors,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("_schedule_post_restart_firmware_reset", body)
        self.assertIn("save_config_restart\\.sh", body)
        self.assertIn("request_restart('restart')", body)

    def test_save_config_tracks_controller_stabilization_update(self):
        self.assertIn(
            "save-config-controller-stabilization-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_save_config_tracks_stock_restart_chain_update(self):
        self.assertIn(
            "save-config-stock-restart-chain-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_installer_tracks_motor_ready_restart_update(self):
        self.assertIn(
            "installer-protected-motor-ready-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_save_config_tracks_validated_motor_e_recovery(self):
        self.assertIn(
            "save-config-motor-e-recovery-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_save_config_tracks_full_callback_recovery(self):
        self.assertIn(
            "save-config-full-callback-recovery-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_macros_track_passive_chamber_no_wait_update(self):
        self.assertIn(
            "test-low-chamber-no-wait-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_low_chamber_target_policy_update(self):
        self.assertIn(
            "test-low-chamber-target-policy-v2",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )


if __name__ == "__main__":
    unittest.main()
