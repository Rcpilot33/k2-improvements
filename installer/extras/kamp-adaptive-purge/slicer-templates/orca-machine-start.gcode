; Orca / OrcaSlicer machine start gcode for K2 Plus with kamp-adaptive-purge.
;
; This conservative template always selects the installed `default` model.
; If the optional Cartographer plate workflow is installed, replace `default`
; with one of its documented model names only after calibrating that model.
;
; Companion to installer/extras/kamp-adaptive-purge. Requires:
;   1. Process tab → Quality → Advanced → Label objects (ON)
;   2. KAMP installed on the printer (sh install.sh from this feature dir)
;   3. k2-improvements START_PRINT macro (installed by the macros feature)
;
; The blocking M109 before LINE_PURGE is required — START_PRINT only sets
; the warm-up temp via M104 (non-blocking). Without M109, LINE_PURGE can
; fire while the nozzle is still heating.

START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[chamber_temperature] MATERIAL={filament_type[initial_extruder]} SURFACE=default

T[initial_extruder]
M204 S2000
M83
M109 S[nozzle_temperature_initial_layer]
LINE_PURGE
