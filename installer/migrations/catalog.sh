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
main-4b6aa14-abort-restart|abort_homing|is_abort_homing|Abort Homing installation restart handling changed
main-02272a5-screws-restart|screws_tilt_adjust|is_screws_tilt|Screws Tilt installation restart handling changed
main-22a032a-axis-restart|axis_twist_compensation|is_axis_twist|Axis Twist installation restart handling changed
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
updater-40c2982-kamp-preservation-scope-v1|kamp-adaptive-purge|is_kamp|KAMP legacy migration now keeps only user-facing settings and removes defaults imported by the updater
main-b0c7efe-cartographer-v2|cartographer|is_cartographer|Cartographer Python reload, adaptive mesh, prime-tower, and Safe Z fixes are available
main-b0c7efe-macros-v2|macros|is_macros|Validated START_PRINT, M191, mesh, and prime-tower workflow fixes are available
main-b0c7efe-save-config-v2|save-config-restart|is_save_config_restart|SAVE_CONFIG now uses the protected Klippy-code restart path
main-b0c7efe-abort-homing-v2|abort_homing|is_abort_homing|Abort Homing now reloads patched Python safely
main-b0c7efe-screws-tilt-v2|screws_tilt_adjust|is_screws_tilt|Screws Tilt installation now reloads patched Python safely
main-b0c7efe-kamp-v2|kamp-adaptive-purge|is_kamp|KAMP settings, purge safety, prime-tower scanning, and activation changed
main-b0c7efe-axis-twist-v2|axis_twist_compensation|is_axis_twist|Axis Twist installation now uses the protected Klippy-code restart
main-b0c7efe-carto-plate-v2|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate workflow generation and guidance changed
main-b0c7efe-plate-aware-v2|plate-aware-mesh|is_plate_aware_mesh|Plate-aware mesh installation and soak behavior changed
updater-kamp-interactive-refresh-v1|kamp-adaptive-purge|is_kamp|KAMP updates now offer settings and firmware-retraction questions before the shared protected restart
main-m191-chamber-circulation-v1|macros|is_macros|M191 now lowers the bed, circulates chamber air, and waits for the original bed temperature after assisted heating
main-m191-cleanup-response-v1|macros|is_macros|M191 assisted-heating cleanup messages were corrected for the K2 command parser
save-config-protected-worker-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG now uses the delayed protected restart worker
save-config-controller-stabilization-v1|save-config-restart|is_save_config_restart|Protected code reload now waits for K2 controller startup before resetting firmware
save-config-stock-restart-chain-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG now preserves the stock Klipper restart before one motor-ready firmware reset
installer-protected-motor-ready-v1|save-config-restart|is_save_config_restart|Installer code reload now requires motor readiness before one firmware reset
test-stock-case-fan-release-v1|macros|is_macros|Stock-probe pre-print now releases Creality's one-time 100% case-fan override
EOF
}
