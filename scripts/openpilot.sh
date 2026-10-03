#!/usr/bin/env bash
# Convenient command entry point for the ai-self-driving-car environment.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose -f "$project_dir/docker/docker-compose.yaml")

usage() {
  cat <<'EOF'
Usage: ./scripts/openpilot.sh <command> [options]

Environment:
  up                 Start compute and display
  down               Stop containers and keep volumes
  restart            Restart both services
  status             Show service status
  validate           Run non-destructive environment checks
  build              Build both Docker images
  build-compute      Build only the compute image
  build-display      Build only the display image

Display and logs:
  display            Print VNC/noVNC connection details
  logs [service]     Follow logs for compute, display, or both

OpenPilot:
  shell              Open a shell in compute
  versions           Show Python, Poetry, SCons, Git, and submodules
  build-op            Compile openpilot with SCons
  build-jll-compat    Rebuild JLL in an isolated Docker volume
  replay-demo        Run the official demo replay
  replay-route DIR ROUTE
                     Replay a route from a local data directory
  replay-jll-demo    Run the compatible JLL USA demo (qcam workaround)
  replay-jll-datac   Run the compatible JLL Taiwan dataC replay

Examples:
  ./scripts/openpilot.sh up
  ./scripts/openpilot.sh replay-demo
  ./scripts/openpilot.sh replay-route /data/dataC 'route|segment'
  ./scripts/openpilot.sh replay-jll-demo
  ./scripts/openpilot.sh replay-jll-datac
EOF
}

require_service() {
  "${compose[@]}" up -d "$@"
}

case "${1:-help}" in
  up)
    require_service compute display
    ;;
  down)
    "${compose[@]}" down
    ;;
  restart)
    "${compose[@]}" restart
    ;;
  status)
    "${compose[@]}" ps -a
    ;;
  validate)
    "$project_dir/scripts/validate-docker.sh"
    ;;
  build)
    "${compose[@]}" build compute display
    ;;
  build-compute)
    "${compose[@]}" build compute
    ;;
  build-display)
    "${compose[@]}" build display
    ;;
  display)
    cat <<'EOF'
VNC:   vnc://127.0.0.1:5910
Web:   http://localhost:6080/vnc.html
Pass:  0000
EOF
    ;;
  logs)
    if [[ -n "${2:-}" ]]; then
      "${compose[@]}" logs -f "$2"
    else
      "${compose[@]}" logs -f compute display
    fi
    ;;
  shell)
    require_service compute
    "${compose[@]}" exec compute bash
    ;;
  versions)
    require_service compute
    "${compose[@]}" exec compute sh -lc '
      python3.8 --version
      poetry --version
      scons --version | head -n 1
      git -C /opt/openpilot describe --tags --always
      git -C /opt/openpilot submodule status
    '
    ;;
  build-op)
    require_service compute
    "${compose[@]}" exec compute sh -lc 'cd /opt/openpilot && scons -u -j2'
    ;;
  build-jll-compat)
    "$project_dir/scripts/build-jll-compatible.sh"
    ;;
  replay-demo)
    require_service compute display
    echo 'Open VNC/noVNC first, then the official demo will start.'
    "${compose[@]}" exec -e TERM=xterm compute sh -lc \
      'tools-official-backup-20261003/replay/replay --demo --qcam --no-hw-decoder --no-loop -c 1'
    ;;
  replay-route)
    if [[ $# -ne 3 ]]; then
      echo 'Usage: ./scripts/openpilot.sh replay-route DATA_DIR ROUTE' >&2
      exit 2
    fi
    require_service compute display
    data_dir="$2"
    route="$3"
    "${compose[@]}" exec -e TERM=xterm compute sh -lc \
      'tools-official-backup-20261003/replay/replay --no-hw-decoder --data_dir "$1" "$2"' \
      sh "$data_dir" "$route"
    ;;
  replay-jll-demo)
    require_service compute display
    echo 'Open the UI in VNC/noVNC first, then the JLL USA demo will start.'
    "${compose[@]}" exec -e TERM=xterm compute sh -lc \
      'test -x tools/replay/replayJLL.compat || { echo "Compatible JLL binary missing; run ./scripts/openpilot.sh build-jll-compat" >&2; exit 1; }; exec tools/replay/replayJLL.compat --demo --qcam --no-hw-decoder --no-loop -c 1'
    ;;
  replay-jll-datac)
    require_service compute display
    echo 'Open the UI in VNC/noVNC first, then the JLL Taiwan dataC replay will start.'
    "${compose[@]}" exec -e TERM=xterm compute sh -lc \
      'test -x tools/replay/replayJLL.compat || { echo "Compatible JLL binary missing; run ./scripts/openpilot.sh build-jll-compat" >&2; exit 1; }; exec tools/replay/replayJLL.compat --no-hw-decoder --data_dir tools/replay/dataC "8bfda98c9c9e4291|2020-05-11--03-00-57--61"'
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $1" >&2
    usage >&2
    exit 2
    ;;
esac
