#!/bin/sh
# Stable update migrations.  Never rename or reuse an id after release.
# id|component|detector|reason

migration_catalog() {
    cat <<'EOF'
cartographer-current-mcu-api-v1|cartographer|is_cartographer|Refresh SAFE_MOVE_Z and Z-homing connection checks for the current Cartographer MCU interface, then reload through the protected restart
cartographer-safe-move-trigger-cleanup-v1|cartographer|is_cartographer|Refresh Cartographer so an unexpected SAFE_MOVE_Z trigger finalizes the K2 motor stop before disarming probe homing, then reload through the protected restart
cartographer-active-disconnect-cleanup-v1|cartographer|is_cartographer|Refresh Cartographer active-probe disconnect cleanup and mesh abort checkpoints, then reload through the protected restart
cartographer-integration-review-v1|cartographer|is_cartographer|Refresh Cartographer integration warning cleanup and branch discovery, then reload through the protected restart
main-451901d-cartographer-temperatures|cartographer|is_cartographer|Cartographer touch-home temperature diagnostics changed
main-eb60d34-cartographer-touch-defaults|cartographer|is_cartographer|Cartographer touch calibration defaults changed
main-7fb13f9-touchscreen-offset|cartographer|is_cartographer|Cartographer touchscreen Z-offset compatibility was added
main-2377a50-live-touchscreen-offset|cartographer|is_cartographer|Live touchscreen Z-offset mirroring changed
main-a4256d7-touchscreen-sign|cartographer|is_cartographer|Touchscreen Z-offset sign handling changed
main-db05901-safe-z-ack|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z acknowledgement changed
main-76b3de6-safe-z-guard|cartographer|is_cartographer|Guarded Cartographer SAFE_MOVE_Z handling changed
main-31fe963-safe-z-queue|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z queuing changed
main-ccd093f-safe-z-complete|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z completion reporting changed
main-cb798e3-safe-z-carto-endstop|cartographer|is_cartographer|Cartographer SAFE_MOVE_Z scan-endstop protection is ready for testing
main-safe-z-carto-retreat-v1|cartographer|is_cartographer|Artificial-Z Cartographer stops now retreat the bed before preparation continues
main-safe-z-backup-retreat-v1|cartographer|is_cartographer|Artificial-Z backup stops now retreat and report completion without waiting for a timeout
main-safe-z-completion-ack-v1|cartographer|is_cartographer|Artificial-Z recovery now acknowledges the requested move without a second nozzle approach
main-safe-z-clearance-target-v1|cartographer|is_cartographer|Artificial-Z recovery now stops directly at guarded Z30 when Cartographer does not trigger
cartographer-reconnect-temperature-v1|cartographer|is_cartographer|Initialize MCU temperature sampling before configuring a probe connected after startup
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
installer-protected-motor-ready-v1|save-config-restart|is_save_config_restart|Installer code reload now requires K2 motor readiness before one firmware reset
save-config-stock-then-firmware-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG now completes its stock restart before one guarded firmware reset
save-config-stock-restart-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG restored to its stock host restart with no wrapper or firmware reset
save-config-fault-recovery-v1|save-config-restart|is_save_config_restart|SAVE_CONFIG firmware restart now also recovers failed K2 motor initialization
installer-startup-fault-recovery-v1|save-config-restart|is_save_config_restart|Installer final restart now recovers failed K2 motor initialization with one firmware reset
test-stock-case-fan-release-v1|macros|is_macros|Stock-probe pre-print now releases Creality's one-time 100% case-fan override
test-low-chamber-no-wait-v1|macros|is_macros|Chamber targets at or below 35 C no longer block pre-print or missing-mesh creation
test-low-chamber-target-policy-v2|macros|is_macros|All mesh paths now use a 2 C chamber-fan margin and keep the heater off at or below 35 C
case-fan-firmware-scope-v1|macros|is_macros|The stock pre-print case-fan release is now enabled only on confirmed affected firmware
m191-bed-assist-tolerance-v1|macros|is_macros|M191 now skips bed assistance when the chamber is within 3 C of its active-heating target
cartographer-prtouch-command-compat-v1|cartographer|is_cartographer|Cartographer now retains safe call compatibility for stock PR-Touch homing commands
cartographer-prtouch-version-report-v2|cartographer|is_cartographer|Cartographer now advertises the hardware-free PR Touch status object required for Creality's complete pre-file preparation selection
case-fan-cartographer-release-v1|macros|is_macros|The firmware-gated pre-print case-fan release now applies to Cartographer
firmware-11313-fan-switch-compat-v1|macros|is_macros|Firmware 1.1.3.13 no longer reports its missing temperature-fan switch command
virtual-sdcard-upload-boundary-v1|virtual-sdcard-guard|is_virtual_sdcard_guard|Virtual SD printing now ignores a verified multipart closing boundary only at physical EOF
case-fan-demand-aware-release-v1|macros|is_macros|The case-fan release now requires the direct 100 percent override and preserves active chamber cooling
managed-overrides-cleanup-v1|macros|is_macros|Obsolete probe, case-fan, and duplicate Cartographer Touch override entries are removed
case-fan-1152-release-v1|macros|is_macros|Firmware 1.1.5.2 now releases a direct 100 percent case-fan override at print preparation when chamber cooling is idle
cartographer-fluidd-layout-v1|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate macros now receive default Fluidd aliases and category organization
cartographer-fluidd-colors-v1|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate macro actions now receive default Fluidd colors
cartographer-fluidd-rgb-colors-v2|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer plate macro colors now use Fluidd-compatible RGB values
cartographer-fluidd-orange-calibration-v3|cartographer-plate-workflow|is_carto_plate_workflow|Cartographer calibration macro accents now use orange for clearer visual separation
cartographer-global-z-optional-v2|cartographer-plate-workflow|is_carto_plate_workflow|The global Touch-offset editor is now a separate optional feature
global-touch-offsets-live-editor-v1|global-touch-offsets|is_global_touch_offsets|The optional global Touch-offset editor uses a live Fluidd control and saves without SAVE_CONFIG
global-touch-offsets-camera-resolver-v2|global-touch-offsets|is_global_touch_offsets|Global Carto Touch Z Offsets restores Creality camera support
global-touch-offsets-category-v3|global-touch-offsets|is_global_touch_offsets|Global Carto Touch Z Offsets moves its macro into the Z Offsets category
global-touch-offsets-shared-ui-v4|global-touch-offsets|is_global_touch_offsets|Global Carto Touch Z Offsets now shares one safe Fluidd overlay with the material editor
material-z-offsets-editor-v1|material-z-offsets|is_material_z_offsets|The optional Material Z Offsets editor and automatic material registration are available
material-z-offsets-start-print-bridge-v2|material-z-offsets|is_material_z_offsets|Material Z Offsets now refreshes and verifies its START_PRINT handoff
macros-preserve-carto-surface-wrapper-v1|macros|is_macros|Macro repairs now preserve an installed Cartographer surface-selection wrapper
case-fan-runtime-state-v2|macros|is_macros|The guarded pre-print case-fan release now applies independently of firmware version
case-fan-any-direct-request-v3|macros|is_macros|Pre-print now releases any nonzero direct case-fan request while preserving chamber cooling
cartographer-default-controls-core-v1|cartographer|is_cartographer|Cartographer now installs default calibration controls while named plate selectors remain optional
m191-configurable-settings-v1|macros|is_macros|M191 bed assistance and chamber waiting settings are now configurable
m191-bed-assist-editor-v2|macros|is_macros|M191 settings can now be edited from the Fluidd Bed Assist control
axis-twist-probe-aware-range-v1|axis_twist_compensation|is_axis_twist|Axis Twist calibration now limits motion using the active probe offsets and toolhead range
axis-twist-prtouch-registration-v2|axis_twist_compensation|is_axis_twist|Stock PR Touch now releases its internal alias so the full Axis Twist module can load
axis-twist-prtouch-probe-params-v3|axis_twist_compensation|is_axis_twist|The legacy stock probe now exposes the parameter interface required by Axis Twist
screws-tilt-probe-aware-points-v1|screws_tilt_adjust|is_screws_tilt|Screws Tilt now positions the active probe near each screw while respecting toolhead boundaries
cartographer-prtouch-cold-boot-registration-v1|cartographer|is_cartographer|Cartographer now reports PR Touch preparation compatibility before Creality checks it during a cold boot
cartographer-prtouch-config-finalization-v2|cartographer|is_cartographer|Cartographer now restores PR Touch preparation compatibility before Klipper exposes its finalized configuration
case-fan-preparation-target-v4|macros|is_macros|Pre-print now releases Creality's direct case-fan request and restores the requested chamber-fan target
chamber-fan-start-print-target-v5|macros|is_macros|START_PRINT now restores the chamber-fan ceiling as soon as the requested chamber temperature is known
case-fan-immediate-start-release-v5|macros|is_macros|START_PRINT now explicitly releases Creality's direct case-fan request immediately after BOX_START_PRINT and rechecks it after nozzle cleaning
case-fan-pre-file-release-v6|macros|is_macros|Creality's pre-file case-fan request is now released before native nozzle-clean homing begins
prtouch-safe-xy-clearance-v1|macros|is_macros|Stock PR Touch now establishes Z30 clearance before the post-recovery XY homing move
prtouch-safe-xy-one-shot-v2|macros|is_macros|Stock PR Touch Z30 clearance now runs only on the first Z home after SAFE_MOVE_Z
prtouch-safe-xy-artificial-gate-v3|macros|is_macros|Stock PR Touch Z30 clearance now runs only after artificial-coordinate SAFE_MOVE_Z recovery
prtouch-safe-xy-cleanup-pass-through-v4|macros|is_macros|Stock PR Touch SAFE_MOVE_Z cleanup acknowledgements now pass through without requiring motion parameters
prtouch-safe-xy-followup-preserve-v5|macros|is_macros|Stock PR Touch safety clearance now remains armed through AI follow-up Z approaches
m141-print-target-preserve-v1|macros|is_macros|Layer-time chamber commands now preserve the configured chamber-fan ceiling during active prints
m141-command-interceptor-v2|macros|is_macros|The chamber-fan target guard now wraps Creality's macro through a compatible Klippy command interceptor
m191-circulation-cycle-v3|macros|is_macros|Bed assist now cycles low and high circulation speeds, actively cools the restored bed, and heat soaks at final print temperatures
m191-chamber-temperature-report-v1|macros|is_macros|M191 waits now report the exact chamber temperature and requested target
EOF
}
