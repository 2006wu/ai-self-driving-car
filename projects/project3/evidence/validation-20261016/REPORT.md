# Project 3 — Software Validation Report (2026-10-16)

This report separates executed file/model tests, synthetic box metrics,
injected failures and untested camera/device behavior. No commit or push.

## A. Implementation summary

The existing detector, capture/render pipeline and greedy one-to-one IoU
tracker are reused. Association remains IoU >= .3, max_missed = 5;
no motion model, embeddings, re-identification or tracker replacement.

`Image/video/opt-in camera → baseline YOLO → person tracks → explicit target
selection → target state → simulated decision → local event/recording files`.

| File | Change |
|---|---|
| p3/follow.py (new) | Explicit-selection state machine; loss/ambiguity/stale-frame STOP latch; normalized simulated speed/turn |
| p3/tracking_eval.py (new) | Validated annotation schema, exact global identity assignment, ID/fragment/continuity/recovery metrics |
| p3/scenarios.py (new) | Twelve authored single/multiple-person/occlusion box sequences |
| p3/tracking.py | Validate before mutation; explicit visible selection/cancel; original association preserved |
| p3/pipeline.py | Capture startup cleanup, early EOF/empty frame errors, HUD/keys, flushed events, final STOP, recording/status and bounded runs |
| p3/cli.py | Simulation/selection/deadline/recording flags, tracking evaluation commands and readable error exits |
| p3/evaluation.py | Optional tracking/decision stage timings, process CPU/RSS and person-count distributions |
| validate_vision.py (new) | Nine local benchmark conditions and five synthetic tracker workloads |
| tests/test_validation.py (new) | Failure/state/metrics/cleanup/measurement regression tests |
| report_validation.py, summarize.py, README, docs/PROJECT3.md, evidence | Rebuildable measured report and scoped acceptance |

Simulation starts IDLE; tracker auto-selection alone cannot arm it. `n` or
`--target-id` explicitly selects, emitting TARGET_SELECTED with zero output.
Subsequent unambiguous frames may emit TRACKING/FOLLOW. Missing targets emit
zero immediately, progress through TARGET_TEMPORARILY_LOST/TARGET_LOST and
latch stopped. Reappearance requires explicit confirmation, even for the
same ID. IoU >= .15 with another visible person stops; overlapping selection
cannot arm. Cancel/quit/errors override FOLLOW. Invalid tracking data faults
require a new session; other latched stops require explicit re-selection.
EOF/limits/interruption always end with a simulated STOP. Follow uses box
width/center heuristics, not physical distance, calibrated control or identity.

Important limits: an identity swap without observed loss/overlap can evade
the policy. The .5-second stale-frame check and max-seconds limit cannot
interrupt a blocked native capture/inference call. Unknown-length video
read failure cannot always be distinguished from EOF. Filesystem failure
can prevent durable logs. No physical safety or hard real-time claim.

## Tests and regression

- Original tests: 50 PASS; both original test files are byte-identical to the pre-task copies.
- New tests: 57 PASS. Total: **107 PASS / 0 FAIL / 0 SKIP**.
- Project 2 offline regression: **96 PASS**; no external API calls.
- Protected files: **273 checked, 0 changed** (P1/P2, other existing docs/reports and professor sources).
- P1 runtime was NOT TESTED this phase; preservation is not a runtime pass.
- Camera, disconnect and GUI-key fault tests use injected doubles; no live-device pass.
- Early unsuccessful test runs are retained as tests-first.txt; tests-final.txt is the final suite.

## B. Tracking evaluation

Source: authored deterministic bounding-box trajectories with known synthetic
IDs. They exercise association and evaluator logic, not YOLO detections on
real people. No dataset download. GT remains present during synthetic missed
detections; the short-exit sequence has no GT while out of view.

| Synthetic scenario | IDF1 | ID precision | ID recall | Switches | Fragments | Recovery | Continuity matched / longest (GT 1) |
|---|---:|---:|---:|---:|---:|---:|---|
| A_left | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| A_right | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| A_approach | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| A_recede | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| A_short_exit | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | 1.000 | 1.000 / 0.579 |
| B_simultaneous_opposite | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| B_crossing | 0.5476 | 0.5476 | 0.5476 | 2 | 0 | N/A | 1.000 / 1.000 |
| B_close_parallel | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| B_partial_overlap | 1.0000 | 1.0000 | 1.0000 | 0 | 0 | N/A | 1.000 / 1.000 |
| C_short_occlusion | 0.9268 | 1.0000 | 0.8636 | 0 | 1 | 1.000 | 0.864 / 0.500 |
| C_long_occlusion | 0.4348 | 0.5556 | 0.3571 | 1 | 1 | 0.000 | 0.643 / 0.357 |
| C_occluded_separation | 0.4675 | 0.5143 | 0.4286 | 2 | 2 | 0.000 | 0.833 / 0.429 |

The crossing occurs between sampled positions to expose ID swaps; an exactly
symmetric sampled crossing can accidentally hide this failure. Short occlusion
recovers the same synthetic ID; long occlusion exceeds retention, creates a
new ID and cannot authorize automatic following. Partial overlap can retain
tracker IDs while the separate follow policy correctly remains stopped.

IDTP maximizes sequence-wide IoU-qualified pair counts under one global ID
assignment; IDFN = GT detections - IDTP, IDFP = predictions - IDTP.
IDF1 = 2 IDTP / (GT detections + predicted detections). Per-frame matching
maximizes match count then IoU at .5. Switches compare each GT ID with its
last matched prediction ID including gaps. Fragmentation is matched →
unmatched while GT present → matched; GT absence alone is not an FN.
Continuity is matched-visible and longest-consecutive fractions; frame-index
gaps break a consecutive streak. Recovery is completed gaps returning to the
initial ID; no eligible gap means N/A. All GT IDs are in the raw JSON.

The global identity matching approach follows the primary
[TrackEval Identity implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/identity.py).
This small evaluator does not implement MOTChallenge ignore-region/class/
visibility preprocessing and is not a certified benchmark implementation.
Annotations must explicitly declare synthetic_ground_truth or human_ground_truth;
declaring the latter does not independently verify annotation quality.

### Real-file proxies and qualitative observations

The complete road video has 10 frames with person predictions and
8 unique predicted track IDs. These are **proxies only**;
they cannot yield real ID switches, IDF1, precision/recall, identity recovery
or mAP without annotations. Real tracking accuracy remains NOT TESTED.
Visual inspection of the sample overlay shows the baseline bus labeled
airplane. This known qualitative error is preserved and not relabeled as
success. Objectness is not calibrated class confidence. No driving-quality claim.

## C. Performance report

Hardware: Apple M3, 24 GiB RAM; macOS-26.6.2-arm64-arm-64bit; Python 3.11.4.
Packages: `{"numpy": "1.26.4", "onnx": "1.17.0", "onnxruntime": "1.20.1", "opencv-python": "4.10.0.84", "psutil": "6.1.1"}`.
Model: original yolov5n_flat.onnx, SHA256
`bf667e5041e89ffaf1faa17c1ecbcf2d87729a514486a46c1996682342386031`.
Fixed input 1×3×416×640, BGR/direct resize/objectness/class-agnostic NMS.
CPU intra-op threads = 1. CoreML has CPU fallback (runtime logs: 230/237
nodes supported in 4 partitions); no GPU-only utilization claim.

Each condition has 5 excluded warmup forwards and 30 measured frames.
Video reopens after warmup; image measurements reuse a resident image.
Source-size overrides do not change the model tensor size. Only the image
provides several detected people; first-30-frame road benchmark has few/no
people. Synthetic box load is reported separately below.

Detection FPS = 1000 / mean(preprocess + inference + postprocess).
Inference FPS uses inference alone; file pipeline FPS includes decode/
resize/render and optional tracking/decision. It excludes model construction,
source opening, export, display and camera capture. No value is webcam FPS.

| Condition | Inference FPS | Detection FPS | File pipeline FPS | Inference mean ms | Tracking mean / P95 ms | E2E median / P95 / std ms | CPU % | RSS sampled max MiB | Person count mean |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| coreml-image | 157.86 | 134.61 | 126.61 | 6.33 | disabled | 7.87 / 9.14 / 0.61 | 88.4 | 351.4 | 4.00 |
| coreml-track-follow | 153.85 | 131.43 | 119.85 | 6.50 | 0.1972 / 0.2221 | 8.20 / 9.26 / 0.73 | 88.0 | 357.4 | 4.00 |
| coreml-video | 158.67 | 129.02 | 104.36 | 6.30 | 0.0126 / 0.0164 | 9.07 / 11.35 / 2.17 | 191.0 | 400.9 | 0.00 |
| cpu-conf50 | 23.89 | 23.18 | 22.72 | 41.86 | 0.2079 / 0.2274 | 43.75 / 45.61 / 0.86 | 100.9 | 287.9 | 4.00 |
| cpu-image | 24.44 | 23.77 | 23.50 | 40.92 | disabled | 42.10 / 44.88 / 1.32 | 100.6 | 211.7 | 4.00 |
| cpu-source-large | 23.06 | 22.41 | 21.04 | 43.37 | 0.2140 / 0.2392 | 44.22 / 50.39 / 14.99 | 105.1 | 287.7 | 4.00 |
| cpu-source-small | 24.27 | 23.64 | 23.15 | 41.20 | 0.2010 / 0.2210 | 42.78 / 45.84 / 1.29 | 101.9 | 251.5 | 4.00 |
| cpu-track-follow | 24.43 | 23.75 | 23.33 | 40.93 | 0.1966 / 0.2099 | 42.72 / 43.95 / 0.55 | 101.0 | 225.7 | 4.00 |
| cpu-video | 24.31 | 23.47 | 22.45 | 41.14 | 0.0142 / 0.0167 | 44.02 / 46.06 / 2.28 | 123.5 | 326.1 | 0.00 |

Full mean/median/P95/population-std/count and per-frame observations, detection
and objectness distributions, input/model/source hashes are in each JSON.
CPU percent uses process CPU time / wall time, one core = 100%; it can exceed
100% and is not whole-machine utilization. CPU timing includes measured
source opening whereas per-frame E2E excludes it. RSS samples are process
memory, not continuous peaks or GPU memory. Conditions run sequentially in
one process, so RSS can retain prior allocations; do not infer isolated
backend memory efficiency or a memory leak from these differences.

| Synthetic person boxes | Measured updates | Tracker mean / median / P95 / std ms |
|---|---:|---|
| 1 | 1000 | 0.0145 / 0.0143 / 0.0164 / 0.0015 |
| 2 | 1000 | 0.0492 / 0.0483 / 0.0536 / 0.0032 |
| 5 | 1000 | 0.2876 / 0.2864 / 0.3012 / 0.0093 |
| 10 | 1000 | 1.1408 / 1.1310 / 1.1952 / 0.0604 |
| 20 | 1000 | 4.5317 / 4.5106 / 4.7211 / 0.1454 |

These box-only workloads isolate tracker cost; they are not multi-person
detector/camera throughput measurements.

### Complete video stability run

- 1200 input frames processed, 1200 recorded AVI frames decoded; termination EOF.
- Wall 60.71 s; session throughput 19.77 FPS including export/journal/opening.
- Frame processing mean/P95: 43.74/45.08 ms; loop incl. export mean/P95: 50.54/52.07 ms.
- Tracking mean/P95: 0.0083/0.0098 ms; CPU 117.8%.
- RSS sampled min/max: 187.2/293.1 MiB; first/last: 187.2/293.1 MiB.
- 0 error events; cleanup errors: []; final simulated action STOP.
- Video simulation deliberately remains IDLE without explicit selection; follow movement/loss/rearm are exercised in deterministic tests, not claimed from this road clip.
- Application-skipped frames: 0 (no intentional skipping). Sensor/camera drops: N/A.
- One roughly minute-long file run is not a multi-hour soak or live-camera stability test.

## D. Acceptance status

| Component | Status | Evidence | Scope / limitation |
|---|---|---|---|
| YOLO image/video | **PASS** | image-final-summary.json; stability-final-summary.json | Actual local model/image and 1200 video frames; no accuracy claim |
| Webcam live detection | **BLOCKED** | camera-authorization.txt | AVFoundation notDetermined; no capture/permission change |
| Multi-person tracking software | **PASS** | tests-final.txt; final-measurements/tracking-synthetic.json | Association and failure cases verified with synthetic boxes |
| Real tracking accuracy | **NOT TESTED** | REPORT.md tracking section | No human-annotated real multi-person clips |
| Crossing identity stability | **FAIL** | B_crossing synthetic fixture | 2 ID switches; known greedy IoU limitation |
| Target selection | **PASS** | tests-final.txt; image-final-summary.json | Logic/headless model run; actual keyboard interaction NOT TESTED |
| Follow decision simulation | **PASS** | tests-final.txt; stability-final-summary.json | Dimensionless local output; explicit selection and rearm |
| Safety handling software | **PASS** | tests-final.txt | Injected camera/model/GUI/IO faults; not physical safety |
| Performance benchmark | **PASS** | final-measurements/*.json | File-input CPU/CoreML and synthetic tracker workloads |
| Actual native keyboard interaction | **NOT TESTED** | README manual command | Injected key events only this phase |
| Physical C2C | **NOT TESTED** | ../../HARDWARE.md | Deferred by user; no SSH/Wi-Fi/device operations |

PASS here applies only to its stated scope. The crossing FAIL describes the
unchanged tracker, while the regression suite PASS means the test correctly
detects that limitation. Physical C2C is deferred, not counted as a test skip.

## Reproduction and evidence map

See [README](../../README.md) for full commands/schema/keys and manual webcam
acceptance. Commands from repository root:

```sh
./projects/project3/verify.sh
projects/project2/agent/.venv/bin/python -m unittest discover -s projects/project2/agent -p '*_tests.py' -v
./projects/project3/run.sh run artifacts/inputs/usa.hevc --track --simulate-follow --max-frames 2000 --output artifacts/my-stability-run
./projects/project3/run.sh run 0 --camera --display --track --simulate-follow --max-frames 300 --max-seconds 30 --output artifacts/webcam-manual-01
cd projects/project3
.venv/bin/python validate_vision.py --output evidence/my-new-measurements
.venv/bin/python summarize.py
```

The webcam command is for user-run validation only; it was not executed in
this phase. Output directories/files must be new; do not overwrite evidence.
Raw media and verbose run/event records are local ignored artifacts under
`artifacts/validation-20261016/`. Small summaries, hashes, timings and test logs
are retained here. `final-measurements/` is authoritative; `measurements/` is
the earlier pre-final-fix run and is retained for history. Neither downloads
nor source opening are included in benchmark E2E. No Docker is needed with
the existing local model/video. Initial dependency/source audits are in AUDIT.md.

## Remaining work and presentation readiness

- **Software implementation:** confirmed limitations remain motion/ReID tracking, a hard external watchdog for native hangs, and a version-matched real C2C adapter once firmware/API are known. Choose tracker changes after real evaluation; no replacement is claimed here.
- **Software validation:** user-run camera permission/capture/disconnect/GUI-key checks; annotated real single/multiple-person/crossing/occlusion clips; real ID metrics and adverse-scene/multi-hour stability tests.
- **Hardware integration:** actual C2C model/firmware, device bindings, Wi-Fi/SSH and UI acceptance remain deferred; no physical following verification.
- **Presentation:** ready to present the measured **software stage and its limits**. Not ready to claim full Run2 completion or real tracking accuracy. No PPTX generated this phase.

Suggested 14-slide structure: (1) course scope, (2) audited starting point,
(3) shared pipeline architecture, (4) original model conventions, (5) image/
video evidence, (6) explicit target state machine, (7) failure/STOP behavior,
(8) tracking data and metric definitions, (9) synthetic results, (10) crossing/
occlusion failures, (11) CPU/CoreML timing scopes and comparison, (12) full
video stability and regression, (13) scoped acceptance including camera/C2C,
(14) annotated live validation and next steps.
