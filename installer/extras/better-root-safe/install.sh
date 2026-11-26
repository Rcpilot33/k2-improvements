#!/bin/sh
set -e
export K2_SKIP_BETTER_ROOT_LOGOUT=1
exec sh "$(dirname "$(readlink -f "$0")")/../../../bootstrap/better-root/install.sh" "$@"
