# Select the macro profile before installing any part of the bundle.
macro_model=$(get_sn_mac.sh model) || exit 1
case "$macro_model" in
    F008) ;;
    F012) macro_config_dir="${PRINTER_CFG_DIR:-$HOME/printer_data/config}" ;;
    *) echo "E: unsupported macro profile: $macro_model" >&2; exit 1 ;;
esac

# The shared M191 and mesh templates read the active Pro profile at runtime.
require_macro_profile() {
    [ "$macro_model" = F012 ] || return 0
    if [ ! -f "$macro_config_dir/custom/start_print_pro.cfg" ] ||
       ! grep -q '^\[include start_print_pro\.cfg\]$' "$macro_config_dir/custom/main.cfg"; then
        echo "E: install the K2 Pro macro bundle with option 13 first" >&2
        return 1
    fi
}
