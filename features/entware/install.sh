#!/bin/ash

set -e

cd $(dirname ${0})

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
  echo "Info: Removing an absent or incomplete Entware installation..."
  [ ! -L /opt ] || rm -f /opt
  rm -rf "$ENTWARE_ROOT"
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
  if download_files "$URL/opkg" "/opt/bin/opkg"; then
    download_files "$URL/opkg.conf" "/opt/etc/opkg.conf"
  else
    echo "Info: Failed to download from Entware repo..."
    rm -f /opt
    rm -rf "$ENTWARE_ROOT"
    exit 1
  fi
fi

echo "Info: Applying permissions..."
chmod 755 /opt/bin/opkg
chmod 777 /opt/tmp

# put the python wget in place long enough to bootstrap opkg with the full version
cp wget-ssl.py /bin/wget

echo "Info: Installing basic packages..."
/opt/bin/opkg update
# replace the bootstrap wget-ssl implementation
/opt/bin/opkg install wget-ssl
rm -f /bin/wget
# ensure newly installed wget-ssl is in path
export PATH=/opt/bin:$PATH
/opt/bin/opkg install entware-opt git git-http curl jq unzip


echo "Info: Installing SFTP server support..."
/opt/bin/opkg install openssh-sftp-server
ln -sf /opt/libexec/sftp-server /usr/libexec/sftp-server

echo "Info: Configuring files..."
for file in passwd group shells shadow gshadow; do
  if [ -f /etc/$file ]; then
    ln -sf /etc/$file /opt/etc/$file
  else
    [ -f /opt/etc/$file.1 ] && cp /opt/etc/$file.1 /opt/etc/$file
  fi
done

[ -f /etc/localtime ] && ln -sf /etc/localtime /opt/etc/localtime

echo "Info: Applying changes in system profile..."
mkdir -p /etc/profile.d
echo 'export PATH="/opt/bin:/opt/sbin:$PATH"' > /etc/profile.d/entware.sh

echo "Info: Adding startup script..."

cp unslung.init /etc/init.d/unslung
chmod 755 /etc/init.d/unslung
ln -sf /etc/init.d/unslung /etc/rc.d/S99unslung
ln -sf /etc/init.d/unslung /etc/rc.d/K01unslung
