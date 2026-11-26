#!/bin/sh
# Both installers use the same runtime. The optional editor config also defines
# its Fluidd macro and can already be active on printers upgraded from older releases.
set -eu
here="$(dirname "$0")"
custom="$1"
extras="$2"
python="${K2_PYTHON:-python3}"
module=k2_material_z_offset_editor.py
ln -sfn "$(readlink -f "$here/../../../installer/extras/material-z-offsets/$module")" "$extras/$module"
if grep -Eiq '^[[:space:]]*\[include[[:space:]]+material_z_offsets\.cfg\][[:space:]]*$' "$custom/main.cfg"; then
    if grep -Fq material_z_registration.cfg "$custom/main.cfg"; then
        "$python" "$here/../../../scripts/ensure_included.py" "$custom/main.cfg" material_z_registration.cfg True
    fi
else
    ln -sfn "$(readlink -f "$here/material_z_registration.cfg")" "$custom/material_z_registration.cfg"
    "$python" "$here/../../../scripts/ensure_included.py" "$custom/main.cfg" material_z_registration.cfg
fi
