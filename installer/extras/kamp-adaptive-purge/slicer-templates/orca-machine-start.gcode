; Legacy Orca KAMP template: explicit default surface, retained for compatibility.
; Prefer one of the four orca-start-material-* templates; see README.md.
M140 S0
M104 S0
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL={filament_type[initial_tool]} SURFACE=default
T[initial_no_support_extruder]
M204 S2000
M83
M109 S[nozzle_temperature_initial_layer]
LINE_PURGE
