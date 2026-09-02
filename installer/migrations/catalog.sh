#!/bin/sh
# Stable update migrations.  Never rename or reuse an id after release.
# id|component|detector|reason

migration_catalog() {
    cat <<'EOF'
main-451901d-cartographer-temperatures|cartographer|is_cartographer|Cartographer touch-home temperature diagnostics changed
main-eb60d34-cartographer-touch-defaults|cartographer|is_cartographer|Cartographer touch calibration defaults changed
main-7fb13f9-touchscreen-offset|cartographer|is_cartographer|Cartographer touchscreen Z-offset compatibility was added
main-2377a50-live-touchscreen-offset|cartographer|is_cartographer|Live touchscreen Z-offset mirroring changed
main-a4256d7-touchscreen-sign|cartographer|is_cartographer|Touchscreen Z-offset sign handling changed
main-db05901-safe-z-ack|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z acknowledgement changed
main-76b3de6-safe-z-guard|cartographer|is_cartographer|Guarded Cartographer SAFE_MOVE_Z handling changed
main-31fe963-safe-z-queue|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z queuing changed
main-ccd093f-safe-z-complete|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z completion reporting changed
main-99f5328-save-config|save-config-restart|is_save_config_restart|SAVE_CONFIG firmware-restart behavior changed
main-611cde3-save-config-guard|save-config-restart|is_save_config_restart|SAVE_CONFIG protection was expanded to every install path
main-87f0841-m191-bed-assist|macros|is_macros|M191 chamber bed assistance became reversible
main-a9c305d-m191-response|macros|is_macros|M191 response syntax was corrected
main-825ce65-chamber-target|macros|is_macros|START_PRINT and M191 now respect the requested chamber temperature
main-2b7bbd3-macro-defaults|macros|is_macros|Material and Cartographer override defaults changed
main-07a189d-carto-plate-macros|cartographer-plate-workflow|is_carto_plate_workflow|Grouped Cartographer plate-profile macros were added
main-a633065-carto-model-syntax|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer model selection syntax was corrected
main-513a452-carto-plate-workflow|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate selection workflow changed
main-b9db389-kamp-retraction|kamp-adaptive-purge|is_kamp|KAMP purge retraction handoff changed
main-7ec1fa6-kamp-install|kamp-adaptive-purge|is_kamp|KAMP installation and include wiring changed
main-d58c860-plate-mesh|plate-aware-mesh|is_plate_aware_mesh|Optional plate-aware saved meshes were added
main-c293d81-plate-soak|plate-aware-mesh|is_plate_aware_mesh|Missing saved-mesh soak became configurable
main-b80d3f7-r3men-install|r3men-bed|is_r3men_bed|R3MEN installation formatting was corrected
main-d6c9674-r3men-power|r3men-bed|is_r3men_bed|R3MEN heater-bed power configuration was corrected
integration-cartographer-runtime-v1|cartographer|is_cartographer|Cartographer Python reload, adaptive mesh, prime-tower, and Safe Z fixes are available
integration-macros-workflow-v1|macros|is_macros|Validated START_PRINT, M191, mesh, and prime-tower workflow fixes are available
integration-save-config-runtime-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG now uses the protected Klippy-code restart path
integration-abort-homing-runtime-v1|abort_homing|is_abort_homing|Abort Homing now reloads patched Python safely
integration-screws-tilt-runtime-v1|screws_tilt_adjust|is_screws_tilt|Screws Tilt installation now reloads patched Python safely
integration-kamp-workflow-v1|kamp-adaptive-purge|is_kamp|KAMP settings, purge safety, prime-tower scanning, and activation changed
integration-axis-twist-runtime-v1|axis_twist_compensation|is_axis_twist|Axis Twist installation now uses the protected Klippy-code restart
integration-carto-plate-v1|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate workflow generation and guidance changed
integration-plate-aware-v1|plate-aware-mesh|is_plate_aware_mesh|Plate-aware mesh installation and soak behavior changed
EOF
}
