# Project 3 verification status — 2026-10-21

Current local verification: **286 tests, OK (skipped=8)**, 11.898 s. This docs-only
check used the user-authorized existing `/workspace/scratch/venv-p3/bin/python`
from `projects/project3`; Docker is unavailable on this box. No new Docker or
hardware execution is claimed. Supported reproduction remains `./scripts/dev.sh`.

The user-reported Mac `develop` **131faef** full local health check passed
**472 tests across projects**, including **276 Project 3 tests at that revision**.
Mac webcam/network stream software STOP was about **0.05 s after SIGINT**.
Those observations are revision-specific and do not establish actuator latency.
Historical [107-test validation](validation-20261016/REPORT.md) and
[163-test Docker validation](docker-20261021/RESULTS.md) retain their original scope.

| Component | Current software status | Evidence / limit |
|---|---|---|
| Run1 YOLO image/video, geometry, EOF and file benchmark | Implemented; software verified | Existing model/file evidence and tests; no labeled detection accuracy claim |
| Tracking/overlay and target selection | Implemented; software verified | Greedy IoU production default; manual display keys still pending |
| `kalman_iou` and tracker benchmark | Implemented; synthetic verified | `tests/test_motion_tracking.py`; synthetic crossings/motion/occlusion/jitter/dropout, no real identity claim |
| MOT/CVAT import and `evaluate --trackers all` | Implemented; offline verified | `tests/test_mot_import.py`; compares greedy_iou/hungarian/kalman_iou; real reviewed annotations pending |
| Webcam/network `stream:` latest-frame reader | Implemented; automated tests and Mac smoke | `tests/test_stream.py`; Mac STOP ~0.05 s after SIGINT; full manual acceptance pending |
| PID follow and `pid_sim` | Implemented; simulation verified | `tests/test_pid_follow.py`; authored kinematic scenarios, no physical dynamics validation |
| `p3_control_dataset/1.0` | Implemented; offline verified | `tests/test_control_dataset.py`; synthetic teacher data and recorded software labels |
| Ridge/MLP behaviour cloning | Implemented; simulation/offline verified | `tests/test_bc_baseline.py`; no real driving or stability guarantee |
| Too-close hard stop | Implemented; software verified | SafetySupervisor, width-based 1.0 m threshold, zero forward speed/no reverse; `tests/test_too_close_stop.py`; cannot guarantee clearance from an approaching person |
| Body interface | Implemented; mock/dry-run verified | `tests/test_body_interface.py`; watchdog, e-stop latch, rate/acceleration limits; `simulation_only=True`; real transport refused |
| Run2 session export and acceptance checker | Implemented; software verified | `tests/test_real_session.py`, `tests/test_run2_acceptance.py`; log PASS is not hardware acceptance |
| Run2 pipeline measurements | Implemented; software verified | `tests/test_run2_logging.py`; frame age, too_close gate/safety_stop, operator_stop and replacement counters |
| Report 3 figures | Implemented; synthetic/offline verified | `tests/test_report3_figures.py`; CSV/Markdown/PNG, missing evidence stays explicit |
| Real tracking accuracy | NOT TESTED | Human CVAT annotation/review and real multi-person evaluation pending |
| Run2 target identity continuity | NOT_MEASURED without annotation | Requires reviewed `target_identity` per selected frame; tracker IDs cannot establish person identity |
| Physical Run2 real-car/Wi-Fi/SSH/UI | NOT TESTED | [Hardware checklist](../HARDWARE.md); API doubles do not exercise cereal serialization/msgq or a real device |
| Physical C2C/comma body control | NOT IMPLEMENTED by design | Separate safety review required; no real transport |

New pipeline logs automatically supply acquisition/decision frame age, `too_close`,
`safety_stop` episode onsets, operator-stop onsets and cumulative latest-frame
replacement counters. Stop latency remains NOT_MEASURED when no operator stop
was requested. Missing older fields can use the documented measurement sidecar.
Zero too-close events can pass coverage only; they do not demonstrate a triggered
stop. Replacement counters are not sensor/network packet loss measurements.

Remaining user/hardware work: real-car Run2 session/acceptance; real CVAT
annotation/evaluation; manual `q/c/n/r/s` with `--display`; online Gemini call
(API key required); Report 3 write-up/slides due **2026-12-25**. Physical control
requires a separate safety review. Synthetic/offline PASS and real-input software
logs remain separate from physical acceptance.

See the [ordered guide](../README.md), [verified commands](COMMANDS.md) and
[requirements audit](../../../docs/PROJECT3.md). No Python behavior changes,
commit/push, device access or historical evidence rewrites accompany this sync.
