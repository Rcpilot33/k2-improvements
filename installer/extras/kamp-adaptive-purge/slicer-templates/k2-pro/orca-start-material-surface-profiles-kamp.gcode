; OrcaSlicer K2 Pro machine start G-code
; SET PRINT AREA MIN AND MAX COORDINATES TO ENABLE ADAPTIVE PROBING
; MINX = {first_layer_print_min[0]}
; MINY = {first_layer_print_min[1]}
; MAXX = {first_layer_print_max[0]}
; MAXY = {first_layer_print_max[1]}
M140 S0
M104 S0
{if curr_bed_type == "Cool Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=orca_cool_plate
{elsif curr_bed_type == "Engineering Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=orca_engineering
{elsif curr_bed_type == "High Temp Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=high_temp
{elsif curr_bed_type == "Textured PEI Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=textured_pei
{elsif curr_bed_type == "Textured Cool Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=orca_textured_cool
{elsif curr_bed_type == "Supertack Plate"}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=orca_supertack
{else}
START_PRINT EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[overall_chamber_temperature] MATERIAL="{filament_type[initial_tool]}" SURFACE=default
{endif}
T[initial_no_support_extruder]
M109 S[nozzle_temperature_initial_layer]
M204 S2000
G1 Z3 F600
M83
LINE_PURGE
