#!/usr/bin/env bash
set -euo pipefail
# Read-only checks: do not stop the user's running services on exit.
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose -f "$project_dir/docker/docker-compose.yaml")
"${compose[@]}" config --quiet
"${compose[@]}" ps
for service in compute display; do
  container_id="$("${compose[@]}" ps -q "$service")"
  test -n "$container_id"
  health="$(docker inspect --format '{{.State.Health.Status}}' "$container_id")"
  test "$health" = healthy || { echo "$service health: $health" >&2; exit 1; }
done
"${compose[@]}" exec -T compute python3.8 --version
"${compose[@]}" exec -T compute sh -ec '
  test -d /data
  test "$(find /data/dataB6 -type f | wc -l)" -eq 129
  test -f "/opt/openpilot/tools/replay/dataC/8bfda98c9c9e4291|2020-05-11--03-00-57/61/rlog.bz2"
  test -f "/opt/openpilot/tools/replay/dataC/8bfda98c9c9e4291|2020-05-11--03-00-57/61/fcamera.hevc"
  test "$(sha256sum /opt/openpilot/tools/replay/replayJLL | cut -d " " -f 1)" = a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1
  test "$(sha256sum /opt/openpilot/tools/replay/replayJLL.compat | cut -d " " -f 1)" = 40fbd0add9ffdf12f77006744992bb90b83235359a43ac2254284732afd92b8a
'
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
echo 'Containers, core assets, display ports, and health socket: PASS (does not certify replay video).'
