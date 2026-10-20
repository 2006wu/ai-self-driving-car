# Project 3 — native YOLO, evaluation and Run2 preparation

See [requirements/source audit](../../docs/PROJECT3.md),
[measured acceptance](evidence/STATUS.md), [hardware checklist](HARDWARE.md).
Required: Run1 PC YOLO and Run2 C2C/Wi-Fi/UI. Benchmark/robustness are engineering
additions; tracking/overlay are Do New. Hardware and webcam acceptance are pending.

Latest: [2026-10-16 software validation report](evidence/validation-20261016/REPORT.md).
107/107 Project 3 tests pass; real annotated tracking accuracy remains NOT TESTED.

## Environment

Tested: Python **3.11.4 arm64**, macOS native. Dedicated `.venv`; full resolved
versions in requirements.txt. No TensorFlow, Agno or OpenPilot environment changes.
From repository root:

```sh
./projects/project3/setup.sh
./projects/project3/run.sh check
./projects/project3/verify.sh
```

If Python 3.11 is elsewhere, set `P3_PYTHON=/absolute/path/to/python3.11` for setup.
Dependencies are pinned, not a wheel/hash lock or cross-platform guarantee.
Model remains the original local `external/aJLL/bodyjim/yolov5n_flat.onnx`:
SHA256 `bf667e5041e89ffaf1faa17c1ecbcf2d87729a514486a46c1996682342386031`.
Missing model produces an error; no hidden downloads. CoreML is optional and
requires the provider to be listed by `check`. CPU default uses one intra-op thread.
`AzureExecutionProvider` is enumerated but not evaluated as a local accelerator.

## Inputs and reference

The original `preview.png` is absent. A public Ultralytics sample is used for
image/person smoke testing, not as labeled accuracy data. Download into ignored
artifacts, from this component directory:

```sh
mkdir -p artifacts/reference artifacts/inputs
curl -L --fail 'https://raw.githubusercontent.com/ultralytics/ultralytics/main/ultralytics/assets/bus.jpg' -o artifacts/bus.jpg
curl -L --fail 'https://drive.usercontent.google.com/download?id=1Sf4PztfOjutOdgJz7CqQow5UUZlW9xl8&export=download&confirm=t' -o artifacts/reference/uiview.py
```

Only parse the downloaded reference for audit. No original device script is
executed against a device or host OpenPilot. If a download is HTML/auth/error,
stop and report it; do not import it. Hash/byte count in source-audit.json verifies
the inspected version. Future upstream changes require renewed comparison.

For this run the existing dataB6 USA video was read from a volume using an
already-installed Alpine image; no P1/P2 services were started or rebuilt:

```sh
docker run --pull never --rm --read-only --network none \
  --mount type=volume,src=ai-self-driving-car_replay-data,dst=/data,readonly \
  --entrypoint /bin/cat alpine:latest \
  /data/dataB6/UHD--2018-08-02--08-34-47--37/video.hevc > artifacts/inputs/usa.hevc
```

Use your existing local video if this volume/image is unavailable. Do not fetch
or replace existing OpenPilot images to run this command. Image, video, reference
and output media stay ignored; small JSON/test evidence is retained separately.

## Run1 (commands from repository root)

Each output directory must be new or empty; existing evidence is never overwritten.

```sh
./projects/project3/run.sh run artifacts/bus.jpg --output artifacts/my-image
./projects/project3/run.sh run artifacts/inputs/usa.hevc --max-frames 2000 --output artifacts/my-video
./projects/project3/run.sh run 0 --camera --display --max-frames 300 --output artifacts/my-camera
```

Paths are relative to `projects/project3/` because run.sh changes to that directory;
absolute paths also work. Camera is **opt-in**, uses AVFoundation, and requires
macOS permission and real hardware. It has not been accessed in this work.
File EOF exits; empty/corrupt inputs produce errors; camera disconnect is an
error. q exits displayed sessions; resources close on normal and error paths.
A single session is loaded per run; model input remains 640×416. BGR, direct
resize, objectness threshold and class-agnostic NMS reproduce professor math.
Boxes map independently into original image width/height and are clipped.
`obj=` is objectness, not a calibrated class confidence or objectness×class score.

## Do New: tracking and overlay dashboard

```sh
./projects/project3/run.sh run artifacts/bus.jpg --track --output artifacts/my-tracking-image
./projects/project3/run.sh run artifacts/inputs/usa.hevc --track --display --max-frames 300 --output artifacts/my-tracking-video
```

Overlay displays class/objectness, boxes, person track IDs, selected target state,
inference timing, previous-frame pipeline timing, person count and explicit C2C
NOT CONNECTED status. Press n for next visible target, q to exit. The first frame
has no previous-frame timing. Headless PNG/video outputs and mocked GUI event
cleanup were verified. An actual native-display smoke run processed 1200 frames
and exited at EOF. UI automation observation timed out; real key interaction
and camera capture remain NOT TESTED.
IoU matching tolerates short gaps at similar locations. Lost targets do not
silently switch to a new person. No re-identification or physical human following. Optional follow decisions are
dimensionless software simulation only, saved locally and never sent to a motor. The status is local, not a live C2C connection monitor. CLI
reports fatal errors; a reconnecting network dashboard is not implemented.

## Benchmark

```sh
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --warmup 5 --output evidence/my-image.json
./projects/project3/run.sh benchmark artifacts/inputs/usa.hevc --samples 120 --warmup 5 --output evidence/my-video.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --resolution 640x480 --output evidence/my-small.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --confidence .5 --output evidence/my-conf50.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --provider CoreMLExecutionProvider --output evidence/my-coreml.json
```

Resolution changes the *source* size; fixed model input stays 640×416. Threshold
changes are tested separately from resolution changes. Five warm-up forwards are
excluded; video is reopened for identical measured starting frames. Resident image
reads exclude disk decode. Video E2E includes decode; both include optional source
resize, preprocess/inference/postprocess and overlay. Excludes model construction,
source opening, exports, GUI display and camera capture. Tracking and simulated
decisions are included only when their flags are enabled. Inference FPS
and file-pipeline FPS are 1000 / mean stage latency, not video playback rate.
Per-stage mean, median, P95, population std/count, per-frame process RSS, detection
count and objectness stats are recorded. Load-time repeated statistics and provider
output comparison: `evaluate.py` (run from this directory, output must not exist).
CoreML uses fallback CPU partitions; GPU-only speed/utilization is not measured.
No ground truth: **precision/recall/mAP not evaluated**. Dark/blur/occlusion image
perturbations are software probes, not real adverse-scene accuracy measurements.

## Run2 verification boundaries

Exact course script is materially different from uiviewJLL: four device processes,
four cereal services and a persistent Params write. The Wi-Fi workflow is PC SSH
to **device-side UI**. No YOLO-to-PC/C2C streaming protocol is specified by it.
`p3/run2.py` preserves process/message APIs through dependency injection and adds
bounded retries/cleanup. It intentionally has no real-device default bindings.
API-double tests include normal/invalid data, timeout, disconnect/recreate-publisher,
partial startup and cleanup. These are not actual network or Capnp/msgq tests.
No network emulator is added without a confirmed streaming interface. Hardware
firmware and bindings must be checked before adding a runnable device adapter.

## Evidence and report outline

Small evidence contains source/environment hashes, measured benchmarks, unit/model
integration logs, API-double results, supplemental probes and preservation checks.
Generated run.json/PNG/AVI remain in ignored artifacts. See COMMANDS.md and STATUS.md.
Tests distinguish executed PASS from explicit fixture SKIP; missing private assets
are not silently treated as passes. `verify.sh` exits on test failure; unittest
SKIPs remain visible in the test summary. No physical test is represented as a skip
that counts toward a hardware PASS.

Report narrative: requirements → original source limits → isolated architecture →
Run1 numerical/file verification → measured provider/scenario results → Run2 device
architecture/API preparation → tracking/robustness extensions → hardware/accuracy
limits → next experiments. No report deck or PDF is generated in this iteration.

## Vision validation and simulated follow (2026-10-16)

The same detector/capture/render pipeline supports simulation; the greedy IoU
association algorithm is unchanged. `--track` alone retains the original initial
tracking target selection. **Simulation begins IDLE and requires explicit selection**
(`n` in display mode, or `--target-id` in a bounded offline run). A displayed
tracker target does not by itself arm simulation.

```sh
# From repository root; output directories must be new or empty.
./projects/project3/run.sh run artifacts/bus.jpg --track --simulate-follow --target-id 1 --output artifacts/my-simulation-image
./projects/project3/run.sh run artifacts/inputs/usa.hevc --track --simulate-follow --max-frames 2000 --output artifacts/my-simulation-video
./projects/project3/run.sh tracking-fixtures --output evidence/my-synthetic-tracking.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --track --simulate-follow --samples 30 --output evidence/my-tracking-performance.json
```

In display mode: `n` selects the next visible track; `r` explicitly confirms the
current visible target; `c` cancels selection and stops; `s` saves a screenshot;
`q` stops and exits. Selection first emits zero output. A later unambiguous frame
can emit FOLLOW. Loss immediately emits zero, progresses from
TARGET_TEMPORARILY_LOST to TARGET_LOST after five missed updates, and latches
stopped. Reappearance of even the same ID requires explicit confirmation.
Overlap with another tracked person at IoU >= .15 also latches STOP; ambiguous
selection cannot arm. Invalid boxes/IDs, model errors and unexpected exceptions
stop and clean up; faults require a new session. Frame age over .5 seconds stops.
Speed/turn are normalized heuristics based on box center/width, not calibrated
vehicle commands or metric distance. STOP has priority over selection/follow.
An undetected identity swap without observable overlap/loss can evade this policy;
tracking IDs and software STOP behavior do not establish real identity or physical safety.

Successful runs save `run.json`, first-frame `preview.png`, and an `overlay.avi`
for video/camera unless `--no-record` is used. `events.jsonl` is flushed per event;
`run-status.json` records termination and cleanup even on failed runs. The final
simulation event is STOP at EOF, limits, quit or error. Failed runs exit nonzero;
frame records remain available in the event journal even if `run.json` was not
completed. Filesystem failure can prevent durable logs. `--max-seconds` is checked
between frames; it cannot interrupt blocked native capture/inference. An external
watchdog would be needed for a hard wall-clock deadline.

### Manual webcam acceptance — currently BLOCKED

The read-only AVFoundation authorization query returned `notDetermined` on
2026-10-16. No capture or permission-setting change was performed. Run this
manually in a local terminal when ready, responding to the macOS permission
prompt yourself:

```sh
./projects/project3/run.sh run 0 --camera --display --track --simulate-follow --max-frames 300 --max-seconds 30 --output artifacts/webcam-manual-01
```

Start with simulation IDLE; verify boxes/obj/IDs/FPS, select with `n`, take a
snapshot with `s`, cancel with `c`, confirm with `r`, then quit with `q`. Repeat
in separate new output folders for permission refusal and camera disconnection
when feasible. Check nonzero error exits, final zero simulated output and
resource release. Actual key interaction, capture, sensor drops and camera FPS
remain NOT TESTED; injected camera/GUI tests are software checks only. No Docker
is needed for these commands when the local model and input files already exist.

### Annotated tracking evaluation

Prepare JSON with trusted human annotations and detector/tracker predictions in
original pixel coordinates; use positive integer IDs and strictly increasing
frame numbers. For example (a **synthetic** two-frame example):

```json
{
  "annotation_kind": "synthetic_ground_truth",
  "target_gt_id": 1,
  "frames": [
    {"frame": 0, "ground_truth": [{"id": 1, "box": [10, 20, 50, 100]}], "predictions": [{"id": 7, "box": [10, 20, 50, 100]}]},
    {"frame": 1, "ground_truth": [{"id": 1, "box": [12, 20, 52, 100]}], "predictions": [{"id": 7, "box": [12, 20, 52, 100]}]}
  ]
}
```

For actual annotated clips use `human_ground_truth`. Merely setting that flag
does not validate annotation quality; annotation provenance and review are still
required. Never label detector outputs as ground truth. No annotation means real
IDF1/ID precision/ID recall are N/A.

```sh
./projects/project3/run.sh tracking-eval /absolute/path/annotations-and-predictions.json --iou .5 --output evidence/my-annotated-tracking.json
```

ID metrics use global identity assignment of all IoU-qualified pairs. Frame
matching maximizes match count then IoU. ID switches compare the last matched
prediction ID for each GT ID, including gaps. Fragmentation is a matched →
unmatched-while-GT-present → matched transition; absence of GT alone is not an
FN. Continuity reports matched-visible and longest-consecutive fractions.
Recovery counts completed gaps returning to the initial prediction ID; no
eligible gap gives N/A. Recovery never grants permission to resume following.
This evaluator omits MOTChallenge ignore-region/class/visibility preprocessing;
see [tracking method reference](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/identity.py).

### Reproduce the full local benchmark and summaries

```sh
cd projects/project3
.venv/bin/python validate_vision.py --output evidence/my-validation-measurements
.venv/bin/python summarize.py
```

Use an idle machine and new output directory; the first command measures local
files only. Nine conditions compare CPU/CoreML, source sizes, thresholds and
optional tracking/follow, with five excluded warmups and 30 measured frames each.
Fixed model input remains 640×416. Synthetic 1/2/5/10/20-person box workloads
measure tracker cost only; actual detector person counts are reported separately.
`summarize.py` rebuilds the current report from the saved final evidence, without
rerunning inference. Its historical 2026-10-14 report remains available separately.
Detection FPS is 1000 / mean(preprocess + inference + postprocess); inference FPS
uses inference alone; file pipeline FPS includes decode/resize/render and optional
tracking/decisions. None is webcam FPS. Per-stage mean/median/P95/std and samples
are retained. Runtime loop timing additionally includes export IO; session wall
includes opening/journaling. CPU percent uses one core = 100% and may exceed 100%;
RSS is sampled process memory, not continuous peak or GPU memory. Application
skipped frames = 0 means no intentional skipping; sensor drops are N/A.

## Opt-in offline research (`p3.research`)

`p3.research` is not imported by `p3.cli` or the Run1/Run2 commands. Nothing in
this package runs unless you start it. It records a local image or video into a
v2 bundle (`manifest.json`, `records.jsonl`, `quality.json`) and can replay the
existing greedy and Hungarian trackers on the stored detections. It does not
open a camera, talk to hardware, or change follow/tracking defaults.

From the repository root, with this component on `PYTHONPATH`:

```sh
PYTHONPATH=projects/project3 python -m p3.research.offline record path/to/clip.mp4 --output path/to/dataset --max-frames 120
PYTHONPATH=projects/project3 python -m p3.research.offline validate path/to/dataset --output path/to/quality.json
PYTHONPATH=projects/project3 python -m p3.research.offline template path/to/dataset --output path/to/annotations.json
PYTHONPATH=projects/project3 python -m p3.research.offline extract path/to/dataset --output path/to/frames --frames 0,30
PYTHONPATH=projects/project3 python -m p3.research.offline validate-annotations path/to/dataset path/to/annotations.json
PYTHONPATH=projects/project3 python -m p3.research.offline evaluate path/to/dataset --output path/to/comparison.json
```

`--media-root` (or the `P3_MEDIA_ROOT` environment variable) stores and resolves
the original media path relative to that directory. Recordings made without a
media root still store an absolute path. Bundles written before this option,
including the samples under `reports/ai-control-milestone2-20261020/`, keep
their original absolute paths and no `path_kind`. `validate` checks record
order, the journal hash, and manifest identity either way. If the original file
is absent, the command exits 0 with status `WARN` and names the missing media;
that is not treated as a corrupt dataset. A file that is present but has a
different size or SHA256 is still `FAIL`. `--verify-pixels` re-decodes when the
file is available, and is reported as skipped when it is not. Point
`--media-root` at a directory that contains a byte-identical copy to check
those bytes on another machine. The contract is described in
[SCHEMA.md](../../reports/ai-control-milestone2-20261020/SCHEMA.md).

`implementation_fingerprint()` hashes every `p3/**/*.py` file. That map is part
of the manifest `identity`, and `session_id` is `offline-` plus the SHA256 of
the canonical identity JSON. Any later change under `p3/` changes the session
id of datasets recorded after that change. Manifests that are already written
keep the fingerprints and session id they were saved with.
