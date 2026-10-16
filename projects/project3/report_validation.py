"""Rebuild the 2026-10-16 report from saved measurements; no inference or devices."""
import json
import re
from pathlib import Path


BASE = Path(__file__).resolve().parent
EVIDENCE = BASE / 'evidence/validation-20261016'


def load(name):
    return json.loads((EVIDENCE / name).read_text())


def test_result(name):
    text = (EVIDENCE / name).read_text()
    count = int(re.search(r'Ran (\d+) tests?', text).group(1))
    if not text.rstrip().endswith('OK'):
        raise ValueError(f'{name}: expected an unskipped successful suite')
    return count


def build():
    total = test_result('tests-final.txt')
    original = test_result('baseline-before.txt')
    p2 = test_result('p2-regression-current.txt')
    stability = load('stability-final-summary.json')
    preservation = load('preservation-final.json')
    environment = load('environment-final.json')['environment']
    hardware = load('hardware-final.json')
    fixtures = load('final-measurements/tracking-synthetic.json')
    run = stability['status']
    if run['status'] != 'PASS' or not preservation['pass']:
        raise ValueError('stability/preservation failed; report needs investigation')
    matrix = [
        ('YOLO image/video', 'PASS', 'image-final-summary.json; stability-final-summary.json', 'Actual local model/image and 1200 video frames; no accuracy claim'),
        ('Webcam live detection', 'BLOCKED', 'camera-authorization.txt', 'AVFoundation notDetermined; no capture/permission change'),
        ('Multi-person tracking software', 'PASS', 'tests-final.txt; final-measurements/tracking-synthetic.json', 'Association and failure cases verified with synthetic boxes'),
        ('Real tracking accuracy', 'NOT TESTED', 'REPORT.md tracking section', 'No human-annotated real multi-person clips'),
        ('Crossing identity stability', 'FAIL', 'B_crossing synthetic fixture', '2 ID switches; known greedy IoU limitation'),
        ('Target selection', 'PASS', 'tests-final.txt; image-final-summary.json', 'Logic/headless model run; actual keyboard interaction NOT TESTED'),
        ('Follow decision simulation', 'PASS', 'tests-final.txt; stability-final-summary.json', 'Dimensionless local output; explicit selection and rearm'),
        ('Safety handling software', 'PASS', 'tests-final.txt', 'Injected camera/model/GUI/IO faults; not physical safety'),
        ('Performance benchmark', 'PASS', 'final-measurements/*.json', 'File-input CPU/CoreML and synthetic tracker workloads'),
        ('Actual native keyboard interaction', 'NOT TESTED', 'README manual command', 'Injected key events only this phase'),
        ('Physical C2C', 'NOT TESTED', '../../HARDWARE.md', 'Deferred by user; no SSH/Wi-Fi/device operations'),
    ]
    lines = ['# Project 3 — Software Validation Report (2026-10-16)', '',
             'This report separates executed file/model tests, synthetic box metrics,',
             'injected failures and untested camera/device behavior. No commit or push.', '',
             '## A. Implementation summary', '',
             'The existing detector, capture/render pipeline and greedy one-to-one IoU',
             'tracker are reused. Association remains IoU >= .3, max_missed = 5;',
             'no motion model, embeddings, re-identification or tracker replacement.', '',
             '`Image/video/opt-in camera → baseline YOLO → person tracks → explicit target',
             'selection → target state → simulated decision → local event/recording files`.', '',
             '| File | Change |', '|---|---|',
             '| p3/follow.py (new) | Explicit-selection state machine; loss/ambiguity/stale-frame STOP latch; normalized simulated speed/turn |',
             '| p3/tracking_eval.py (new) | Validated annotation schema, exact global identity assignment, ID/fragment/continuity/recovery metrics |',
             '| p3/scenarios.py (new) | Twelve authored single/multiple-person/occlusion box sequences |',
             '| p3/tracking.py | Validate before mutation; explicit visible selection/cancel; original association preserved |',
             '| p3/pipeline.py | Capture startup cleanup, early EOF/empty frame errors, HUD/keys, flushed events, final STOP, recording/status and bounded runs |',
             '| p3/cli.py | Simulation/selection/deadline/recording flags, tracking evaluation commands and readable error exits |',
             '| p3/evaluation.py | Optional tracking/decision stage timings, process CPU/RSS and person-count distributions |',
             '| validate_vision.py (new) | Nine local benchmark conditions and five synthetic tracker workloads |',
             '| tests/test_validation.py (new) | Failure/state/metrics/cleanup/measurement regression tests |',
             '| report_validation.py, summarize.py, README, docs/PROJECT3.md, evidence | Rebuildable measured report and scoped acceptance |', '',
             'Simulation starts IDLE; tracker auto-selection alone cannot arm it. `n` or',
             '`--target-id` explicitly selects, emitting TARGET_SELECTED with zero output.',
             'Subsequent unambiguous frames may emit TRACKING/FOLLOW. Missing targets emit',
             'zero immediately, progress through TARGET_TEMPORARILY_LOST/TARGET_LOST and',
             'latch stopped. Reappearance requires explicit confirmation, even for the',
             'same ID. IoU >= .15 with another visible person stops; overlapping selection',
             'cannot arm. Cancel/quit/errors override FOLLOW. Invalid tracking data faults',
             'require a new session; other latched stops require explicit re-selection.',
             'EOF/limits/interruption always end with a simulated STOP. Follow uses box',
             'width/center heuristics, not physical distance, calibrated control or identity.', '',
             'Important limits: an identity swap without observed loss/overlap can evade',
             'the policy. The .5-second stale-frame check and max-seconds limit cannot',
             'interrupt a blocked native capture/inference call. Unknown-length video',
             'read failure cannot always be distinguished from EOF. Filesystem failure',
             'can prevent durable logs. No physical safety or hard real-time claim.', '',
             '## Tests and regression', '',
             f'- Original tests: {original} PASS; both original test files are byte-identical to the pre-task copies.',
             f'- New tests: {total-original} PASS. Total: **{total} PASS / 0 FAIL / 0 SKIP**.',
             f'- Project 2 offline regression: **{p2} PASS**; no external API calls.',
             f'- Protected files: **{preservation["protected_files"]} checked, {len(preservation["changed"])} changed** (P1/P2, other existing docs/reports and professor sources).',
             '- P1 runtime was NOT TESTED this phase; preservation is not a runtime pass.',
             '- Camera, disconnect and GUI-key fault tests use injected doubles; no live-device pass.',
             '- Early unsuccessful test runs are retained as tests-first.txt; tests-final.txt is the final suite.', '',
             '## B. Tracking evaluation', '',
             'Source: authored deterministic bounding-box trajectories with known synthetic',
             'IDs. They exercise association and evaluator logic, not YOLO detections on',
             'real people. No dataset download. GT remains present during synthetic missed',
             'detections; the short-exit sequence has no GT while out of view.', '',
             '| Synthetic scenario | IDF1 | ID precision | ID recall | Switches | Fragments | Recovery | Continuity matched / longest (GT 1) |',
             '|---|---:|---:|---:|---:|---:|---:|---|']
    for item in fixtures['scenarios']:
        m = item['metrics']; recovery = m['target_recovery']['rate']; c = m['track_continuity']['1']
        rec = 'N/A' if recovery is None else f'{recovery:.3f}'
        lines.append(f'| {item["scenario"]} | {m["IDF1"]:.4f} | {m["ID_precision"]:.4f} | {m["ID_recall"]:.4f} | {m["ID_switches"]} | {m["track_fragmentations"]} | {rec} | {c["matched_visible_fraction"]:.3f} / {c["longest_consecutive_match_fraction"]:.3f} |')
    lines += ['', 'The crossing occurs between sampled positions to expose ID swaps; an exactly',
              'symmetric sampled crossing can accidentally hide this failure. Short occlusion',
              'recovers the same synthetic ID; long occlusion exceeds retention, creates a',
              'new ID and cannot authorize automatic following. Partial overlap can retain',
              'tracker IDs while the separate follow policy correctly remains stopped.', '',
              'IDTP maximizes sequence-wide IoU-qualified pair counts under one global ID',
              'assignment; IDFN = GT detections - IDTP, IDFP = predictions - IDTP.',
              'IDF1 = 2 IDTP / (GT detections + predicted detections). Per-frame matching',
              'maximizes match count then IoU at .5. Switches compare each GT ID with its',
              'last matched prediction ID including gaps. Fragmentation is matched →',
              'unmatched while GT present → matched; GT absence alone is not an FN.',
              'Continuity is matched-visible and longest-consecutive fractions; frame-index',
              'gaps break a consecutive streak. Recovery is completed gaps returning to the',
              'initial ID; no eligible gap means N/A. All GT IDs are in the raw JSON.', '',
              'The global identity matching approach follows the primary',
              '[TrackEval Identity implementation](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/identity.py).',
              'This small evaluator does not implement MOTChallenge ignore-region/class/',
              'visibility preprocessing and is not a certified benchmark implementation.',
              'Annotations must explicitly declare synthetic_ground_truth or human_ground_truth;',
              'declaring the latter does not independently verify annotation quality.', '',
              '### Real-file proxies and qualitative observations', '',
              f'The complete road video has {stability["proxies"]["frames_with_person_predictions"]} frames with person predictions and',
              f'{stability["proxies"]["unique_predicted_track_ids"]} unique predicted track IDs. These are **proxies only**;',
              'they cannot yield real ID switches, IDF1, precision/recall, identity recovery',
              'or mAP without annotations. Real tracking accuracy remains NOT TESTED.',
              'Visual inspection of the sample overlay shows the baseline bus labeled',
              'airplane. This known qualitative error is preserved and not relabeled as',
              'success. Objectness is not calibrated class confidence. No driving-quality claim.', '',
              '## C. Performance report', '',
              f'Hardware: {hardware["cpu"]}, {hardware["memory_bytes"]/1073741824:g} GiB RAM; {environment["platform"]}; Python {environment["python"]}.',
              f'Packages: `{json.dumps(environment["packages"], sort_keys=True)}`.',
              'Model: original yolov5n_flat.onnx, SHA256',
              '`bf667e5041e89ffaf1faa17c1ecbcf2d87729a514486a46c1996682342386031`.',
              'Fixed input 1×3×416×640, BGR/direct resize/objectness/class-agnostic NMS.',
              'CPU intra-op threads = 1. CoreML has CPU fallback (runtime logs: 230/237',
              'nodes supported in 4 partitions); no GPU-only utilization claim.', '',
              'Each condition has 5 excluded warmup forwards and 30 measured frames.',
              'Video reopens after warmup; image measurements reuse a resident image.',
              'Source-size overrides do not change the model tensor size. Only the image',
              'provides several detected people; first-30-frame road benchmark has few/no',
              'people. Synthetic box load is reported separately below.', '',
              'Detection FPS = 1000 / mean(preprocess + inference + postprocess).',
              'Inference FPS uses inference alone; file pipeline FPS includes decode/',
              'resize/render and optional tracking/decision. It excludes model construction,',
              'source opening, export, display and camera capture. No value is webcam FPS.', '',
              '| Condition | Inference FPS | Detection FPS | File pipeline FPS | Inference mean ms | Tracking mean / P95 ms | E2E median / P95 / std ms | CPU % | RSS sampled max MiB | Person count mean |',
              '|---|---:|---:|---:|---:|---|---|---:|---:|---:|']
    for path in sorted((EVIDENCE/'final-measurements').glob('*.json')):
        r = json.loads(path.read_text())
        if 'inference_fps' not in r:
            continue
        m = r['metrics']; t = m['tracking_ms']; e = m['e2e_ms']
        detection = 1000 / sum(m[k]['mean'] for k in ['preprocess_ms','inference_ms','postprocess_ms'])
        track = f'{t["mean"]:.4f} / {t["p95"]:.4f}' if r['tracking_enabled'] else 'disabled'
        lines.append(f'| {path.stem} | {r["inference_fps"]:.2f} | {detection:.2f} | {r["file_pipeline_fps"]:.2f} | {m["inference_ms"]["mean"]:.2f} | {track} | {e["median"]:.2f} / {e["p95"]:.2f} / {e["std"]:.2f} | {r["cpu_percent_one_core"]:.1f} | {max(x["rss_bytes"] for x in r["observations"])/1048576:.1f} | {r["person_count"]["mean"]:.2f} |')
    lines += ['', 'Full mean/median/P95/population-std/count and per-frame observations, detection',
              'and objectness distributions, input/model/source hashes are in each JSON.',
              'CPU percent uses process CPU time / wall time, one core = 100%; it can exceed',
              '100% and is not whole-machine utilization. CPU timing includes measured',
              'source opening whereas per-frame E2E excludes it. RSS samples are process',
              'memory, not continuous peaks or GPU memory. Conditions run sequentially in',
              'one process, so RSS can retain prior allocations; do not infer isolated',
              'backend memory efficiency or a memory leak from these differences.', '',
              '| Synthetic person boxes | Measured updates | Tracker mean / median / P95 / std ms |',
              '|---|---:|---|']
    for r in load('final-measurements/tracking-workload.json')['workloads']:
        m = r['tracking_ms']
        lines.append(f'| {r["synthetic_person_boxes"]} | {m["count"]} | {m["mean"]:.4f} / {m["median"]:.4f} / {m["p95"]:.4f} / {m["std"]:.4f} |')
    m = stability['metrics']
    lines += ['', 'These box-only workloads isolate tracker cost; they are not multi-person',
              'detector/camera throughput measurements.', '', '### Complete video stability run', '',
              f'- {run["frames"]} input frames processed, {stability["recording_decoded_frames"]} recorded AVI frames decoded; termination {run["termination"]}.',
              f'- Wall {run["wall_seconds"]:.2f} s; session throughput {stability["session_wall_fps"]:.2f} FPS including export/journal/opening.',
              f'- Frame processing mean/P95: {m["e2e_ms"]["mean"]:.2f}/{m["e2e_ms"]["p95"]:.2f} ms; loop incl. export mean/P95: {m["loop_ms"]["mean"]:.2f}/{m["loop_ms"]["p95"]:.2f} ms.',
              f'- Tracking mean/P95: {m["tracking_ms"]["mean"]:.4f}/{m["tracking_ms"]["p95"]:.4f} ms; CPU {run["cpu_percent_one_core"]:.1f}%.',
              f'- RSS sampled min/max: {stability["rss_min_max_bytes"][0]/1048576:.1f}/{stability["rss_min_max_bytes"][1]/1048576:.1f} MiB; first/last: {stability["rss_first_last_bytes"][0]/1048576:.1f}/{stability["rss_first_last_bytes"][1]/1048576:.1f} MiB.',
              f'- {stability["error_events"]} error events; cleanup errors: {run["cleanup_errors"]}; final simulated action STOP.',
              '- Video simulation deliberately remains IDLE without explicit selection; follow movement/loss/rearm are exercised in deterministic tests, not claimed from this road clip.',
              '- Application-skipped frames: 0 (no intentional skipping). Sensor/camera drops: N/A.',
              '- One roughly minute-long file run is not a multi-hour soak or live-camera stability test.', '',
              '## D. Acceptance status', '', '| Component | Status | Evidence | Scope / limitation |', '|---|---|---|---|']
    lines += [f'| {name} | **{status}** | {evidence} | {scope} |' for name,status,evidence,scope in matrix]
    lines += ['', 'PASS here applies only to its stated scope. The crossing FAIL describes the',
              'unchanged tracker, while the regression suite PASS means the test correctly',
              'detects that limitation. Physical C2C is deferred, not counted as a test skip.', '',
              '## Reproduction and evidence map', '',
              'See [README](../../README.md) for full commands/schema/keys and manual webcam',
              'acceptance. Commands from repository root:', '', '```sh',
              './projects/project3/verify.sh',
              "projects/project2/agent/.venv/bin/python -m unittest discover -s projects/project2/agent -p '*_tests.py' -v",
              './projects/project3/run.sh run artifacts/inputs/usa.hevc --track --simulate-follow --max-frames 2000 --output artifacts/my-stability-run',
              './projects/project3/run.sh run 0 --camera --display --track --simulate-follow --max-frames 300 --max-seconds 30 --output artifacts/webcam-manual-01',
              'cd projects/project3',
              '.venv/bin/python validate_vision.py --output evidence/my-new-measurements',
              '.venv/bin/python summarize.py', '```', '',
              'The webcam command is for user-run validation only; it was not executed in',
              'this phase. Output directories/files must be new; do not overwrite evidence.',
              'Raw media and verbose run/event records are local ignored artifacts under',
              '`artifacts/validation-20261016/`. Small summaries, hashes, timings and test logs',
              'are retained here. `final-measurements/` is authoritative; `measurements/` is',
              'the earlier pre-final-fix run and is retained for history. Neither downloads',
              'nor source opening are included in benchmark E2E. No Docker is needed with',
              'the existing local model/video. Initial dependency/source audits are in AUDIT.md.', '',
              '## Remaining work and presentation readiness', '',
              '- **Software implementation:** confirmed limitations remain motion/ReID tracking, a hard external watchdog for native hangs, and a version-matched real C2C adapter once firmware/API are known. Choose tracker changes after real evaluation; no replacement is claimed here.',
              '- **Software validation:** user-run camera permission/capture/disconnect/GUI-key checks; annotated real single/multiple-person/crossing/occlusion clips; real ID metrics and adverse-scene/multi-hour stability tests.',
              '- **Hardware integration:** actual C2C model/firmware, device bindings, Wi-Fi/SSH and UI acceptance remain deferred; no physical following verification.',
              '- **Presentation:** ready to present the measured **software stage and its limits**. Not ready to claim full Run2 completion or real tracking accuracy. No PPTX generated this phase.', '',
              'Suggested 14-slide structure: (1) course scope, (2) audited starting point,',
              '(3) shared pipeline architecture, (4) original model conventions, (5) image/',
              'video evidence, (6) explicit target state machine, (7) failure/STOP behavior,',
              '(8) tracking data and metric definitions, (9) synthetic results, (10) crossing/',
              'occlusion failures, (11) CPU/CoreML timing scopes and comparison, (12) full',
              'video stability and regression, (13) scoped acceptance including camera/C2C,',
              '(14) annotated live validation and next steps.', '']
    (EVIDENCE/'REPORT.md').write_text('\n'.join(lines))
    status = ['# Project 3 verification status — 2026-10-16', '',
              '[Complete implementation/tracking/performance report](validation-20261016/REPORT.md).',
              '[Pre-update 2026-10-14 status](validation-20261016/status-before.md).', '',
              f'Project 3: **{total} PASS / 0 FAIL / 0 SKIP**, including all {original} original tests unchanged.',
              f'Project 2 offline: **{p2} PASS**. Protected files: **{preservation["protected_files"]} unchanged**.',
              'No commit/push, professor source changes, device control, SSH, network changes or model retraining.', '',
              '| Component | Status | Evidence / limitation |', '|---|---|---|']
    status += [f'| {name} | **{state}** | {evidence}; {scope} |' for name,state,evidence,scope in matrix]
    status += ['', 'Evidence references in the table are relative to `validation-20261016/` unless stated.',
               'PASS is limited to executed software scope. Synthetic ID scores do not measure',
               'real tracking accuracy; ID switches/IDF1 on unannotated video are N/A.',
               'Camera authorization is notDetermined (read-only query); Webcam Live BLOCKED.',
               'Real C2C is NOT TESTED / deferred. Native GUI keyboard interaction NOT TESTED.',
               'Run2 injected lifecycle/message tests continue to pass, but cannot establish',
               'real cereal serialization, network communication or device UI integration.', '',
               f'Full video: {run["frames"]} frames, {run["wall_seconds"]:.2f}s, EOF, recorded AVI checked, final simulation STOP.',
               'Suitable for a software-stage final presentation with explicit pending items;',
               'not a claim that all course hardware requirements are complete.', '']
    (BASE/'evidence/STATUS.md').write_text('\n'.join(status))
    print(f'Current report rebuilt: {total} P3 tests, {p2} P2 tests; saved measurements only.')


if __name__ == '__main__':
    build()
