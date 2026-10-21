# Docker validation — 2026-10-21 (Asia/Taipei)

Branch: `codex/project3-advanced`, HEAD `5d40d8905e7b4767806f887e6ef0e33e759f876d`,
with the uncommitted Docker migration in this working tree. All runs below use
Linux containers. No macOS Python packages were installed. Existing native
environments and Docker data/output volumes were preserved.

| Check | Result | Evidence |
| --- | --- | --- |
| Project 1 running services, health, data hashes and VNC/noVNC ports | PASS | project1-check.txt |
| ModelB6 dependency check and offline tests | 93/93 PASS; no skips | modelb6-tests.txt |
| ModelB6 compatibility and read-only source/data mounts | PASS | modelb6-compatibility.json |
| Agent dependency check and offline tests | 96/96 PASS; no skips | agent-tests.txt |
| Canonical Agent evidence exports | 26/26 verified | agent-tests.txt |
| Agent reference construction | PASS, no provider request | agent-baseline.json |
| Project 3 dependency check and complete test suite | 163/163 PASS; no skips | project3-tests.txt |
| Baseline / Kalman image inference | Each 1 frame, 5 detections, 4 person detections | integration-summary.json |
| Baseline / Kalman video inference | Each 300 frames, 1627 detections, 1 person detection | integration-summary.json |
| Detector output equality across both tracker runs | Exact equality on image and 300 video frames | integration-summary.json |
| Kalman coasting / reacquisition + follow controller | STOP on missing target; explicit confirmation required after reacquisition | integration-summary.json, smoke.py |
| Final simulated command on every integration run | Zero speed / turn and STOP | integration-summary.json |
| Qt5 window loop on shared Docker X11 / VNC desktop | 120 frames completed, no GUI/runtime error | gui-smoke.txt |
| Synthetic benchmark, five scenarios / three trackers | PASS | synthetic.json |

352 tests passed in total. Agent and Project 3 use native Linux arm64 Python 3.11;
OpenPilot and ModelB6 retain amd64 emulation and Python 3.8. Image IDs are recorded
in images.txt. Model SHA256 remains
`bf667e5041e89ffaf1faa17c1ecbcf2d87729a514486a46c1996682342386031`.

The first Agent image lacked Git, causing eight provenance-related test errors.
Git was added to its Dockerfile and the complete 96-test suite was rerun successfully.
A Git package download timeout was resolved by an apt retry with cached downloads.

## Synthetic results and limits

On seed 2026, greedy / Hungarian / Kalman ID switches are respectively:

| Scenario | Greedy | Hungarian | Kalman |
| --- | --- | --- | --- |
| Crossing | 2 | 2 | 0 |
| Fast lateral motion | 24 | 24 | 0 |
| Three-frame occlusion | 1 | 1 | 0 |
| Jitter | 0 | 0 | 0 |
| Detection dropout | 0 | 0 | 0 |

These are synthetic boxes, not human-annotated real tracking accuracy. The real
video has only one person detection over the measured frames; it verifies file
pipeline integration, not multi-person identity stability. All video simulation
frames remained STOP because no target was explicitly selected. The image run
checks explicit selection; the synthetic controller integration checks loss,
reacquisition, and rearming. No motor commands or live Agent API calls were made.

The GUI smoke run establishes successful Qt display processing and cleanup;
manual VNC key interaction and subjective visual correctness were not verified.
CoreML is unavailable in Linux. AVFoundation webcam access, real C2C/device
integration, physical following and driving quality remain unverified. Project 1
validation does not rerun replay or certify a fresh empty-volume rebuild.

## Reproduction

From the repository root:

```sh
./scripts/dev.sh test
./scripts/dev.sh agent baseline_check.py
./scripts/dev.sh p3 check
```

To repeat the integration smoke in a fresh output directory:

```sh
./scripts/dev.sh p3-python evidence/docker-20261021/smoke.py artifacts/new-docker-smoke
```

Existing model, image, video and professor reference fixtures are required;
missing private fixtures are never represented as completed hardware acceptance.
