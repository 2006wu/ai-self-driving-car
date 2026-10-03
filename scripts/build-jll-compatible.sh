#!/usr/bin/env bash
# Rebuild the tools092 JLL replay without touching the working source volume.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_volume=ai-self-driving-car_openpilot-repo
build_volume="ai-self-driving-car-jll-build-$(date +%Y%m%d%H%M%S)-$$"
image=ai-self-driving-car-compute
complete=false
volume_created=false

cleanup() {
  if [[ "$complete" == true ]]; then
    docker volume rm "$build_volume" >/dev/null
  elif [[ "$volume_created" == true ]]; then
    echo "Build copy kept for inspection: $build_volume" >&2
  fi
}
trap cleanup EXIT

docker compose -f "$project_dir/docker/docker-compose.yaml" up -d compute
docker volume inspect "$source_volume" >/dev/null
docker image inspect "$image" >/dev/null
docker volume create "$build_volume" >/dev/null
volume_created=true

echo 'Copying working source into an isolated build volume...'
docker run --rm --platform linux/amd64 \
  -v "$source_volume:/source:ro" -v "$build_volume:/work" \
  --entrypoint bash "$image" -lc \
  'set -e
   expected=a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1
   test -f /source/tools/replay/SConscript
   test -x /source/tools/replay/replayJLL
   actual=$(sha256sum /source/tools/replay/replayJLL | cut -d " " -f 1)
   test "$actual" = "$expected"
   cp -a /source/. /work/'

echo 'Building replayJLL from the tools092 SCons source...'
docker run --rm --platform linux/amd64 \
  -v "$build_volume:/opt/openpilot" -w /opt/openpilot \
  --entrypoint bash "$image" -lc \
  'scons -u -j2 tools/replay/replayJLL && test -x tools/replay/replayJLL'

echo 'Installing a separate compatible binary; the supplied replayJLL stays unchanged...'
docker run --rm --platform linux/amd64 \
  -v "$build_volume:/source:ro" -v "$source_volume:/target" \
  --entrypoint bash "$image" -lc \
  'set -e
   expected=a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1
   install -m 0755 /source/tools/replay/replayJLL /target/tools/replay/replayJLL.compat
   cmp /source/tools/replay/replayJLL /target/tools/replay/replayJLL.compat
   actual=$(sha256sum /target/tools/replay/replayJLL | cut -d " " -f 1)
   test "$actual" = "$expected"
   sha256sum /target/tools/replay/replayJLL /target/tools/replay/replayJLL.compat'

complete=true
echo 'Compatible JLL build passed; the isolated build volume was removed.'
