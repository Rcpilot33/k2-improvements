#!/bin/ash
set -e

CFG="/mnt/UDISK/printer_data/config/printer.cfg"
BACKUP="${CFG}.r3men-bed.$(date +%Y%m%d-%H%M%S).bak"

echo "#### Installing R3MEN bed thermistor profile ..."

if [ ! -f "$CFG" ]; then
    echo "E: printer.cfg not found at $CFG"
    exit 1
fi

cp "$CFG" "$BACKUP"
echo "I: backup created: $BACKUP"

python3 - "$CFG" <<'PY'
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
text = cfg_path.read_text()

thermistor_block = """[thermistor R3men_bed]
temperature1: 25
resistance1: 100000
temperature2: 97
resistance2: 1385
temperature3: 248
resistance3: 165"""

if "[thermistor R3men_bed]" not in text:
    # Add thermistor block before heater_bed if possible, otherwise append.
    marker = "[heater_bed]"
    if marker in text:
        before, after = text.split(marker, 1)
        text = before.rstrip() + "\n\n" + thermistor_block + "\n\n" + marker + after
    else:
        text = text.rstrip() + "\n\n" + thermistor_block + "\n"

lines = text.splitlines()
out = []
in_bed = False
seen_sensor = False
seen_max_power = False

for line in lines:
    stripped = line.strip()

    if stripped.startswith("[") and stripped.endswith("]"):
        if in_bed:
            # Keep generated heater_bed settings inside the section rather
            # than after its trailing separator lines. Restore one blank line
            # before the following section for readable formatting.
            while out and not out[-1].strip():
                out.pop()
            if not seen_sensor:
                out.append("sensor_type: R3men_bed")
            if not seen_max_power:
                out.append("max_power: 0.8")
            out.append("")
        in_bed = stripped == "[heater_bed]"
        seen_sensor = False
        seen_max_power = False
        out.append(line)
        continue

    if in_bed:
        if stripped.startswith("sensor_type:"):
            value = stripped.split(":", 1)[1].strip()
            if value == "R3men_bed":
                if not seen_sensor:
                    out.append("sensor_type: R3men_bed")
                    seen_sensor = True
                continue
            else:
                if not seen_sensor:
                    out.append("sensor_type: R3men_bed")
                    seen_sensor = True
                out.append("# " + line if not stripped.startswith("#") else line)
                continue

        if stripped.startswith("# sensor_type:"):
            out.append(line)
            continue

        if stripped.startswith("max_power:"):
            if not seen_max_power:
                while out and not out[-1].strip():
                    out.pop()
                out.append("max_power: 0.8")
                seen_max_power = True
            continue

    out.append(line)

# Handle if [heater_bed] was last section.
if in_bed:
    while out and not out[-1].strip():
        out.pop()
    if not seen_sensor:
        out.append("sensor_type: R3men_bed")
    if not seen_max_power:
        out.append("max_power: 0.8")

cfg_path.write_text("\n".join(out) + "\n")
PY

touch /tmp/r3men-bed

echo "I: R3MEN bed thermistor profile installed."
echo "I: when no print is active, run FIRMWARE_RESTART and wait for the complete K2 startup sequence."
echo "I: power-cycle before homing only if that restart reports an error."
