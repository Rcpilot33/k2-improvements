#!/bin/ash
set -e

# Use the same non-destructive package repair as the first-stage bootstrap.
exec sh "$(dirname "$0")/../../bootstrap/entware/install.sh" "$@"
