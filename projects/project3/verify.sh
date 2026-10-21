#!/bin/sh
set -eu
exec "$(dirname "$0")/../../scripts/dev.sh" test-p3 "$@"
