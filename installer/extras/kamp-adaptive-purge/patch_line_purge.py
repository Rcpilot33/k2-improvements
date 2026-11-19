#!/usr/bin/env python3
"""Create the K2 Plus-compatible LINE_PURGE macro from upstream KAMP."""

import os
import re
import sys
import tempfile
from pathlib import Path


MARKER = "k2-improvements: balance LINE_PURGE retraction before slicer travel"
BOUNDARY_MARKER = "k2-improvements: constrain the complete LINE_PURGE motion path"
WAIT_MARKER = "k2-improvements: wait cooperatively for first-layer geometry"


WAIT_WRAPPER = r'''[gcode_macro LINE_PURGE]
description: K2-safe KAMP purge with first-layer synchronization
gcode:
    # k2-improvements: wait cooperatively for first-layer geometry
    PRIME_TOWER_WAIT
    _KAMP_LINE_PURGE {rawparams}

'''


FRONT_PURGE = r'''
[gcode_macro _KAMP_FRONT_CENTER_PURGE]
description: K2 Plus CP-style front-center fallback for a full print area
gcode:
    {% set flow = params.FLOW | default(12) | float %}
    {% set tip = params.TIP | default(0) | float %}
    {% set min_y = params.OBJECT_MIN_Y | default(-1) | float %}
    {% set lo = printer.toolhead.axis_minimum %}
    {% set hi = printer.toolhead.axis_maximum %}
    {% if 'x' not in printer.toolhead.homed_axes or 'y' not in printer.toolhead.homed_axes or 'z' not in printer.toolhead.homed_axes %}
        {action_respond_info("KAMP front-center fallback requires XYZ homed; purge skipped.")}
    {% elif not (lo.x <= 150 and hi.x >= 205 and lo.y <= -1 and hi.y >= -1 and lo.z <= 0 and hi.z >= 3) %}
        {action_respond_info("KAMP has no adaptive purge space and the CP front-center fallback requires X150..205, Y=-1, Z0..3 within configured travel; purge skipped.")}
    {% elif not (min_y >= 0 and flow > 0 and flow <= 100 and tip >= 0 and tip <= 100) %}
        {action_respond_info("KAMP front-center fallback requires a print footprint at Y>=0 and valid flow/tip settings; purge skipped.")}
    {% elif not printer.extruder.can_extrude %}
        {action_respond_info("Heat the nozzle with M109 before the KAMP front-center fallback; purge skipped.")}
    {% elif printer.configfile.settings.extruder.max_extrude_cross_section | float < 0.87 %}
        {action_respond_info("KAMP front-center fallback requires max_extrude_cross_section of at least 0.87; purge skipped.")}
    {% else %}
    {action_respond_info("KAMP: no adaptive corridor; using CP-style front-center purge at Y=-1 (outside the active mesh if necessary).")}
    SAVE_GCODE_STATE NAME=KAMP_Front_Center_State
    G90
    M83
    # Return from the CFS wipe before any Z or cross-bed travel.
    {% set pos = printer.toolhead.position %}
    {% if pos.y > hi.y %}
        G0 Y{hi.y - 2.0} F12000
    {% elif pos.y < lo.y %}
        G0 Y{lo.y + 2.0} F12000
    {% endif %}
    G1 Z3 F600
    G1 X150 Y-1 F30000
    {% if tip > 0 %}
        G1 E{tip} F300
    {% endif %}
    G1 Z0.3 F1200
    # CP 7.3 line geometry; use KAMP flow_rate in place of the slicer variable.
    G1 X175 E9 F{flow / (24.0 / 20.0) * 60}
    G1 X180 E0.3742 F{flow / (0.3 * 0.5) / 4 * 60}
    G1 X185 E0.3742 F{flow / (0.3 * 0.5) * 60}
    G1 X190 E0.3742 F{flow / (0.3 * 0.5) / 4 * 60}
    G1 X195 E0.3742 F{flow / (0.3 * 0.5) * 60}
    G1 X200 E0.3742 F{flow / (0.3 * 0.5) / 4 * 60}
    G1 X201 Z0
    G1 X205
    G1 Z1 F600
    # Restore XYZ/E modes and the slicer's extrusion origin without moving back.
    RESTORE_GCODE_STATE NAME=KAMP_Front_Center_State MOVE=0
    {% endif %}
'''


BOUNDARY_CALCULATIONS = r'''    # k2-improvements: constrain the complete LINE_PURGE motion path
    # Include the 10mm string-break move when selecting a safe corridor.
    {% set boundary_inset = 0.5 | float %}
    {% set path_length = purge_amount + 10.0 %}
    {% set object_points = printer.exclude_object.objects | map(attribute='polygon') | sum(start=[]) %}
    {% set footprint_points = printer.prime_tower.polygon if printer.prime_tower is defined and printer.prime_tower.detected else [] %}
    {% set all_points = object_points + footprint_points %}
    {% set stock_purge_fallback = printer["gcode_macro _KAMP_Settings"].stock_purge_fallback | int %}
    {% set object_x_min = (all_points | map(attribute=0) | min | default(0)) | float %}
    {% set object_x_max = (all_points | map(attribute=0) | max | default(0)) | float %}
    {% set object_y_min = (all_points | map(attribute=1) | min | default(0)) | float %}
    {% set object_y_max = (all_points | map(attribute=1) | max | default(0)) | float %}

    # Start with the configured machine envelope. If a real mesh is active,
    # intersect it with that envelope so the purge remains on the meshed area.
    {% set axis_x_min = printer.toolhead.axis_minimum.x | float %}
    {% set axis_x_max = printer.toolhead.axis_maximum.x | float %}
    {% set axis_y_min = printer.toolhead.axis_minimum.y | float %}
    {% set axis_y_max = printer.toolhead.axis_maximum.y | float %}
    {% set axis_z_min = printer.toolhead.axis_minimum.z | float %}
    {% set axis_z_max = printer.toolhead.axis_maximum.z | float %}
    {% set stock_path_fits_machine = axis_x_min <= 0.0 and axis_x_max >= 150.0
        and axis_y_min <= 0.0 and axis_y_max >= 150.0
        and axis_z_min <= 0.2 and axis_z_max >= 3.0 %}
    {% set mesh_active = printer.bed_mesh is defined
        and (printer.bed_mesh.mesh_max[0] | float) > (printer.bed_mesh.mesh_min[0] | float)
        and (printer.bed_mesh.mesh_max[1] | float) > (printer.bed_mesh.mesh_min[1] | float) %}
    {% set safe_x_min = ([axis_x_min, (printer.bed_mesh.mesh_min[0] | float)] | max) + boundary_inset if mesh_active else axis_x_min + boundary_inset %}
    {% set safe_x_max = ([axis_x_max, (printer.bed_mesh.mesh_max[0] | float)] | min) - boundary_inset if mesh_active else axis_x_max - boundary_inset %}
    {% set safe_y_min = ([axis_y_min, (printer.bed_mesh.mesh_min[1] | float)] | max) + boundary_inset if mesh_active else axis_y_min + boundary_inset %}
    {% set safe_y_max = ([axis_y_max, (printer.bed_mesh.mesh_max[1] | float)] | min) - boundary_inset if mesh_active else axis_y_max - boundary_inset %}

    {% set x_start_min = safe_x_min %}
    {% set x_start_max = safe_x_max - path_length %}
    {% set y_start_min = safe_y_min %}
    {% set y_start_max = safe_y_max - path_length %}
    {% set ideal_x_start = ((object_x_min + object_x_max) / 2.0) - (purge_amount / 2.0) %}
    {% set ideal_y_start = ((object_y_min + object_y_max) / 2.0) - (purge_amount / 2.0) %}
    {% set x_start = ([[ideal_x_start, x_start_min] | max, x_start_max] | min) %}
    {% set y_start = ([[ideal_y_start, y_start_min] | max, y_start_max] | min) %}

    {% set front_y = object_y_min - purge_margin %}
    {% set left_x = object_x_min - purge_margin %}
    {% set rear_y = object_y_max + purge_margin %}
    {% set right_x = object_x_max + purge_margin %}
    {% set horizontal_fits = x_start_max >= x_start_min %}
    {% set vertical_fits = y_start_max >= y_start_min %}
    {% set front_fits = horizontal_fits and front_y >= safe_y_min and front_y <= safe_y_max and front_y < object_y_min %}
    {% set left_fits = vertical_fits and left_x >= safe_x_min and left_x <= safe_x_max and left_x < object_x_min %}
    {% set rear_fits = horizontal_fits and rear_y >= safe_y_min and rear_y <= safe_y_max and rear_y > object_y_max %}
    {% set right_fits = vertical_fits and right_x >= safe_x_min and right_x <= safe_x_max and right_x > object_x_max %}

    # Prefer the familiar front/left locations, then use rear/right if needed.
    {% set purge_side = 'front' if front_fits else ('left' if left_fits else ('rear' if rear_fits else ('right' if right_fits else 'none'))) %}
    {% set horizontal_purge = purge_side in ['front', 'rear'] %}
    {% set purge_start_x = x_start if horizontal_purge else (left_x if purge_side == 'left' else right_x) %}
    {% set purge_start_y = (front_y if purge_side == 'front' else rear_y) if horizontal_purge else y_start %}
    {% set purge_end_x = purge_start_x + purge_amount if horizontal_purge else purge_start_x %}
    {% set purge_end_y = purge_start_y if horizontal_purge else purge_start_y + purge_amount %}
    {% set break_end_x = purge_end_x + 10.0 if horizontal_purge else purge_end_x %}
    {% set break_end_y = purge_end_y if horizontal_purge else purge_end_y + 10.0 %}
'''


BOUNDARY_EXECUTION = r'''    # Calculate purge speed
    {% set purge_move_speed = (flow_rate / 5.0) * 60 | float %}

    {% set settings_valid = purge_height > 0
        and tip_distance >= 0
        and purge_margin > 0
        and purge_amount > 0
        and flow_rate > 0
        and (purge_height * 2.0) <= (printer.toolhead.axis_maximum.z | float) %}

    {% if not settings_valid %}
        {action_respond_info("KAMP boundary safety: one or more purge settings are invalid; adaptive purge skipped.")}
    {% elif 'x' not in printer.toolhead.homed_axes or 'y' not in printer.toolhead.homed_axes or 'z' not in printer.toolhead.homed_axes %}
        {action_respond_info("KAMP boundary safety: XYZ must be homed before LINE_PURGE; adaptive purge skipped.")}
    {% elif all_points | length == 0 %}
        {% if stock_purge_fallback == 1 and stock_path_fits_machine %}
            {action_respond_info("WARNING: No exclude-object geometry is available. Running the enabled stock-style front-left purge fallback; it cannot account for print placement and may be outside the active mesh.")}
            SAVE_GCODE_STATE NAME=KAMP_Stock_Fallback_State
            G90
            M83
            G1 Z3 F600
            G1 Y150 F12000
            G1 X0 F12000
            G1 Z0.2 F600
            G1 X0 Y150 F6000
            G1 E0.8 F300
            G1 X0 Y0 E9 F2400
            G1 X150 Y0 E9 F2400
            G92 E0
            G1 Z1 F600
            RESTORE_GCODE_STATE NAME=KAMP_Stock_Fallback_State MOVE=0
        {% elif stock_purge_fallback == 1 %}
            {action_respond_info("KAMP stock purge fallback is enabled, but its X0..150/Y0..150/Z0.2..3 path is outside the configured machine limits; purge skipped.")}
        {% else %}
            {action_respond_info("KAMP boundary safety: no exclude-object geometry is available and stock purge fallback is disabled; purge skipped.")}
        {% endif %}
    {% elif purge_side == 'none' %}
        # Known full-bed footprint: use the CP front-center line by default.
        _KAMP_FRONT_CENTER_PURGE FLOW={flow_rate} TIP={tip_distance} OBJECT_MIN_Y={object_y_min}
    {% elif cross_section < 5 %}
        {action_respond_info("[Extruder] max_extrude_cross_section is insufficient for purge, please set it to 5 or greater. Purge skipped.")}
    {% else %}
        {% if verbose_enable == True %}
            {action_respond_info("KAMP boundary safety selected the {} side; complete path ({:.1f},{:.1f}) to ({:.1f},{:.1f}) is inside X[{:.1f},{:.1f}] Y[{:.1f},{:.1f}].".format(
                purge_side, purge_start_x, purge_start_y, break_end_x, break_end_y,
                safe_x_min, safe_x_max, safe_y_min, safe_y_max))}
            {action_respond_info("Moving filament tip {}mms".format(tip_distance))}
        {% endif %}
        {% if printer.firmware_retraction is defined %}
            {action_respond_info("KAMP purge is using firmware retraction.")}
        {% else %}
            {action_respond_info("KAMP purge is not using firmware retraction, it is recommended to configure it.")}
        {% endif %}
        {action_respond_info("KAMP purge starting at {:.1f}, {:.1f} and purging {}mm of filament, requested flow rate is {}mm3/s.".format(
            purge_start_x, purge_start_y, purge_amount, flow_rate))}

        SAVE_GCODE_STATE NAME=Prepurge_State
        G92 E0
        # The CFS wipe may leave Y just beyond the normal travel limit.
        # Move straight into the machine envelope before crossing to the purge.
        {% set pos = printer.toolhead.position %}
        G90
        {% if pos.y > axis_y_max %}
            G0 Y{axis_y_max - 2.0} F{travel_speed}
        {% elif pos.y < axis_y_min %}
            G0 Y{axis_y_min + 2.0} F{travel_speed}
        {% endif %}
        G0 X{purge_start_x} Y{purge_start_y} F{travel_speed}
        G0 Z{purge_height}
        M83
        G1 E{tip_distance} F{purge_move_speed}
        {% if horizontal_purge %}
            G1 X{purge_end_x} E{purge_amount} F{purge_move_speed}
            {RETRACT}
            G0 X{break_end_x} F{travel_speed}  # Rapid move to break string
        {% else %}
            G1 Y{purge_end_y} E{purge_amount} F{purge_move_speed}
            {RETRACT}
            G0 Y{break_end_y} F{travel_speed}  # Rapid move to break string
        {% endif %}
        G92 E0
        M82
        G0 Z{purge_height * 2} F{travel_speed}
        RESTORE_GCODE_STATE NAME=Prepurge_State
    {% endif %}
'''


def fail(message):
    print(f"E: {message}", file=sys.stderr)
    raise SystemExit(1)


def quote_firmware_commands(text):
    assignments = (
        (
            "{% set RETRACT = G10 | string %}",
            "{% set RETRACT = 'G10' | string %}",
        ),
        (
            "{% set UNRETRACT = G11 | string %}",
            "{% set UNRETRACT = 'G11' | string %}",
        ),
    )

    for unquoted, quoted in assignments:
        if unquoted in text:
            text = text.replace(unquoted, quoted)
        elif quoted not in text:
            fail(f"upstream LINE_PURGE no longer contains a recognized assignment: {unquoted}")

    return text


def harden_boundaries(text):
    calculation_start = "    # Calculate purge origins and centers from objects\n"
    speed_start = "    # Calculate purge speed\n"
    execution_start = "    {% if cross_section < 5 %}\n"

    if BOUNDARY_MARKER in text:
        return text
    if text.count(calculation_start) != 1 or text.count(speed_start) != 1:
        fail("upstream LINE_PURGE calculation layout is not recognized")

    prefix, remainder = text.split(calculation_start, 1)
    _, speed_and_execution = remainder.split(speed_start, 1)
    if speed_and_execution.count(execution_start) != 1:
        fail("upstream LINE_PURGE execution layout is not recognized")
    _, old_execution = speed_and_execution.split(execution_start, 1)
    if "[gcode_macro" in old_execution or not old_execution.rstrip().endswith("{% endif %}"):
        fail("upstream LINE_PURGE has an unrecognized execution tail")
    if old_execution.count("Rapid move to break string") != 2:
        fail("upstream LINE_PURGE no longer has the two verified purge paths")

    result = prefix + BOUNDARY_CALCULATIONS + "\n" + BOUNDARY_EXECUTION
    if result.count(BOUNDARY_MARKER) != 1:
        fail("the installed macro is missing its K2 boundary-safety marker")
    return result


def add_balancing_unretracts(text):
    lines = text.splitlines(keepends=True)
    output = []
    break_moves = 0
    balanced_moves = 0

    for index, line in enumerate(lines):
        output.append(line)
        if "Rapid move to break string" not in line:
            continue

        break_moves += 1
        next_command = ""
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if stripped and not stripped.startswith("#"):
                next_command = stripped
                break

        if next_command.startswith("{UNRETRACT}"):
            balanced_moves += 1
            continue

        indent = re.match(r"\s*", line).group(0)
        newline = "\r\n" if line.endswith("\r\n") else "\n"
        output.append(f"{indent}{{UNRETRACT}}  # {MARKER}{newline}")
        balanced_moves += 1

    if break_moves != 2:
        fail(
            "expected two upstream rapid string-break moves, "
            f"found {break_moves}; refusing to install an unverified macro"
        )
    if balanced_moves != break_moves:
        fail("not every upstream string-break move has a balancing unretract")

    result = "".join(output)
    command_count = sum(
        1 for line in result.splitlines() if line.strip().startswith("{UNRETRACT}")
    )
    if command_count != break_moves:
        fail(
            f"expected {break_moves} UNRETRACT commands after patching, "
            f"found {command_count}"
        )
    if result.count(MARKER) != break_moves:
        fail("the installed macro is missing its K2 compatibility markers")

    return result


def add_prime_tower_wait_wrapper(text):
    """Defer rendering the purge calculation until first-layer scan finishes.

    Klipper renders an entire gcode_macro before executing its first command.
    A wrapper is therefore required: PRIME_TOWER_WAIT runs first, and the
    renamed implementation is rendered only after that cooperative wait.
    """
    if WAIT_MARKER in text:
        if text.count(WAIT_MARKER) != 1:
            fail("installed LINE_PURGE has duplicate prime-tower wait markers")
        return text

    header = "[gcode_macro LINE_PURGE]"
    internal_header = "[gcode_macro _KAMP_LINE_PURGE]"
    if text.count(header) != 1 or internal_header in text:
        fail("LINE_PURGE macro header is not recognized")
    return WAIT_WRAPPER + text.replace(header, internal_header, 1) + FRONT_PURGE


def write_atomic(destination, text, mode):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=str(destination.parent),
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        temp_name = handle.name
        handle.write(text)

    try:
        os.chmod(temp_name, mode)
        os.replace(temp_name, destination)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main():
    if len(sys.argv) != 3:
        fail(f"usage: {Path(sys.argv[0]).name} SOURCE DESTINATION")

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    if not source.is_file():
        fail(f"upstream LINE_PURGE source not found: {source}")

    text = source.read_text(encoding="utf-8")
    text = quote_firmware_commands(text)
    text = harden_boundaries(text)
    text = add_balancing_unretracts(text)
    text = add_prime_tower_wait_wrapper(text)

    # os.replace() must target the installed file, not an older upstream symlink.
    if destination.is_symlink():
        destination.unlink()
    write_atomic(destination, text, source.stat().st_mode & 0o777)
    print(f"I: installed corrected LINE_PURGE macro at {destination}")


if __name__ == "__main__":
    main()
