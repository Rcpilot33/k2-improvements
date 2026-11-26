#!/bin/sh
set -e
exec sh "$(dirname "$(readlink -f "$0")")/../../bootstrap/better-root/install.sh" "$@"
