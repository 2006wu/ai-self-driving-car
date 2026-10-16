# Project 3 verification status — 2026-10-14

Branch `develop`; HEAD `0098f886e078cacbe08eb2d1282922cd78b5b1dc`. No commit or push.
P3.0 audit complete; independent file-input implementation and evaluation verified.
Webcam and actual C2C remain pending. User confirmed no available/confirmed C2C for this phase; continue software work only.

## Final acceptance matrix

| Category | Item | Classification | Status | Evidence | Limitation |
|---|---|---|---|---|---|
| Run1 | Adapted image YOLO + boxes/class/objectness | Required baseline / source-defined image mode | PASS | tests-final.txt; artifacts/final-preview | Original preview.png absent; unchanged professor GUI not run |
| Run1 | Real USA video + EOF | Source option / Engineering verification | PASS | full-video-summary.json; artifacts/full-video | 1200 decoded frames, cap 2000; no driving accuracy claim |
| Run1 | Camera open/close | Source option / Engineering verification | NOT RUN | camera-capability.txt | AVFoundation authorization notDetermined; capture pending OS permission |
| Run1 | Model IO / baseline parity / coordinates / single session | Engineering | PASS | 7 model + 12 geometry tests | BGR/objectness/class-agnostic NMS preserved |
| Run1 | Benchmark | Engineering / Extension | PASS | final-*.json; supplemental.json | File pipeline, no camera/accuracy metrics |
| Run2 | Requirement + source / Level A | Required preparation | PASS | source-audit.json; docs/PROJECT3.md | Actual device schema/version unknown |
| Run2 | Process/message API test double / partial Level B | Engineering | PASS within API scope | 8 Run2 + 1 invalid-UI cleanup test; run2-mock.json | No real cereal serialization, msgq, SSH or Wi-Fi |
| Run2 | Wi-Fi/SSH communication setup | Required | BLOCKED | HARDWARE.md | User deferred hardware; no available/confirmed device |
| Run2 | Device UI / Level C physical C2C | Required | BLOCKED | HARDWARE.md | No real device integration performed |
| Do New | Person tracking + persistent IDs / target selection | Extension | PARTIALLY VERIFIED | 10 tracker tests; full-video-summary.json; artifacts/final-preview | Synthetic box association + real detector execution; no annotated MOT accuracy |
| Do New | OpenCV overlay dashboard | Extension | PARTIALLY VERIFIED | PNG visual inspection; GUI cleanup test; native-gui.txt | Visual OS interaction observation unavailable; no live network status |
| Do New | Robustness probes | Extension | PARTIALLY VERIFIED | supplemental.json; tests-final.txt | Synthetic darkness/blur/occlusion and 1000 tracker updates; real adverse scene trials pending |
| Regression | P2 Agent offline | Engineering | PASS | p2-regression.txt | 44/44 offline; no provider/API calls |
| Regression | Existing P1/P2 + professor source preservation | Engineering | PASS | preservation.json | 261 pre-task files compared; only intended docs changed |
| Regression | P1 compose configuration | Engineering | PASS | docker compose config --quiet exit 0 | Services absent before work; replay/UI runtime NOT TESTED |

## Actual tests

Final Project 3 suite: **50 executed, 50 PASS, 0 FAIL, 0 SKIP**.
Geometry 12; inputs/EOF/errors/stats 9; real-model integration 7; Run2 API 8;
benchmark integration 2; dashboard/API-invalid-data cleanup 2; tracking 10.
Camera failures and GUI keys in unit tests are injected doubles, not real hardware passes.
Project 2 regression: **44/44 PASS**. P1 runtime and TF training were not rerun.

## Measured performance

Each scenario has five excluded warm-up forwards. CPU intra-op threads=1.
FPS = 1000 / mean latency; model input remains 640×416. Source size is varied separately.
CoreML has CPU fallback partitions (230/237 nodes supported, 4 CoreML partitions).
These numbers characterize this machine/run; no GPU-only or universal acceleration claim.

| Scenario | n | Inference mean / median / P95 / std ms | Inference FPS | File E2E mean / P95 ms | File FPS | RSS sampled max MiB |
|---|---:|---|---:|---|---:|---:|
| CPU image | 30 | 40.46 / 40.30 / 41.49 / 0.55 | 24.72 | 42.08 / 43.12 | 23.77 | 201.9 |
| CPU video short | 20 | 42.82 / 42.33 / 46.23 / 1.84 | 23.35 | 46.81 / 53.44 | 21.36 | 282.4 |
| CPU video long | 120 | 40.71 / 40.56 / 42.00 / 0.63 | 24.56 | 43.74 / 45.36 | 22.86 | 305.8 |
| CPU source 640×480 | 30 | 42.79 / 42.93 / 45.83 / 2.05 | 23.37 | 44.68 / 48.15 | 22.38 | 217.9 |
| CPU source 1920×1080 | 30 | 40.73 / 40.60 / 42.06 / 0.61 | 24.55 | 43.68 / 45.38 | 22.89 | 265.5 |
| CPU confidence .5 | 30 | 40.72 / 40.44 / 42.24 / 0.67 | 24.56 | 42.38 / 44.20 | 23.60 | 221.8 |
| CoreML+CPU image | 30 | 6.33 / 6.28 / 7.07 / 0.41 | 158.02 | 7.86 / 8.63 | 127.17 | 264.2 |

Full pre/inference/post/render/acquisition stage mean/median/P95/std/count,
RSS, detection counts, objectness distribution and observations are in each JSON.
Image scope: resident frame + preprocessing + inference + postprocessing + overlay.
Video adds frame decode. Optional source resize is timed. Source opening, exports,
GUI display, tracking and camera capture are excluded; not camera end-to-end latency.
RSS is sampled process memory, not continuous peak or GPU memory.

## Model construction and provider output differences

- CPUExecutionProvider: n=5, mean 13.57, median 13.04, P95 14.63, std 0.81 ms.
- CoreMLExecutionProvider: n=5, mean 932.04, median 921.96, P95 972.50, std 26.62 ms.

Construction includes ONNX read/check, class metadata and session creation;
five repeated constructions use warm OS caches and exclude interpreter startup.
Provider raw output mean/max absolute difference: 0.004386 / 18.611328.
On this single image both emit five detections with the same class/rank sequence;
max corresponding box-coordinate difference is about 0.69 source pixels and max
objectness difference about 0.0047. Not bitwise/numerically equivalent and not an
accuracy validation. CPU remains the professor-parity baseline.

## Robustness / qualitative limitations

| Deterministic image probe | Detections | Person predictions |
|---|---:|---:|
| original | 5 | 4 |
| low_light_25pct | 4 | 4 |
| motion_blur_horizontal | 1 | 1 |
| partial_occlusion | 3 | 2 |
| all_black | 0 | 0 |

These counts are outputs, not true/false-positive or recall measurements.
Visual inspection of the baseline sample shows the bus box labeled airplane;
this is a qualitative model error worth investigating separately. Class indexing
and objectness presentation follow the original program. No labeled precision,
recall, mAP or real-person identity/physical-following claim is made.
Road-video full run had 10 frames with person predictions and 8 predicted track IDs;
neither count establishes that real people were correctly tracked.

## Remaining work in priority order

1. Supply actual C2C model/firmware/network information, then implement version-matched
   bindings and verify real cereal/UI/Wi-Fi/SSH with rollback and hardware evidence.
2. Grant native camera permission and run bounded acquisition/open/close/disconnect tests;
   validate actual GUI target cycling/quit through visual interaction.
3. Collect annotated multi-person motion/occlusion/crossing clips; measure ID switches
   before choosing a more capable tracking algorithm.
4. Investigate baseline color/class/confidence conventions in a separate controlled
   experiment; retain current reference-parity baseline.
5. Add real adverse-scene/extended duration trials; prepare final report after hardware
   status and results are known.

## Verification summary

**VERIFIED:** source audit, native environment, model/image/video file inference,
geometry/EOF/error handling, stage benchmarks, API-double lifecycle, P2 offline regression.
**PARTIALLY VERIFIED:** tracking, dashboard and robustness (limited sources/test doubles).
**BLOCKED:** actual Run2 hardware integration pending actual device information.
**NOT TESTED:** camera capture, real C2C transport/UI, P1 replay runtime this session,
annotated detection/tracking accuracy, physical human following.
No commit/push, professor source edits, P1/P2 dependency changes or volume deletion.
