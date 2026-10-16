# Phase 0 — 2026-10-16

Checked all p3 modules, entry scripts, both existing test files, README/HARDWARE,
STATUS/commands/test/environment/source records, original Run1/follow_human/exact
uiview as read-only text, and both course DOCX requirements. Run1 PC YOLO and Run2
C2C/Wi-Fi/UI remain the required scope. No robot/SSH/network operation is allowed.

Fresh baseline: 50 tests PASS, no SKIP, before changes. Existing detector keeps one
ORT session, 640x416 BGR direct resize, objectness and class-agnostic NMS. Reuse it.
Tracker is deterministic one-to-one greedy IoU with max_missed=5, no appearance or
motion model. It auto-picks the largest first target; missing target ID is not
silently replaced. There is no identity ground truth, tracking evaluator or follow
controller. Camera entry and recording already exist; add screenshots/cancellation,
status logs and safe simulated decisions to that pipeline, not another detector.

Webcam authorization query: notDetermined, not authorized. Do not change permission
or open an unapproved session. Live camera/keyboard validation BLOCKED; provide a
manual command. No real MOT dataset locally; use annotated synthetic box fixtures
for evaluator logic, real file runs for runtime/proxy evidence only.

Planned changes: p3/tracking.py validation/selection, p3/pipeline.py event recording
and safe cleanup, p3/cli.py options, p3/evaluation.py optional tracking timings;
new p3/follow.py, p3/tracking_eval.py, p3/scenarios.py and validation runner/tests.
Original 50 tests stay intact. No P1/P2 dependencies, professor files or model edits.
Snapshot protected-before.json records 273 non-P3 files plus original sources.
