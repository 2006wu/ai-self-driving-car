#!/usr/bin/env bash
# All application Python and package installation run in containers.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose -f "$project_dir/docker/docker-compose.yaml" --profile all --profile project2)
command="${1:-help}"
[[ $# -eq 0 ]] || shift
case "$command" in
  build)
    if [[ $# -gt 0 ]]; then
      for service in "$@"; do
        if [[ "$service" == modelb6 ]]; then
          "$project_dir/scripts/dev.sh" prepare-modelb6
          break
        fi
      done
      "${compose[@]}" build "$@"
    else
      "${compose[@]}" build compute display
      "$project_dir/scripts/dev.sh" prepare-modelb6
      "${compose[@]}" build modelb6 agent project3
    fi
    ;;
  prepare-modelb6)
    mkdir -p "$project_dir/projects/project2/modelb6/wheelhouse"
    docker run --rm --read-only --platform linux/amd64 --tmpfs /tmp \
      --mount "type=bind,src=$project_dir/projects/project2/modelb6,dst=/workspace/student,readonly" \
      --mount "type=bind,src=$project_dir/projects/project2/modelb6/wheelhouse,dst=/workspace/student/wheelhouse" \
      --entrypoint python3.8 ai-self-driving-car-compute:latest \
      /workspace/student/fetch_tensorflow_wheel.py
    ;;
  up) "${compose[@]}" up -d compute display ;;
  status) "${compose[@]}" ps -a ;;
  p3) "${compose[@]}" run --rm --no-deps project3 python -m p3.cli "$@" ;;
  p3-display)
    "${compose[@]}" up -d compute display
    "${compose[@]}" run --rm --no-deps -e DISPLAY=:99 -e QT_QPA_PLATFORM=xcb \
      -v ai-self-driving-car_op-runtime:/display-runtime:ro project3 sh -ec \
      'ln -s /display-runtime/.X11-unix /tmp/.X11-unix; exec python -m p3.cli "$@"' sh "$@"
    ;;
  p3-python) "${compose[@]}" run --rm --no-deps project3 python "$@" ;;
  agent) "${compose[@]}" run --rm --no-deps -e GOOGLE_API_KEY -e GEMINI_MODEL_ID agent python "$@" ;;
  modelb6) "${compose[@]}" run --rm --no-deps modelb6 python3.8 "$@" ;;
  test-p3)
    "${compose[@]}" run --rm --no-deps project3 sh -ec \
      'python -m pip check; python -m unittest discover -s tests -v'
    ;;
  test-agent)
    "${compose[@]}" run --rm --no-deps agent sh -ec \
      'python -m pip check; python -m unittest discover -p "*_tests.py" -v; python prepare_v2.py --verify'
    ;;
  test-modelb6)
    "${compose[@]}" run --rm --no-deps modelb6 sh -ec \
      'python3.8 -m pip check; python3.8 -m unittest discover -s /workspace/student -p "*tests.py" -v'
    ;;
  test)
    "$project_dir/scripts/validate-docker.sh"
    "$0" test-modelb6
    "$0" test-agent
    "$0" test-p3
    ;;
  help|-h|--help)
    cat <<'EOF'
Usage: ./scripts/dev.sh COMMAND [ARGS...]
  build [SERVICE...]  Build environments (default: all, compute before modelb6)
  prepare-modelb6     Fetch/verify TensorFlow wheel using the compute image
  up                  Start OpenPilot compute and VNC/noVNC display
  status              Show containers
  test                Validate Project 1 and test ModelB6, Agent and Project 3
  test-modelb6        ModelB6 offline tests in Docker
  test-agent          Agent offline tests and canonical export verification
  test-p3             Project 3 unit and model integration tests in Docker
  p3 ARGS...          Project 3 CLI (check/run/benchmark/tracking-fixtures)
  p3-display ARGS...  Project 3 CLI on existing VNC desktop (add --display)
  p3-python ARGS...   Python/module in Project 3 container
  agent ARGS...       Python/script in Agent container (keys forwarded by name)
  modelb6 ARGS...     Python/script in ModelB6 container

Project 3 paths are relative to /workspace/projects/project3.
Outputs: artifacts/... (host-visible). Sources and model/data volumes: read-only.
Example: ./scripts/dev.sh p3 run artifacts/bus.jpg --track --output artifacts/docker-image
EOF
    ;;
  *) echo "Unknown command: $command" >&2; exit 2 ;;
esac
