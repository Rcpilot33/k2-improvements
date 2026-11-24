#!/bin/sh
# Shared by the downloaded bootstrap and the installed menu. Checks are local.
bootstrap_package_tools_ready() {
    local helper
    case "$1" in
        entware-opt) [ -x /opt/etc/init.d/rc.unslung ] ;;
        git-http) helper=$(/opt/bin/git --exec-path) && [ -x "$helper/git-remote-https" ] ;;
        wget-ssl) [ -x /opt/bin/wget ] ;;
        openssh-sftp-server) [ -x /opt/libexec/sftp-server ] ;;
        *) [ -x "/opt/bin/$1" ] ;;
    esac
}

bootstrap_packages_ready() {
    local packages name
    [ -x /opt/bin/opkg ] && [ -s /opt/etc/opkg.conf ] || { echo 'Missing opkg or /opt/etc/opkg.conf'; return 1; }
    packages=$(/opt/bin/opkg list-installed) || return 1
    for name in entware-opt git git-http wget-ssl curl jq unzip openssh-sftp-server; do
        printf '%s\n' "$packages" | grep -q "^$name " || {
            echo "Missing Entware package: $name"; return 1;
        }
        bootstrap_package_tools_ready "$name" || { echo "Missing executable for Entware package: $name"; return 1; }
    done
}

bootstrap_link_ready() {
    [ -e "$1" ] && [ -e "$2" ] && [ "$(readlink -f "$1")" = "$(readlink -f "$2")" ] ||
        { echo "Missing or incorrect link: $1 -> $2"; return 1; }
}

bootstrap_entware_ready() {
    local file
    bootstrap_link_ready /opt /mnt/UDISK/opt && bootstrap_packages_ready &&
    bootstrap_link_ready /usr/libexec/sftp-server /opt/libexec/sftp-server || return 1
    grep -Fq 'export PATH="/opt/bin:/opt/sbin:$PATH"' /etc/profile.d/entware.sh || {
        echo 'Entware PATH is missing from /etc/profile.d/entware.sh'; return 1;
    }
    [ -x /etc/init.d/unslung ] && cmp -s "$1/entware/unslung.init" /etc/init.d/unslung || {
        echo 'Missing or changed Entware init script: /etc/init.d/unslung'; return 1;
    }
    bootstrap_link_ready /etc/rc.d/S99unslung /etc/init.d/unslung &&
    bootstrap_link_ready /etc/rc.d/K01unslung /etc/init.d/unslung || return 1
    for file in passwd group shells shadow gshadow localtime; do
        if [ -f "/etc/$file" ]; then
            bootstrap_link_ready "/opt/etc/$file" "/etc/$file" || return 1
        elif [ -f "/opt/etc/$file.1" ]; then
            [ -f "/opt/etc/$file" ] || return 1
        fi
    done
}

bootstrap_home_ready() {
    local name root=/mnt/UDISK/root
    [ "$(awk -F: '$1=="root" {print $6}' /etc/passwd)" = "$root" ] || {
        echo "Root login home should be $root"; return 1;
    }
    for name in klipper klippy-env moonraker moonraker-env printer_data; do
        local target="/usr/share/$name"
        [ "$name" != printer_data ] || target=/mnt/UDISK/printer_data
        case "$name" in moonraker*) [ -d "$target" ] || continue ;; esac
        # Mainline Moonraker and user-managed directories are kept by better-root.
        [ -d "$root/$name" ] || { echo "Missing printer directory: $root/$name"; return 1; }
        [ ! -L "$root/$name" ] || bootstrap_link_ready "$root/$name" "$target" || return 1
    done
}

bootstrap_checkout_ready() {
    local missing
    [ -r "$1/menu.sh" ] && [ -r "$1/installer/menus/main.sh" ] &&
    [ "$(/opt/bin/git -C "$1" rev-parse --show-toplevel)" = "$(readlink -f "$1")" ] &&
    /opt/bin/git -C "$1" rev-parse --verify HEAD >/dev/null || return 1
    missing=$(/opt/bin/git -C "$1" ls-files --deleted -- menu.sh bootstrap installer) || return 1
    [ -z "$missing" ] || { echo "Missing installer files: $missing"; return 1; }
}
