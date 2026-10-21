# Project 3 — Docker YOLO, evaluation and Run2 preparation

Current runtime policy (2026-10-21): all setup, execution and testing use Docker.
The existing setup/run/verify scripts now delegate to `scripts/dev.sh`.
See [Docker commands and limits](../../docs/DOCKER.md); older native macOS evidence
below describes historical measurements, not the current runtime.
Docker validation: [163/163 Project 3 tests, image/video and Qt/VNC smoke](evidence/docker-20261021/RESULTS.md).

See [requirements/source audit](../../docs/PROJECT3.md),
[measured acceptance](evidence/STATUS.md), [hardware checklist](HARDWARE.md).
Required: Run1 PC YOLO and Run2 C2C/Wi-Fi/UI. Benchmark/robustness are engineering
additions; tracking/overlay are Do New. Hardware and webcam acceptance are pending.

Latest: [2026-10-16 software validation report](evidence/validation-20261016/REPORT.md).
107/107 Project 3 tests pass; real annotated tracking accuracy remains NOT TESTED.

## Environment

Runtime: Python **3.11**, Linux Docker, native host architecture. Dependencies
in requirements.txt are installed in the image, separately from Agent/ModelB6.
From repository root:

```sh
./projects/project3/setup.sh
./projects/project3/run.sh check
./projects/project3/verify.sh
```

Dependencies are pinned, not a wheel/hash lock or cross-platform guarantee.
Model remains the original local `external/aJLL/bodyjim/yolov5n_flat.onnx`:
SHA256 `bf667e5041e89ffaf1faa17c1ecbcf2d87729a514486a46c1996682342386031`.
Missing model produces an error; no hidden downloads. CoreML is unavailable in
the Linux container. CPU default uses one intra-op thread.
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
```

Paths are relative to `projects/project3/` because run.sh changes to that directory;
absolute container paths also work. The legacy camera path uses AVFoundation
and is unavailable in Linux Docker; use the opt-in Mac webcam bridge below.
Real camera acceptance remains pending.
File EOF exits; empty/corrupt inputs produce errors; camera disconnect is an
error. q exits displayed sessions; resources close on normal and error paths.
A single session is loaded per run; model input remains 640×416. BGR, direct
resize, objectness threshold and class-agnostic NMS reproduce professor math.
Boxes map independently into original image width/height and are clipped.
`obj=` is objectness, not a calibrated class confidence or objectness×class score.

## Do New: tracking and overlay dashboard

```sh
./projects/project3/run.sh run artifacts/bus.jpg --track --output artifacts/my-tracking-image
./scripts/dev.sh p3-display run artifacts/inputs/usa.hevc --track --display --max-frames 300 --output artifacts/my-tracking-video
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
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --warmup 5 --output artifacts/my-image.json
./projects/project3/run.sh benchmark artifacts/inputs/usa.hevc --samples 120 --warmup 5 --output artifacts/my-video.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --resolution 640x480 --output artifacts/my-small.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --samples 30 --confidence .5 --output artifacts/my-conf50.json
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
./projects/project3/run.sh tracking-fixtures --output artifacts/my-synthetic-tracking.json
./projects/project3/run.sh benchmark artifacts/bus.jpg --track --simulate-follow --samples 30 --output artifacts/my-tracking-performance.json
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

### Manual webcam acceptance — user hardware verification pending

The read-only AVFoundation authorization query returned `notDetermined` on
2026-10-16. No capture or permission-setting change was performed. Under the
current Docker runtime, AVFoundation cannot be used directly. The opt-in Mac
webcam bridge below supplies container-compatible stream input; real webcam
acceptance still requires user permission and hardware verification.
Use `scripts/dev.sh p3-display` with existing files for desktop testing.

Start with simulation IDLE; verify boxes/obj/IDs/FPS, select with `n`, take a
snapshot with `s`, cancel with `c`, confirm with `r`, then quit with `q`. Repeat
in separate new output folders for permission refusal and camera disconnection
when feasible. Check nonzero error exits, final zero simulated output and
resource release. Actual key interaction, capture, sensor drops and camera FPS
remain NOT TESTED; injected camera/GUI tests are software checks only.

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
./projects/project3/run.sh tracking-eval /absolute/path/annotations-and-predictions.json --iou .5 --output artifacts/my-annotated-tracking.json
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
../../scripts/dev.sh p3-python validate_vision.py --output artifacts/my-validation-measurements
```

Use an idle machine and new output directory; the command measures local
files only. Six CPU conditions compare source sizes, thresholds and
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

From the repository root, through the Project 3 Docker runtime (paths inside
the container are relative to `projects/project3/`). Choose a fresh artifacts
directory for each run:

```sh
mkdir projects/project3/artifacts/my-real-annotation-run
./scripts/dev.sh p3-python -m p3.research.offline record artifacts/inputs/multi-person.mp4 --output artifacts/my-real-annotation-run/dataset --max-frames 120
./scripts/dev.sh p3-python -m p3.research.offline validate artifacts/my-real-annotation-run/dataset --output artifacts/my-real-annotation-run/quality.json
./scripts/dev.sh p3-python -m p3.research.offline template artifacts/my-real-annotation-run/dataset --output artifacts/my-real-annotation-run/blank.json
./scripts/dev.sh p3-python -m p3.research.offline evaluate artifacts/my-real-annotation-run/dataset --output artifacts/my-real-annotation-run/unannotated.json
```

### Real multi-person annotation with CVAT / MOT

Real tracking accuracy remains **NOT TESTED** until real clips have been labeled
and human reviewed. Synthetic unit tests and offline follow simulation do not
count as real accuracy or hardware acceptance. The recorder above reads an
existing local clip; it does not capture from a camera.

1. Record the local clip into a bundle as above. Extract **every contiguous
   frame** you intend to label, preserving order. For a 120-frame bundle:

   ```sh
   ./scripts/dev.sh p3-python -m p3.research.offline extract artifacts/my-real-annotation-run/dataset --output artifacts/my-real-annotation-run/frames --frames "$(seq -s, 0 119)"
   ```

   Use the actual recorded count from `manifest.json` if EOF occurs earlier.
   Upload only `frame-*.png` to CVAT in numeric filename order; `index.json`
   records the original dataset mapping. Sparse extracts such as `0,30` cannot
   use the contiguous MOT frame mapping below.
2. In CVAT, label all persons, keep each person's track identity through
   crossings/occlusion, and inspect empty frames too. Use pedestrian class 1
   for the MOT export. Export **MOT 1.1**, unpack it locally, and place its
   `gt/gt.txt` at `projects/project3/artifacts/my-real-annotation-run/gt.txt`.
   Only the GT text file is read; no CVAT service or network connection is used.
3. Import a draft, inspect the printed JSON summary and resulting boxes against
   the extracted originals:

   ```sh
   ./scripts/dev.sh p3-python -m p3.research.offline import-mot artifacts/my-real-annotation-run/dataset artifacts/my-real-annotation-run/gt.txt --output artifacts/my-real-annotation-run/draft.json --target-person-id 9
   ```

   Replace 9 with the ground-truth person identity you want to assess. Omitting
   it leaves selected-target continuity unavailable. Drafts remain blocked by
   `validate-annotations` and have no accuracy metrics in `evaluate`.
4. After human review of **all frames in the span**, import to a new file with
   explicit verification and provenance, then validate and compare:

   ```sh
   ./scripts/dev.sh p3-python -m p3.research.offline import-mot artifacts/my-real-annotation-run/dataset artifacts/my-real-annotation-run/gt.txt --output artifacts/my-real-annotation-run/reviewed.json --target-person-id 9 --human-verified --annotator "Annotator name" --reviewer "Reviewer name"
   ./scripts/dev.sh p3-python -m p3.research.offline validate-annotations artifacts/my-real-annotation-run/dataset artifacts/my-real-annotation-run/reviewed.json
   ./scripts/dev.sh p3-python -m p3.research.offline evaluate artifacts/my-real-annotation-run/dataset --annotations artifacts/my-real-annotation-run/reviewed.json --trackers all --output artifacts/my-real-annotation-run/comparison.json
   ```

`--human-verified` maps to the existing contract's `status: reviewed`, reviewed
frames and `human_annotation` provenance; it is a user attestation, not automated
verification of truth. An import always refuses to overwrite an existing file.
Results count as real tracking accuracy only for human-verified **real** clips.

MOT rows are `frame,id,x,y,width,height[,mark[,class[,visibility]]]` (6–9 numeric
columns, consistent within a file). Frames and IDs must be positive integers;
duplicate IDs within any frame are errors. The mapping is
`dataset_frame_id = MOT_frame - 1 + frame_offset`: frame 1 maps to dataset frame
0 by default. For a contiguous extract of dataset frames 30–59, use
`--frame-offset 30 --frame-count 30`; MOT frames 1–30 then map to those records.
Without `--frame-count`, the span extends to the final recorded frame. Missing
rows within that span mean no labeled persons, including trailing empty frames;
verify the export covers the entire chosen span before marking it reviewed.
Out-of-range rows fail instead of being dropped.

MOT x/y are 1-based by default and converted to zero-based `[x1,y1,x2,y2]`;
width/height are unchanged. Use `--box-origin 0` only for exports with zero-based
x/y, and verify alignment against originals. Nonfinite numbers, nonpositive
sizes, and boxes outside the image fail. `--clip-boxes` explicitly permits
clipping with every original/result box reported; boxes with no area inside the
image still fail. Optional GT mark is 0 or 1 (default 1); mark 0 rows are excluded.
Class must be a positive integer (default 1); only class 1 pedestrians are
included. Visibility must be in [0,1] (default 1), mapped to none/partial/full
occlusion. A visibility-0 row retains its trusted box and is scored; visibility
alone never creates a missing box. All rows, including excluded rows, undergo
validation. Detector result files with confidence/XYZ columns are unsupported.
The summary includes exclusions, clipping, frame mapping and the source SHA256;
it is also retained as JSON in `provenance.reference` without extending the
annotation schema. Excluded rows do not create ignore regions, so predictions
there can count as false positives. This is not full MOTChallenge preprocessing.

`--trackers all` compares `greedy_iou`, `hungarian` and `kalman_iou`, or pass a
comma-separated subset. Each replays every stored detection frame, using the
same recorded threshold/max-missed settings and input hash. Each method reports
the existing evaluator metrics (including ID switches, IDF1 and recovery), timing,
predictions, plus `selected_target_continuity`. Continuity anchors the selected
GT person to its first matched prediction ID, counting frames on that ID
(including the first match), on a different ID, lost while a GT box is present,
and absent/unboxed GT separately. It uses only reviewed frames and the same
IoU matching as the evaluator; sampled frames cannot prove continuity between
samples. Without `--trackers`, the historical greedy/Hungarian report and its
fields stay unchanged. None of these results authorizes physical following.

`--media-root` (or the `P3_MEDIA_ROOT` environment variable) stores and resolves
the original media path relative to that directory. Recordings made without a
media root still store an absolute path. Bundles written before this option,
including the samples under `reports/ai-control-milestone2-20261020/`, keep
their original absolute paths and no `path_kind`. `validate` checks record
order, the journal hash, and manifest identity either way. If the original file
is absent, the command exits 0 with status `WARN` and names the missing media;
that is not treated as a corrupt dataset. `--require-media` makes that absence
a `FAIL` (exit 2). A file that is present but has a different size or SHA256 is
still `FAIL`, including a same-named file under the media root
(`media found under media root but hash mismatch`). `--verify-pixels` re-decodes
when the file is available. If the file is absent, pixel verification fails
(exit 2) instead of skipping. Point `--media-root` at a directory that contains
a byte-identical copy to check those bytes on another machine. The contract is
described in
[SCHEMA.md](../../reports/ai-control-milestone2-20261020/SCHEMA.md).

`implementation_fingerprint()` hashes every `p3/**/*.py` file. That map is part
of the manifest `identity`, and `session_id` is `offline-` plus the SHA256 of
the canonical identity JSON. Any later change under `p3/` changes the session
id of datasets recorded after that change. Manifests that are already written
keep the fingerprints and session id they were saved with.

### Regenerable large evidence files (not stored in git)

To keep the repository small, these generated files (about 5.5 MB together) were
removed from git on 2026-10-21. They are reproducible from local, gitignored inputs
under `projects/project3/artifacts/`, no test depends on them, and their original
SHA-256 values remain in the tracked JSON evidence (`integrity.json`,
`annotation-frames/index.json`, `checks.json`, `preservation-*.json`). Git history
still contains the old copies. Regenerate them in Docker from the repository root.
Outputs go to the writable `artifacts/` mount; the source tree is read-only.

| Removed file | SHA-256 (original) | Regenerate with |
|---|---|---|
| `reports/ai-control-readiness-20261020/export-sample.jsonl` (2.3 MB) | `846efc8b…07cfe` | export command below |
| `reports/ai-control-milestone2-20261020/annotation-frames/frame-{000000,000030,000060,000090,000119}.png` (~0.5 MB each) | see `annotation-frames/index.json` and `checks.json` | extract command below |
| `reports/ai-control-milestone3-20261020/audit/audit-contact-sheet.jpg` (0.6 MB) | `92e0d5c3…0f017` | local-audit command below |

```sh
# 1. Offline export sample (needs artifacts/validation-20261016/stability-video-final/events.jsonl)
./scripts/dev.sh p3-python -m p3.research.export \
  artifacts/validation-20261016/stability-video-final/events.jsonl \
  artifacts/regenerated/export-sample.jsonl
sha256sum projects/project3/artifacts/regenerated/export-sample.jsonl   # expect 846efc8ba74133b091fa64f6c7480c9a22a508d833f93816631be8f0e3407cfe

# 2. Annotation frames (needs artifacts/inputs/usa.hevc)
./scripts/dev.sh p3-python -m p3.research.offline extract \
  /workspace/reports/ai-control-milestone2-20261020/usa-verified \
  --frames 0,30,60,90,119 --media-root artifacts/inputs \
  --output artifacts/regenerated/annotation-frames

# 3. Milestone 3 audit contact sheet (runs from repo root; needs local media under artifacts/)
docker compose -f docker/docker-compose.yaml --profile project3 run --rm --no-deps \
  -w /workspace -e PYTHONPATH=/workspace/projects/project3 project3 \
  python reports/ai-control-milestone3-20261020/local-audit.py \
  --output projects/project3/artifacts/regenerated/milestone3-audit
```

The `.gitignore` lists the removed paths so a regenerated copy is not re-committed
by accident. Course deliverables (Report PDFs/PPTX) and the small sample bundles
(`usa-sample`, `usa-verified`, `image-sample`, each record file < 500 KB) stay in git.

### Opt-in motion tracker and synthetic tracker benchmark

Research callers can use `p3.research.tracking.create_tracker('kalman_iou')`
for constant-velocity Kalman prediction and optimal IoU assignment. The default
remains `greedy_iou`; `hungarian` remains available. Unmatched tracks coast as
`missing` for up to `max_missed` frames, then expire. Optional
`center_distance_gate` (default 1.5 predicted-box diagonals; `None` disables it)
allows missed tracks to associate with nearby detections. Prediction never
marks an unmatched target as tracked or grants permission to resume following.

From the repository root, after building the Project 3 image, choose a new output path:

```sh
./scripts/dev.sh p3-python -m p3.research.tracker_benchmark --output artifacts/new-synthetic-tracker-benchmark.json
```

The command refuses overwrite and records seeds, parameters and evaluator metrics
for crossing, fast lateral motion, a three-frame target occlusion, jitter and
detection dropout. Only matched detections are scored as predictions; synthetic
boxes remain in ground truth during detection gaps. All annotations and results
are explicitly `synthetic_ground_truth`. These results do not establish real
person identity, real-world tracking accuracy or physical safety.

### Mac webcam bridge to Docker (opt-in)

The helper captures at 30 fps by default; `--fps 15` downsamples output with
ffmpeg `-r 15`, keeping the capture rate at 30.

The host helper is a capture-only exception to the Docker runtime: ffmpeg must
already be installed **on the Mac**, with AVFoundation support. Python, inference
and tests remain in Docker. No permission settings are changed; macOS may prompt
for camera access for the terminal running ffmpeg. Approve manually if desired;
permission refusal must be treated as a failed capture, never a hardware PASS.

From the repository root, in a Mac terminal:

```sh
./projects/project3/tools/mac-webcam-stream.sh --help
./projects/project3/tools/mac-webcam-stream.sh --device 0 --size 640x480 --fps 30 --port 8081
```

In a second terminal (Docker Desktop running, Project 3 image built):

```sh
./scripts/dev.sh p3-stream http://host.docker.internal:8081/ --track --simulate-follow --max-frames 300 --max-seconds 60 --output artifacts/mac-stream-acceptance-001
```

Use a fresh output directory each time. The default URL can be omitted. The
underlying CLI also accepts `p3 run stream:http://host.docker.internal:8081/`.
For interactive VNC acceptance use `p3-display run` with the same `stream:` source
and `--display --track --simulate-follow`, then use n/r/c/s/q as described above.
Without explicit selection simulation stays IDLE; all output is local simulation,
with no physical control. Expect preview.png, overlay.avi, events.jsonl and
run-status.json; run.json is produced only on success.

Stop the consumer with Ctrl-C (or q with display), then stop the host helper with
Ctrl-C. ffmpeg serves one client; explicitly restart the helper and start a new
consumer session after disconnect. No automatic reconnect occurs. The helper binds
only 127.0.0.1 and captures no audio; do not expose this unauthenticated feed to a
LAN. Docker Desktop must support host loopback access via host.docker.internal;
if your Desktop/network policy blocks it, capture remains blocked. The Linux
host-gateway mapping does not by itself expose a host loopback listener.

The reader continuously drains capture and retains only the latest frame.
`application_skipped_frames` and `stream_dropped_frames` in run-status.json and
the session_end event count replaced, unconsumed frames; sensor drops remain unknown.
A read failure latches disconnect immediately, discarding any pending frame.
Stream open deadline is 3 seconds; local acquisition/stale deadline is .5 seconds.
Disconnect, invalid BGR frame or a deadline failure terminates the session,
latches the source closed and writes a final zero/STOP when simulation is enabled.
Native FFmpeg open/read timeout parameters are supplied, with a separate caller
watchdog. If a native backend ignores timeouts, its daemon worker releases capture
when the native call returns; the main pipeline still stops on deadline. These
limits do not interrupt model inference. Frame age measures local acquisition,
not sensor time: buffered/repeated upstream imagery and sensor drops cannot be
identified reliably from MJPEG. This is software fail-closed behavior, not a
physical safety guarantee.

Tests use injected captures and generated localhost MJPEG only. Run in Docker:

```sh
./scripts/dev.sh p3-python -m unittest discover -s tests -p test_stream.py -v
./scripts/dev.sh test-p3
```

Real Mac permission approval/refusal, image quality, latency, key interaction,
and disconnect behavior still require user hardware acceptance. Synthetic and
loopback results do not count as that acceptance.

## Run3 direction: PID follow (simulation only)

`p3.research.pid_controller.PIDFollowController` is an opt-in Controller adapter.
It delegates selection, stale age, loss, overlap, explicit confirmation and
permanent faults to an unchanged `FollowController`. The unchanged
`RuleBasedController` is the baseline. Production follow and replay defaults are
unchanged. Physical control remains disabled; no device interface is implemented.

This is a **synthetic kinematic simulation with an image-size distance proxy**,
not a calibrated vehicle controller or real hardware acceptance. There is no
vision inference, identity association error, vehicle dynamics, latency or noise
in this experiment. Gains were tuned on these authored scenarios; the comparison
is not held-out validation.

From the repository root, use Docker and a **new** output file:

```sh
./scripts/dev.sh p3-python -m p3.research.pid_sim --controller both --output artifacts/pid-sim/compare.json
# Optional configuration / scenario subset:
./scripts/dev.sh p3-python -m p3.research.pid_sim --controller pid --gains p3/research/pid_gains.json --scenarios straight_walk,turn --steps 200 --output artifacts/pid-sim-custom/compare.json
./scripts/dev.sh p3-python -m unittest discover -s tests -p test_pid_follow.py
```

JSON uses exclusive creation, sorted keys and finite numbers; an existing output
is refused. The CLI defaults to 200 steps at 0.1s (20s), all six scenarios and
both controllers. `--seed` is recorded; trajectories currently use no randomness.
`SimConfig` allows Python callers to change image dimensions, HFOV, person size,
physical simulation scales, desired distance and the safety threshold.

The world has x forward, y left and CCW positive heading. Positive normalized
turn rotates left; a target right of image centre produces negative PID turn.
Speed 0.3 maps to 1m/s and turn 0.5 to 1.5rad/s. The camera has 70-degree HFOV,
640×480 pixels and a 0.5m wide/1.7m tall person. Pinhole boxes are clipped to the
image; a centre outside HFOV or behind the camera is invisible. The default
width target 0.2 corresponds to axial distance
`0.5 / (2*tan(35 degrees)*0.2) = 1.785185m` before clipping.
Height mode needs its own target fraction for the chosen geometry; neither mode
is a calibrated range estimate.

Tuned defaults (also in `p3/research/pid_gains.json`):

| Parameter | Lateral | Longitudinal |
| --- | ---: | ---: |
| Kp | 0.85 | 6.0 |
| Ki | 0.06 | 1.0 |
| Kd | 0.12 | 0.10 |
| Deadband | 0.015 | 0.003 |
| Slew (normalized command/s) | 1.5 | 1.2 |

Both axes use derivative on measurement with a 0.15s first-order filter and an
error-integral clamp of ±0.4. Conditional integration considers both output and
slew saturation. Output limits are speed [0,0.3], turn [-0.5,0.5]. Forward speed
is zero when size fraction reaches the target, overriding slew for immediate
stopping; reverse is never permitted. dt comes from successive observation
timestamps, with nominal 0.1s for missing or repeated timestamps. Negative,
nonfinite or numerically tiny positive dt (<1ns) latches STOP. Configuration is
a frozen, strictly validated dataclass; JSON rejects unknown/duplicate keys.
Actions include P/I/D terms and legacy follow state/reason.

Selection calls `select(1, tracks)` once before prediction and rearms the replay
supervisor. This is the same explicit-confirmation method used by the pipeline's
`r` key. Loss immediately sets both commands to **exactly zero**, resets PID
memory and latches STOP. There is no nonzero decay after loss. Reappearance
never auto-resumes. Python callers may explicitly model an operator with
`operator_reselect_steps=(55,)`; only those steps call select and rearm again.
The default occlusion removes the target at steps 40–49 with no operator reselect.
The replay supervisor and CommandReplay gate every integrated action.
In `run_scenario`, the supervisor independently estimates target camera depth
from bbox width using the configured pinhole geometry. Below 1.0m it forces
forward speed to zero, preserves turning and TRACKING status, and adds
`safety_stop: too_close` and `estimated_distance_m` metadata. It releases at
or above 1.0m without latching or hysteresis. Horizontally clipped boxes
(`x1 <= 0` or `x2 >= image width`) and missing target boxes conservatively
use a zero estimate. Vertical clipping leaves the width-based estimate intact.
Controller
metadata cannot override this gate. The default lies between the 0.65m pass
threshold and 1.785m desired distance. For a stationary person, one 0.1s step
at 1m/s can take the robot to `1.0 - dt * max_linear = 0.9m`, still above
0.65m. This bound does not cover a person continuing to approach after stopping:
the hostile controller in the authored `too_close` scenario first stops at
0.976m, then the person continues to its endpoint, reducing the gap to 0.600m
(below 0.65m, so `safety_pass` is false). No forward command is emitted below
1.0m; a forward-only stop cannot guarantee clearance from an approaching person.
Results count these steps separately as `too_close_stop_steps`. Command-only
replay calls without an observation retain their existing behavior.

Measured 200-step comparison (rule → PID):

| Scenario | Centering RMS | Distance RMS (m) | Safety pass (both) |
| --- | ---: | ---: | --- |
| straight_walk | 0.0888 → 0.0393 | 0.4339 → 0.3314 | yes |
| turn | 0.0893 → 0.0403 | 0.4026 → 0.3250 | yes |
| stop_go | 0.0797 → 0.0393 | 0.4338 → 0.3356 | yes |
| lateral_step | 0.0906 → 0.0463 | 0.4370 → 0.3316 | yes |
| occlusion | 0.1252 → 0.1181 | 2.8797 → 2.9621 | yes |
| too_close | 0 → 0 | 0.8408 → 0.8408 | yes |

PID improves centering in 5/6 and distance in 4/6 scenarios. The occlusion
comparison includes the stopped interval: both controllers latch for 160 steps,
and PID's distance error is worse there. Both too_close runs command zero speed
while the person approaches to 0.9m and stops. All runs stay above the sampled
0.65m safety threshold with zero supervisor faults. This threshold pass applies
only to these authored trajectories: a stationary robot cannot keep a person
from approaching it. No collision clamp silently changes the trajectories.

Metrics use visible frames for normalized centering RMS and all steps for
Euclidean distance RMS. Final distance error includes the last integration
endpoint. Distance overshoot measures approach closer than desired; lateral
overshoot measures crossing the initial bearing side in metres. Settling time
is the earliest step after which both |offset|≤0.05 and |distance error|≤0.2m
hold through the end (null if never settled). Smoothness is mean L1 command
first difference and second difference (discrete jerk, not divided by dt).
Safety stop steps count non-TRACKING predictions; latched steps count either
legacy or supervisor latch. Minimum distance includes sampled steps and the final
endpoint, not a continuous collision certificate. The JSON also records tracking,
lost and visible steps, operator reselections and supervisor fault steps.

Local validation used the explicitly requested existing
`/workspace/scratch/venv-p3/bin/python` because Docker is unavailable in this
workspace. No environment or dependencies were installed. Docker commands above
are the supported reproduction path; a Docker execution was not measured here.

Validation for this change: 18 new tests pass in approximately 0.13s; full suite
203 tests, zero failures, 8 skips (existing optional fixtures/runtime checks).
The full suite took approximately 12s. Generated local comparison and test log
are under the fresh `artifacts/pid-sim-tuned/` directory; initial exploratory
results remain preserved under `artifacts/pid-sim/`.

## Control training dataset (comma body / AI-control direction)

`p3.research.control_dataset` builds versioned observation/action pairs without
copying images or sending commands. These are **synthetic teacher datasets** or
**offline recorded-run exports**, not real hardware acceptance or human driving.
From the repository root (output paths are relative to Project 3 in Docker):

```sh
./scripts/dev.sh p3-python -m p3.research.control_dataset build-sim --output artifacts/control-training-v1 --controllers pid,rule --episodes-per-scenario 3 --seed 7 --steps 100
./scripts/dev.sh p3-python -m p3.research.control_dataset build-recorded --events artifacts/my-run/events.jsonl artifacts/my-bundle/dataset --output artifacts/control-recorded-v1
./scripts/dev.sh p3-python -m p3.research.control_dataset validate artifacts/control-training-v1
./scripts/dev.sh p3-python -m p3.research.control_dataset stats artifacts/control-training-v1
```

`--scenarios` accepts comma-separated names: `straight_walk,turn,stop_go,lateral_step,occlusion,too_close`.
Optional `--perturb` uses a private seeded `random.Random` to vary the simulated
robot maximum linear speed by a factor in [0.8, 1.2]. Both teachers share each
scenario's factor; episode metadata includes the factor, seed, index, steps,
full simulator configuration and PID gains. It changes only this opt-in dataset
experiment. Without perturbations, repeated episodes intentionally duplicate
trajectories and are not independent experimental evidence.

Schema **`p3_control_dataset/1.0`** stores each sample's content-derived sample ID,
episode ID, split, step, timestamp, source kind and SHA256 reference; `frame_ref`
is a `sha256:<media hash>#decoded_frame=<index>` URI when available, otherwise
null. Simulation timestamps are seconds before action with clock
`simulation_seconds`; event timestamps retain `session_elapsed_monotonic` /
`journal_emission`, while v2 timestamps describe `processing_complete`. Neither
recorded timestamp represents camera exposure time. Source references hash the
event/record file or canonical simulator configuration/scenario/controller/gains.

Observations contain frame height/width, selected-target visibility, normalized
bbox corners (pixel x / width, pixel y / height), centre offset in [-1, 1], width
and height fractions, track count, follow state/reason and measured age in seconds.
A missing or invisible target has null geometry. A v2 tracker selection does not
imply the follow controller has selected that target. Unknown fields remain null
and are enumerated in `missing_fields`; no zero imputation occurs.

`FEATURES` (also `FEATURE`) defines the fixed numeric input order:
`frame_height, frame_width, target_visible, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
centre_offset, width_fraction, height_fraction, number_of_tracks, age_seconds`.
`feature_vector` follows that order (boolean visibility, numbers, or null).
Follow state/reason are retained as context outside the numeric vector. `ACTIONS`
is `[linear, angular]`. Teacher actions include controller `pid` or `rule`, status,
validity and units `normalized_simulation`. Safety stores supervisor latch/fault
and the final gated command actually submitted to **CommandReplay** in simulation.
Recorded runs do not log this independent gate, so those fields are null; teacher
labels are never presented as physical actuator commands. Simulation distance
and bearing are in `sim_ground_truth`, explicitly marked `privileged: true` and
`for_model_input: false`, and excluded from the feature vector.

Output directories must not exist. Each contains canonical JSON-lines files
`samples-{train,val,test}.jsonl`, `stats.json`, and `manifest.json` with schema,
version, creation configuration, feature/action names, episode metadata, excluded
teacherless-row count, split counts and file SHA256s. Stats include population
mean/std/min/max and missing counts for features/actions, zero-command STOP
fraction, status counts and per-scenario/controller row counts. Empty splits have
null distribution statistics. Both building and `stats` print the report;
`validate` recomputes all hashes and statistics and checks sample structure,
finite numbers, feature length, unique IDs and strictly increasing episode steps.

Splits hash **episode IDs only**, with default train/val/test ratios 70/15/15;
`--ratios 0.7,0.15,0.15` overrides them. An episode cannot appear in multiple
splits, and validation checks this guarantee and the split hash assignment.
Small datasets need not match the ratios exactly. Related scenarios, alternate
teachers and repeated synthetic trajectories can still be correlated across
episodes; episode separation alone does not establish generalization.

The checked-in fixture at `p3/research/samples/control-dataset-sample/` has 48
synthetic samples. Regenerate into a **new directory** and compare its five files;
there are no build timestamps or output paths in their identity, so the same
code/configuration gives a deterministic, byte-identical rebuild:

```sh
./scripts/dev.sh p3-python -m p3.research.control_dataset build-sim --output artifacts/control-sample-rebuilt --steps 4 --seed 7
./scripts/dev.sh p3-python -m p3.research.control_dataset validate p3/research/samples/control-dataset-sample
```

Teachers are PID/rule heuristics, not human driving. Pinhole boxes and simple
unicycle dynamics do not reproduce real perception, calibration or vehicle
behavior. Recorded runs lack physical commands, measured emergency-stop state
and camera exposure times; event journals also lack geometry. Bundle import
reuses v2 integrity/media-root resolution (`--media-root` or `P3_MEDIA_ROOT`),
permits missing original media, and never decodes or copies pixels. A present
original with an incorrect hash still fails. No media-byte verification is
claimed when it is absent.

This is not real comma body data yet. A future real log adapter would need
synchronized exposure/observation and actuator timestamps with documented clocks,
calibrated units and coordinate frames, camera dimensions and hashed media
references, target/tracking associations, human or controller action provenance,
command validity plus requested versus actually gated actuator commands, measured
robot motion/odometry and independent stop/fault state. Human review, real-world
coverage and separate hardware acceptance would still be required before any
physical-control claims. No model training or hardware adapter is included here.

## Behaviour-cloning baseline (simulation only)

`p3.research.bc_baseline` provides standardized ridge regression and a small
numpy MLP (16 tanh hidden units, full-batch Adam). `BCFollowController` is a new
opt-in controller with source `bc`; the `AIController` placeholder still returns
invalid zero-command `UNAVAILABLE`. Existing follow, PID, rule, replay and
simulator defaults are unchanged. Physical control is disabled.

From the repository root, use Docker. Every dataset directory, model and report
must be new; these commands refuse overwrite:

```sh
./scripts/dev.sh p3-python -m p3.research.control_dataset build-sim --output artifacts/control-ds --episodes-per-scenario 8
./scripts/dev.sh p3-python -m p3.research.bc_baseline train --dataset artifacts/control-ds --model ridge --output artifacts/bc-run/ridge.json --seed 0
./scripts/dev.sh p3-python -m p3.research.bc_baseline train --dataset artifacts/control-ds --model mlp --output artifacts/bc-run/mlp.json --seed 0
./scripts/dev.sh p3-python -m p3.research.bc_baseline eval-offline --dataset artifacts/control-ds --model-file artifacts/bc-run/ridge.json --output artifacts/bc-run/ridge-offline.json
./scripts/dev.sh p3-python -m p3.research.bc_baseline eval-closed-loop --model-file artifacts/bc-run/ridge.json --output artifacts/bc-run/ridge-closed.json --steps 200
./scripts/dev.sh p3-python -m p3.research.bc_baseline eval-offline --dataset artifacts/control-ds --model-file artifacts/bc-run/mlp.json --output artifacts/bc-run/mlp-offline.json
./scripts/dev.sh p3-python -m p3.research.bc_baseline eval-closed-loop --model-file artifacts/bc-run/mlp.json --output artifacts/bc-run/mlp-closed.json --steps 200
./scripts/dev.sh p3-python -m unittest discover -s tests -p test_bc_baseline.py
```

The dataset is fully validated before reading any training features. Only its
`FEATURES` vector enters the model; `ACTIONS` (linear, angular) are targets.
Ground-truth distance/bearing, follow state/reason, episode identifiers and labels
are excluded from model inputs. `--teacher pid|rule|all` defaults to PID.
Training defaults to TRACKING rows: other states have forced zero commands from
the safety layer and should be handled by that layer rather than learned.
`--all-states` explicitly includes these zero labels in training.

Only train rows determine imputation (per-feature train mean, or zero for an
entirely missing train feature), mean/std normalization and weight updates.
Constant features use scale 1. Validation MSE selects ridge alpha from
0.0001/0.01/1/10, or MLP learning rate from 0.003/0.01 and the early-stopping epoch
(maximum 500, patience 35). Seeds fix MLP initialization; training uses no test
labels for fitting or selection and does not refit on validation data. Numerical
reproducibility assumes the same numpy/BLAS runtime. Empty train/val selections
are rejected; empty test metrics are null.

Models are finite JSON with schema `p3_bc_model/1.0`, exact feature/action names,
normalization, list-valued weights, training manifest SHA256, configuration,
validation selection scores and per-split metrics. Loading checks schema, shapes,
finite values, positive scales, feature names and duplicate JSON keys.
Offline metrics use clamped commands and the authoritative non-TRACKING zero
gate; each split also reports a TRACKING-only subset. MAE/RMSE and R² are per
action. Constant-target R² is 1 for a perfect fit, otherwise 0. STOP agreement
means both command magnitudes are at most 0.001; it is a command comparison,
not a prediction of safety state. Non-TRACKING zeros can inflate all-state scores.

The controller uses the dataset's own `observation_features` function and an
unchanged `FollowController` for selection, loss, overlap, stale age, latches and
faults. Model inference runs only in TRACKING. Other states return exactly 0,0;
outputs are clamped to speed [0,0.3] and turn [-0.5,0.5], with no reverse.
Non-finite or malformed model output latches STOP with a permanent controller
fault. No controller automatically rearms after loss.

Closed-loop evaluation calls the unchanged `closed_loop.run_scenario` for BC,
PID and rule on all six scenarios. It reports all original metrics, including
centering RMS, distance RMS, sampled safety pass, supervisor fault steps and
mean command difference/jerk. Besides nominal episodes, it evaluates two fresh
plant speed scales in [0.65,0.75] and [1.25,1.35], outside the dataset builder's
training perturbation range [0.8,1.2]. A deterministic evaluation seed is the
training dataset seed plus 100003; the seed actually generates perturbations.
Nominal episodes can duplicate training trajectories and are not held out.

This baseline imitates a synthetic PID teacher from low-dimensional bbox
features. PID has history (integral, filtered derivative, slew) absent from this
memoryless policy. Repeated unperturbed training episodes are correlated across
splits. Held-out plant scales exercise only narrow synthetic variation, with no
perception noise or real dynamics. Offline imitation errors do not establish
closed-loop stability: covariate shift can put the learner in states the teacher
did not visit. It is not trained on real comma body data, not validated on
hardware, and provides no real hardware acceptance evidence. Physical control
remains disabled.

Reference results (2026-10-21, Linux box with the Project 3 Python 3.11
dependencies; not yet re-run in Docker on the Mac). Dataset:
`build-sim --episodes-per-scenario 8` (default seed), 8,600 samples, PID teacher,
TRACKING rows only; offline metrics on the held-out **test** split (1,800 rows):

| Model | MAE linear | MAE angular | R² linear | R² angular | STOP agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| ridge | 0.0157 | 0.0057 | 0.853 | 0.870 | 0.976 |
| mlp (seed 0) | 0.0123 | 0.0048 | 0.904 | 0.936 | 0.897 |

Closed loop (`eval-closed-loop`, 200 steps, all six scenarios; mean over
scenarios; held-out = 2 perturbed plant episodes per scenario):

| Partition | Controller | Centering RMS | Distance RMS (m) | Safety pass | Supervisor faults |
| --- | --- | ---: | ---: | ---: | ---: |
| nominal | rule | 0.0789 | 0.905 | 6/6 | 0 |
| nominal | pid (teacher) | 0.0472 | 0.854 | 6/6 | 0 |
| nominal | bc ridge | 0.0494 | 0.867 | 6/6 | 0 |
| nominal | bc mlp | 0.0494 | 0.864 | 6/6 | 0 |
| held-out | rule | 0.0777 | 0.962 | 12/12 | 0 |
| held-out | pid (teacher) | 0.0472 | 0.886 | 12/12 | 0 |
| held-out | bc ridge | 0.0487 | 0.914 | 12/12 | 0 |
| held-out | bc mlp | 0.0510 | 0.916 | 12/12 | 0 |

BC closely imitates the PID teacher and clearly beats the rule baseline, but does
not exceed its teacher. The table above predates the shared distance hard stop.
BC has no controller-local "box larger than target => speed 0" override;
the supervisor now enforces the distance stop for BC, PID, rule and future
controllers through `run_scenario`. The `tests/test_too_close_stop.py` regression
trains ridge and MLP models and checks zero forward commands whenever true
distance is below 1.0m (only 1e-9m pinhole roundoff tolerance). With a stationary
person, hostile, BC, PID and rule runs must meet the derived 0.9m one-step
bound and the 0.65m safety floor. The authored moving-person BC/PID/rule runs
retain an empirical 0.88m regression floor; it is not a one-step clearance
guarantee. The hostile moving-person test explicitly records the 0.600m
limitation above. Measured in a Python
3.11 environment (same pinned requirements), that test's tiny dataset
(`episodes_per_scenario=8`, `steps=25`, `seed=5`, perturbed PID teacher) gives
`too_close` minimum distances before → after: ridge 0.900 → 0.900m,
MLP 0.750355 → 0.885022m, PID and rule both 0.900 → 0.900m. These are synthetic
simulation checks, not physical safety acceptance. Distance RMS includes the
occlusion scenario, where every standard controller stays latched after loss.
Dataset teacher labels remain the proposed controller action, with the final
gated command recorded separately; the committed sample is not regenerated.

## Report 3 draft figures

`p3.research.report3_figures` collects tracker, PID/rule and behaviour-cloning
metrics into a new folder of CSV and Markdown tables plus matplotlib PNG charts.
Matplotlib is pinned in `requirements.txt` (`matplotlib==3.9.4` and its wheels).
`docker/Dockerfile.project3` installs that file through `install_requirements.py`;
there is no second pip install.

The run is deterministic for a fixed seed and the same numpy build. Tracker
numbers come from `p3.research.tracker_benchmark` synthetic boxes. PID and rule
numbers come from `p3.research.pid_sim`, with one world-frame trajectory plot
per scenario. Behaviour cloning trains ridge and MLP on a fresh temporary
`control_dataset build-sim` dataset (PID teacher, fixed seeds) and compares
closed-loop metrics with PID. Stream stop-latency and unittest counts are read
from `projects/project3/evidence` when those files exist. Missing measurements
are marked NOT AVAILABLE and are not invented. Real hardware stays NOT TESTED
unless a cited evidence line records it.

From the repository root, after the Project 3 image is built, pick a new output
directory. An existing path is refused. `reports/project3-report3-draft` is used
only when you pass `--draft`.

```sh
./scripts/dev.sh p3-python -m p3.research.report3_figures --output artifacts/report3-draft-001
./scripts/dev.sh p3-python -m unittest discover -s tests -p test_report3_figures.py
```

`summary.md` in that folder lists every figure and table with the source command
and separates synthetic/simulated results from real-hardware results.

## Body interface (simulation only)

`p3.research.body_interface` is the Run4/Run5 software command boundary behind
`SafetySupervisor`. It lives in `research` alongside the simulation contracts
because this is an offline replay experiment, with no physical integration.
**No real transport exists.** `MockTransport` and `DryRunTransport` record commands
in memory only; `RealTransport` always raises `NotImplementedError`. Factory
and interface defaults are `simulation_only=True`; `--transport real` is refused
before creating output. No network, device discovery or hardware sends occur.

From the Project 3 directory, using its Python 3.11 runtime (use
`./scripts/dev.sh p3-python` from the repository root for the supported Docker
path), choose a fresh output directory:

```sh
python -m p3.research.body_interface replay-sim --scenario straight_walk --controller pid --steps 100 --output artifacts/body-sim-001
python -m p3.research.body_interface replay-log tests/fixtures/body-actions.jsonl --output artifacts/body-log-001
```

`replay-sim` consumes the existing simulator callback's supervisor-gated `safe`
action. It observes that simulation; the body commands do not replace the
simulator's dynamics input. `replay-log` accepts one JSON object per line:

```json
{"timestamp":0.1,"action":{"linear_velocity_command":0.3,"angular_velocity_command":0.2,"status":"TRACKING","source_controller":"pid","valid":true,"units":"normalized_simulation"}}
```

Timestamps are finite, nonnegative monotonic seconds in one replay clock.
Actions use the existing `Action` constructor fields (`units` defaults to
`normalized_simulation`). Log proposals pass through a fresh SafetySupervisor,
rearmed once at replay start; STOP/invalid input latches it for the rest of the
file. The tiny fixture demonstrates that subsequent motion cannot clear STOP.
Programmatic callers must supply the supervisor's safe output to
`BodyInterface.tick(action, now=...)`; `tick(now=...)` polls without a new action.
The interface cannot prove an action's provenance or replace the supervisor.

`BodyLimits` validates finite positive limits and acceleration budgets, with a
0.25s watchdog. Speed [0, 0.3] maps to [0, max_linear], turn [-0.5, 0.5] maps to
[-max_angular, max_angular]. Units are **body_normalized / uncalibrated**, not
physical velocity or physical acceleration; defaults are 1 for each bound and
acceleration. Defensive clamping handles finite out-of-range input; malformed,
non-finite or invalid tracking input produces zero and a diagnostic fault flag.
A supervisor STOP produces zero immediately. Fault flags persist for diagnosis.

E-stop latch overrides watchdog, clamping and acceleration; `estop(reason)`
emits zero immediately. Only explicit `reset_estop()` clears the latch, after a
valid explicit zero action received since the latch was set, with no intervening
nonzero input. No-command ticks never count as the required zero input.
Watchdog emits zero on every tick more than 0.25s after the last received action.
Callers must continue ticking; there is no background timer. Acceleration is
limited by elapsed time, while magnitude reductions and stops are immediate.
Angular reversals brake to zero then accelerate in the opposite direction.
The first tick and any tick following a gap longer than the watchdog have zero
acceleration budget, preventing an idle interval from accumulating a burst.
Invalid/backwards clock readings are rejected before emission.

Each emitted command has a sequence, timestamp, source and reason codes in the
interface history. CLI output writes `commands.jsonl` with those records and
`summary.json` with reason counts, per-axis maximum absolute change between
consecutive ticks, `simulation_only: true`, transport name and uncalibrated units.
Reasons are `ok`, `clamped`, `rate_limited`, `watchdog_zero`, `estop_latched`,
`invalid_input`, and `supervisor_stop`; clamped acceleration can record both
`clamped` and `rate_limited`. All results are synthetic/offline simulation,
separate from real hardware acceptance, which remains untested.

## Run2 session export and measured checklist (software only)

These read-only tools consume existing local logs. They never open a camera,
connect to a stream, discover a device or send commands. Use a fresh output path:

```sh
./scripts/dev.sh p3-python -m p3.research.real_session to-control-dataset artifacts/my-session --output artifacts/real-control-001
./scripts/dev.sh p3-python -m p3.research.run2_acceptance artifacts/my-session --report artifacts/run2-001.md --json artifacts/run2-001.json
```

Supported inputs are the actual `p3.cli run` output folder (`events.jsonl`,
optionally `run.json` and `run-status.json`), and a complete
`p3.research.recorder.record_media` v2 bundle (`records.jsonl` and
`manifest.json`). V2 structure/hashes are checked with the existing bundle
reader; missing original media is allowed, existing media integrity is checked,
and no pixels are decoded. Bare records JSONL and arbitrary PID/controller
logs are not supported. Both existing writers record rule-controller output;
the converter does not rerun a teacher or invent PID labels. Missing teacher
commands, invalid timestamps, mismatched frame decisions and invalid commands
are refused before dataset output is opened. Geometry absent from an event
journal remains null; `run.json` adds tracks, but does not record image dimensions.
V2 provides dimensions and controller-selected target IDs.

Recorded session observations default to `real`, including local video recordings,
even though commands remain normalized software simulation commands. This is
source classification, not proof of physical execution. V2 bundles whose detector
kind contains `synthetic` are classified as simulated.
Synthetic fixtures that mimic camera metadata must include
`session-provenance.json` containing `{"kind":"simulated"}`; this marker can
only downgrade evidence. Every new exported sample and episode has
`provenance: {kind, source_session, source_sha256}`. The source hash covers a
canonical mapping of the consumed file names to their SHA256s, including any
measurement/provenance sidecar. Dataset hashes, features, splits and stats use
the existing control-dataset helpers. Existing synthetic datasets remain
byte-identical: their absent provenance is inferable as simulated from
`closed_loop_simulation` and `synthetic_closed_loop`. Teacher labels are the
recorded rule output, **never physical actuator feedback**; gated commands and
independent supervisor state remain null.

The pipeline journal records elapsed monotonic emission times, frame indices,
software decisions and a final zero STOP. An error with type
`KeyboardInterrupt` records observable SIGINT receipt. A STOP command alone
does not establish when an operator requested it. `e2e_ms` includes acquisition
wait and rendering; it is not acquisition-to-decision frame age.
The recorder's processing age is likewise not camera exposure age.
Consequently existing logs commonly produce **NOT_MEASURED**.

For missing measurements, an optional local `run2-measurements.json` sidecar
uses the same session origin and seconds as the journal. It is an explicit
measurement/annotation contract, not output already supplied by the pipeline:

```json
{
  "clock": "session_elapsed_monotonic",
  "operator_stops": [{"time_seconds": 1.0}],
  "frames": [
    {"frame": 0, "age_seconds": 0.04, "too_close": false,
     "target_identity": "reviewed-person-A"}
  ]
}
```

Supply acquisition-to-decision `age_seconds` for **every** processed frame,
and `too_close` booleans for every journal frame (from reviewed geometry or
independent annotation). At least one too-close event must be exercised.
A zero forward command in its frame or the next processed frame satisfies the
one-frame deadline. Supply `operator_stops` onset timestamps (STOP/SIGINT
receipt, not zero-command timestamps); each is matched to the first subsequent
journalled zero linear **and** angular software command. SIGINT error events
also supply onsets. Never substitute the earlier unrelated 0.042s measurement.

Continuity requires `run.json` tracks and a reviewed `target_identity` on
each selected frame. ID switches count changes of selected tracker ID for the
same annotated person; loss segments count entries into absent/non-tracked
selected-target intervals. An intentional selection of another person is not
an ID switch. These annotations are necessary because tracker IDs alone cannot
prove physical identity continuity. No selected target means NOT_MEASURED.

`run2_acceptance.Thresholds` is the single threshold definition:
frame age nearest-rank p95 <= **0.5s** (the stream stale timeout/follow max age),
maximum stop latency <= **0.2s**, latest-frame replacement fraction <= **0.05**,
ID switches <= **0**, lost segments <= **0**. CLI overrides:
`--max-frame-age-p95`, `--max-stop-latency`, `--max-drop-fraction`,
`--max-id-switches`, `--max-lost-segments`.
Drops use the final `run-status.json.stream_dropped_frames` divided by
processed plus replaced frames. These are the stream reader's cumulative
latest-frame replacements, not sensor/network packet drops; a missing final
counter is NOT_MEASURED. Thresholds cannot recover missing measurements.

Reports show provenance, source hashes, values, thresholds and per-item
PASS/FAIL/NOT_MEASURED. Overall PASS requires every item PASS. Exit codes:
0 overall PASS, 1 FAIL/incomplete measurements, 2 malformed input or I/O error.
Report/dataset destinations must be new. **Synthetic fixture PASS is NOT a
hardware acceptance**, and real-input software-log PASS still requires the
separate physical checks in HARDWARE.md.
