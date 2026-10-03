#!/usr/bin/env bash
set -euo pipefail
# Read-only checks: do not stop the user's running services on exit.
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose -f "$project_dir/docker/docker-compose.yaml")
"${compose[@]}" config --quiet
"${compose[@]}" ps
"${compose[@]}" exec -T compute python3.8 --version
"${compose[@]}" exec -T compute test -d /data
"${compose[@]}" exec -T display python3 /usr/local/bin/display_client.py
"${compose[@]}" exec -T display sh -ec '
  pgrep -x Xvfb
  pgrep -x openbox
  pgrep -f "^python3 /usr/local/bin/launcher.py$"
  test -x /opt/openpilot/selfdrive/ui/_ui
  ! ldd /opt/openpilot/selfdrive/ui/_ui | grep "not found"
'
curl --fail --silent --output /dev/null http://127.0.0.1:6080/vnc.html
nc -z 127.0.0.1 5910
echo 'Display and health socket: PASS (does not certify replay data).'
