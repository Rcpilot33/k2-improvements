# Mesh bounds are in probe coordinates. With Jamin's 5.8 mm spacers,
# the stock Y endstops (-6.2 Plus, -6.5 Pro) become -0.4 and -0.7.
CARTO_MODEL=$(get_sn_mac.sh model) || return 1
case "$CARTO_MODEL" in
    F008)
        MESH_ZERO_REFERENCE='175, 175'
        JAMIN_MESH_MAX='340, 330'
        JIMMYV_MESH_MAX='345, 340'
        JAMIN_Y_HOME=-0.4 ;;
    F012)
        MESH_ZERO_REFERENCE='150, 150'
        JAMIN_MESH_MAX='290, 280'
        JIMMYV_MESH_MAX='295, 290'
        JAMIN_Y_HOME=-0.7 ;;
    *) echo 'E: no Cartographer mesh limits for this printer model' >&2; return 1 ;;
esac

# Render the managed Jamin baseline for the detected model and USB port.
render_cartographer_config() {
    sed -e "s|^serial: /dev/cartographer$|serial: $2|" \
        -e "s|^zero_reference_position: .*|zero_reference_position: $MESH_ZERO_REFERENCE|" \
        -e "s|^mesh_max: .*|mesh_max: ${JAMIN_MESH_MAX}|" \
        -e "/^\[stepper_y\]$/,/^\[/s|^position_endstop: .*|position_endstop: $JAMIN_Y_HOME|" \
        -e "/^\[stepper_y\]$/,/^\[/s|^position_min: .*|position_min: $JAMIN_Y_HOME|" "$1" || return 1
    if [ "$CARTO_MODEL" = F012 ]; then
        cat "$(dirname "$1")/home_z_pro.cfg"
    fi
}
