#!/bin/ash

set -e

cd "$(dirname "$0")"
. ../prerequisites.sh

unset LD_LIBRARY_PATH
unset LD_PRELOAD

LOADER=ld-linux.so.3
GLIBC=2.27

ENTWARE_ROOT=/mnt/UDISK/opt
FRESH_INSTALL=0
if [ -x "$ENTWARE_ROOT/bin/opkg" ]; then
  echo "Info: Preserving the existing Entware installation..."
else
  FRESH_INSTALL=1
  echo "Info: Bootstrapping opkg in the persistent Entware directory..."
fi

echo "Info: Creating directory..."
mkdir -p "$ENTWARE_ROOT"

echo "Info: Linking folder..."
if [ -L /opt ]; then
  if [ "$(readlink -f /opt)" != "$ENTWARE_ROOT" ]; then
    echo "Error: /opt points outside $ENTWARE_ROOT; refusing to replace it" >&2
    exit 1
  fi
elif [ -e /opt ]; then
  echo "Error: /opt exists and is not the Entware symlink; refusing to replace it" >&2
  exit 1
else
  ln -s "$ENTWARE_ROOT" /opt
fi

echo "Info: Creating subdirectories..."
for folder in bin etc lib/opkg tmp var/lock
do
  mkdir -p /mnt/UDISK/opt/$folder
done

chmod 755 ./wget-ssl.py
URL="https://bin.entware.net/armv7sf-k3.2/installer"

download_files() {
  local url="$1"
  local output_file="$2"
  ./wget-ssl.py "$url" -O "$output_file"
  return $?
}

if [ "$FRESH_INSTALL" -eq 1 ]; then
  echo "Info: Downloading opkg package manager from Entware repo..."
  download_files "$URL/opkg" "/opt/bin/opkg.new"
  mv /opt/bin/opkg.new /opt/bin/opkg
fi
if [ ! -s /opt/etc/opkg.conf ]; then
  download_files "$URL/opkg.conf" "/opt/etc/opkg.conf.new"
  mv /opt/etc/opkg.conf.new /opt/etc/opkg.conf
fi

echo "Info: Applying permissions..."
chmod 755 /opt/bin/opkg
chmod 777 /opt/tmp

# put the python wget in place long enough to bootstrap opkg with the full version
export PATH=/opt/bin:$PATH
if ! bootstrap_packages_ready; then
  wget_dir=$(mktemp -d)
  trap 'rm -f "$wget_dir/wget"; rmdir "$wget_dir"' EXIT
  ln -s "$(pwd)/wget-ssl.py" "$wget_dir/wget"
  download_path="$PATH"
  [ -x /opt/bin/wget ] || download_path="$wget_dir:$PATH"
  PATH="$download_path" /opt/bin/opkg update
  packages=$(/opt/bin/opkg list-installed)
  for name in wget-ssl entware-opt git git-http curl jq unzip openssh-sftp-server; do
    if printf '%s\n' "$packages" | grep -q "^$name "; then
      bootstrap_package_tools_ready "$name" && continue
      PATH="$download_path" /opt/bin/opkg --force-reinstall install "$name"
    else
      PATH="$download_path" /opt/bin/opkg install "$name"
    fi
    bootstrap_package_tools_ready "$name" || { echo "Error: $name is still incomplete" >&2; exit 1; }
    download_path="$PATH"
  done
fi
mkdir -p /usr/libexec
ln -sf /opt/libexec/sftp-server /usr/libexec/sftp-server

echo "Info: Configuring files..."
for file in passwd group shells shadow gshadow localtime; do
  if [ -f /etc/$file ]; then
    ln -sf /etc/$file /opt/etc/$file
  elif [ ! -e "/opt/etc/$file" ] && [ -f "/opt/etc/$file.1" ]; then
    cp "/opt/etc/$file.1" "/opt/etc/$file"
  fi
done

echo "Info: Applying changes in system profile..."
mkdir -p /etc/profile.d
echo 'export PATH="/opt/bin:/opt/sbin:$PATH"' > /etc/profile.d/entware.sh

echo "Info: Adding startup script..."

cp unslung.init /etc/init.d/unslung
chmod 755 /etc/init.d/unslung
ln -sf /etc/init.d/unslung /etc/rc.d/S99unslung
ln -sf /etc/init.d/unslung /etc/rc.d/K01unslung
