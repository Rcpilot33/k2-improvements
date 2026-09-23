#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.sh"
UPDATE_MENU = HERE.parent / "menus" / "update.sh"
MAIN_MENU = HERE.parent / "menus" / "main.sh"

KNOWN_COMPONENTS = {
    "cartographer",
    "macros",
    "save-config-restart",
    "virtual-sdcard-guard",
    "abort_homing",
    "screws_tilt_adjust",
    "kamp-adaptive-purge",
    "r3men-bed",
    "axis_twist_compensation",
    "cartographer-plate-workflow",
    "global-touch-offsets",
    "material-z-offsets",
    "plate-aware-mesh",
}

EXPECTED_DETECTORS = {
    "cartographer": "is_cartographer",
    "macros": "is_macros",
    "save-config-restart": "is_save_config_restart",
    "virtual-sdcard-guard": "is_virtual_sdcard_guard",
    "abort_homing": "is_abort_homing",
    "screws_tilt_adjust": "is_screws_tilt",
    "kamp-adaptive-purge": "is_kamp",
    "r3men-bed": "is_r3men_bed",
    "axis_twist_compensation": "is_axis_twist",
    "cartographer-plate-workflow": "is_carto_plate_workflow",
    "global-touch-offsets": "is_global_touch_offsets",
    "material-z-offsets": "is_material_z_offsets",
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
    def test_safe_move_trigger_cleanup_is_offered_once(self):
        update_id = "cartographer-safe-move-trigger-cleanup-v1"
        catalog_ids = {entry[0] for entry in entries()}
        self.assertIn(update_id, catalog_ids)
        previously_completed = catalog_ids - {update_id}
        self.assertEqual(
            recommended({"cartographer", "macros"}, previously_completed),
            {"cartographer"},
        )
        self.assertEqual(recommended({"macros"}, previously_completed), set())
        self.assertEqual(recommended({"cartographer"}, catalog_ids), set())

    def test_current_cartographer_mcu_api_fix_is_offered_once(self):
        update_id = "cartographer-current-mcu-api-v1"
        catalog_ids = {entry[0] for entry in entries()}
        self.assertIn(update_id, catalog_ids)
        previously_completed = catalog_ids - {update_id}
        self.assertEqual(
            recommended({"cartographer", "macros"}, previously_completed),
            {"cartographer"},
        )
        self.assertEqual(recommended({"macros"}, previously_completed), set())
        self.assertEqual(recommended({"cartographer"}, catalog_ids), set())

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
        self.assertNotIn("global-touch-offsets", recommended(installed))
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

    def test_installer_tracks_motor_ready_restart_update(self):
        self.assertIn(
            "installer-protected-motor-ready-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "save-config-restart"
            },
        )

    def test_every_catalog_component_has_a_direct_dispatch_and_label(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        for component in KNOWN_COMPONENTS:
            self.assertIn(component, menu)

    def test_main_menu_surfaces_pending_update_actions(self):
        menu = MAIN_MENU.read_text(encoding="utf-8")
        self.assertIn("migration_pending_component_count", menu)
        self.assertIn("ACTION(S) PENDING", menu)
        self.assertIn("INSTALLER UPDATE AVAILABLE", menu)
        self.assertIn("UP TO DATE", menu)
        self.assertIn("REMOTE CHECK UNAVAILABLE", menu)
        self.assertIn("ls-remote --heads origin", menu)
        self.assertIn("Update installer / apply updates", menu)

    def test_update_plan_keeps_terminal_input_available_to_installers(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn("read -r component <&3", menu)
        self.assertIn('done 3< "$components_file"', menu)

    def test_macros_repairs_explicitly_require_a_code_restart(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        restart_case = re.search(
            r"migration_component_restart_kind\(\) \{(.*?)\n\}",
            menu,
            re.DOTALL,
        )
        self.assertIsNotNone(restart_case)
        self.assertRegex(
            restart_case.group(1),
            r"(?:^|\|)macros(?:\||\))[^\n]*\n\s*echo code",
        )

    def test_updater_can_back_up_and_restore_tracked_local_edits(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn("migration_restore_tracked_checkout", menu)
        self.assertIn("status --porcelain --untracked-files=no", menu)
        self.assertIn("diff --binary HEAD --", menu)
        self.assertIn("reset --hard HEAD", menu)
        self.assertIn("Untracked files are kept", menu)
        self.assertIn("migration_restore_tracked_checkout || return 1", menu)

    def test_updater_can_confirm_and_recover_a_diverged_checkout(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn('git pull --ff-only origin "$branch"', menu)
        self.assertIn("migration_replace_diverged_checkout", menu)
        self.assertIn("repository-refresh.sh", menu)
        self.assertIn("Any previous repository recovery backup will be deleted", menu)
        self.assertIn("including Git history and local files", menu)
        self.assertIn('migration_replace_diverged_checkout "$branch"', menu)

    def test_cartographer_refresh_records_shared_python_dependencies(self):
        menu = UPDATE_MENU.read_text(encoding="utf-8")
        self.assertIn("migration_record_refreshed_component", menu)
        self.assertIn(
            "dependencies='save-config-restart virtual-sdcard-guard'", menu
        )

    def test_virtual_sdcard_guard_is_a_direct_component(self):
        self.assertIn(
            "virtual-sdcard-upload-boundary-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "virtual-sdcard-guard"
            },
        )

    def test_macros_track_demand_aware_case_fan_release(self):
        self.assertIn(
            "case-fan-demand-aware-release-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_managed_overrides_cleanup(self):
        self.assertIn(
            "managed-overrides-cleanup-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_1152_case_fan_release(self):
        self.assertIn(
            "case-fan-1152-release-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
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

    def test_macros_track_case_fan_firmware_scope_update(self):
        self.assertIn(
            "case-fan-firmware-scope-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_bed_assist_tolerance_update(self):
        self.assertIn(
            "m191-bed-assist-tolerance-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_material_offsets_track_start_print_handoff_update(self):
        self.assertIn(
            "material-z-offsets-start-print-bridge-v2",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "material-z-offsets"
            },
        )

    def test_macros_track_surface_wrapper_preservation(self):
        self.assertIn(
            "macros-preserve-carto-surface-wrapper-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_firmware_independent_case_fan_release(self):
        self.assertIn(
            "case-fan-runtime-state-v2",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_any_nonzero_case_fan_release(self):
        self.assertIn(
            "case-fan-any-direct-request-v3",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_configurable_m191_settings(self):
        self.assertIn(
            "m191-configurable-settings-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_m191_circulation_cycle(self):
        self.assertIn(
            "m191-circulation-cycle-v3",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_m191_chamber_temperature_report(self):
        self.assertIn(
            "m191-chamber-temperature-report-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_immediate_case_fan_release(self):
        self.assertIn(
            "case-fan-immediate-start-release-v5",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_prtouch_safe_xy_cleanup_pass_through(self):
        self.assertIn(
            "prtouch-safe-xy-cleanup-pass-through-v4",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_macros_track_prtouch_safe_xy_followup_preservation(self):
        self.assertIn(
            "prtouch-safe-xy-followup-preserve-v5",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "macros"
            },
        )

    def test_axis_twist_tracks_probe_aware_calibration_range(self):
        self.assertIn(
            "axis-twist-probe-aware-range-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "axis_twist_compensation"
            },
        )

    def test_axis_twist_tracks_prtouch_registration_release(self):
        self.assertIn(
            "axis-twist-prtouch-registration-v2",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "axis_twist_compensation"
            },
        )

    def test_axis_twist_tracks_prtouch_probe_parameter_bridge(self):
        self.assertIn(
            "axis-twist-prtouch-probe-params-v3",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "axis_twist_compensation"
            },
        )

    def test_screws_tilt_tracks_probe_aware_points(self):
        self.assertIn(
            "screws-tilt-probe-aware-points-v1",
            {
                migration_id
                for migration_id, component, _detector, _reason in entries()
                if component == "screws_tilt_adjust"
            },
        )

if __name__ == "__main__":
    unittest.main()
