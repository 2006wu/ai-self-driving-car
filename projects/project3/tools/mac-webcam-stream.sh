#!/usr/bin/env bash
# Explicit host-side bridge: application/inference remains in Docker.
set -euo pipefail
device=0
size=640x480
fps=15
port=8081
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      cat <<'HELP'
Usage: mac-webcam-stream.sh [--device INDEX] [--size WIDTHxHEIGHT] [--fps FPS] [--port PORT]
Run on macOS with an existing ffmpeg installation supporting avfoundation.
Streams one HTTP multipart MJPEG client at http://127.0.0.1:8081/.
Container URL: http://host.docker.internal:8081/ (Docker Desktop required).
macOS may prompt for camera permission; this script never changes permissions.
Stop with Ctrl-C. Restart explicitly after client disconnect. No audio captured.
HELP
      exit 0 ;;
    --device|--size|--fps|--port)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --device) device="$2" ;; --size) size="$2" ;; --fps) fps="$2" ;; --port) port="$2" ;;
      esac
      shift 2 ;;
    *) echo "Unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[[ "$device" =~ ^[0-9]+$ && "$size" =~ ^[1-9][0-9]*x[1-9][0-9]*$ && "$fps" =~ ^[1-9][0-9]*$ && "$port" =~ ^[0-9]{1,5}$ ]] || { echo 'Invalid device/size/fps/port' >&2; exit 2; }
(( 10#$port > 0 && 10#$port <= 65535 )) || { echo 'Port must be 1..65535' >&2; exit 2; }
[[ "$(uname -s)" == Darwin ]] || { echo 'This helper requires macOS.' >&2; exit 2; }
command -v ffmpeg >/dev/null || { echo 'Install ffmpeg on the Mac host first.' >&2; exit 2; }
exec ffmpeg -hide_banner -nostdin -f avfoundation -framerate "$fps" -video_size "$size" \
  -i "$device:none" -an -c:v mjpeg -q:v 5 -f mpjpeg -listen 1 "http://127.0.0.1:$port/"
