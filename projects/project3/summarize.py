"""Build report-ready tables from measured evidence, without rerunning inference."""
import json
from pathlib import Path

base=Path(__file__).resolve().parent
E=base/'evidence'
if (E/'validation-20261016/final-measurements/tracking-workload.json').exists():
    from report_validation import build
    build()
    raise SystemExit(0)
scenarios=[('CPU image','final-image.json'),('CPU video short','final-video-short.json'),
           ('CPU video long','final-video-long.json'),('CPU source 640×480','final-image-small.json'),
           ('CPU source 1920×1080','final-image-large.json'),('CPU confidence .5','final-image-conf50.json'),
           ('CoreML+CPU image','final-coreml.json')]
lines=['# Project 3 verification status — 2026-10-14','',
'Branch `develop`; HEAD `0098f886e078cacbe08eb2d1282922cd78b5b1dc`. No commit or push.',
'P3.0 audit complete; independent file-input implementation and evaluation verified.',
'Webcam and actual C2C remain pending. User confirmed no available/confirmed C2C for this phase; continue software work only.',
'', '## Final acceptance matrix','',
'| Category | Item | Classification | Status | Evidence | Limitation |',
'|---|---|---|---|---|---|',
'| Run1 | Adapted image YOLO + boxes/class/objectness | Required baseline / source-defined image mode | PASS | tests-final.txt; artifacts/final-preview | Original preview.png absent; unchanged professor GUI not run |',
'| Run1 | Real USA video + EOF | Source option / Engineering verification | PASS | full-video-summary.json; artifacts/full-video | 1200 decoded frames, cap 2000; no driving accuracy claim |',
'| Run1 | Camera open/close | Source option / Engineering verification | NOT RUN | camera-capability.txt | AVFoundation authorization notDetermined; capture pending OS permission |',
'| Run1 | Model IO / baseline parity / coordinates / single session | Engineering | PASS | 7 model + 12 geometry tests | BGR/objectness/class-agnostic NMS preserved |',
'| Run1 | Benchmark | Engineering / Extension | PASS | final-*.json; supplemental.json | File pipeline, no camera/accuracy metrics |',
'| Run2 | Requirement + source / Level A | Required preparation | PASS | source-audit.json; docs/PROJECT3.md | Actual device schema/version unknown |',
'| Run2 | Process/message API test double / partial Level B | Engineering | PASS within API scope | 8 Run2 + 1 invalid-UI cleanup test; run2-mock.json | No real cereal serialization, msgq, SSH or Wi-Fi |',
'| Run2 | Wi-Fi/SSH communication setup | Required | BLOCKED | HARDWARE.md | User deferred hardware; no available/confirmed device |',
'| Run2 | Device UI / Level C physical C2C | Required | BLOCKED | HARDWARE.md | No real device integration performed |',
'| Do New | Person tracking + persistent IDs / target selection | Extension | PARTIALLY VERIFIED | 10 tracker tests; full-video-summary.json; artifacts/final-preview | Synthetic box association + real detector execution; no annotated MOT accuracy |',
'| Do New | OpenCV overlay dashboard | Extension | PARTIALLY VERIFIED | PNG visual inspection; GUI cleanup test; native-gui.txt | Visual OS interaction observation unavailable; no live network status |',
'| Do New | Robustness probes | Extension | PARTIALLY VERIFIED | supplemental.json; tests-final.txt | Synthetic darkness/blur/occlusion and 1000 tracker updates; real adverse scene trials pending |',
'| Regression | P2 Agent offline | Engineering | PASS | p2-regression.txt | 44/44 offline; no provider/API calls |',
'| Regression | Existing P1/P2 + professor source preservation | Engineering | PASS | preservation.json | 261 pre-task files compared; only intended docs changed |',
'| Regression | P1 compose configuration | Engineering | PASS | docker compose config --quiet exit 0 | Services absent before work; replay/UI runtime NOT TESTED |',
'', '## Actual tests','',
'Final Project 3 suite: **50 executed, 50 PASS, 0 FAIL, 0 SKIP**.',
'Geometry 12; inputs/EOF/errors/stats 9; real-model integration 7; Run2 API 8;',
'benchmark integration 2; dashboard/API-invalid-data cleanup 2; tracking 10.',
'Camera failures and GUI keys in unit tests are injected doubles, not real hardware passes.',
'Project 2 regression: **44/44 PASS**. P1 runtime and TF training were not rerun.',
'', '## Measured performance','',
'Each scenario has five excluded warm-up forwards. CPU intra-op threads=1.',
'FPS = 1000 / mean latency; model input remains 640×416. Source size is varied separately.',
'CoreML has CPU fallback partitions (230/237 nodes supported, 4 CoreML partitions).',
'These numbers characterize this machine/run; no GPU-only or universal acceleration claim.',
'', '| Scenario | n | Inference mean / median / P95 / std ms | Inference FPS | File E2E mean / P95 ms | File FPS | RSS sampled max MiB |',
'|---|---:|---|---:|---|---:|---:|']
for label,file in scenarios:
 r=json.loads((E/file).read_text());m=r['metrics'];i=m['inference_ms'];e=m['e2e_ms']
 peak=max(x['rss_bytes'] for x in r['observations'])/1048576
 lines.append(f"| {label} | {i['count']} | {i['mean']:.2f} / {i['median']:.2f} / {i['p95']:.2f} / {i['std']:.2f} | {r['inference_fps']:.2f} | {e['mean']:.2f} / {e['p95']:.2f} | {r['file_pipeline_fps']:.2f} | {peak:.1f} |")
lines+=['', 'Full pre/inference/post/render/acquisition stage mean/median/P95/std/count,',
'RSS, detection counts, objectness distribution and observations are in each JSON.',
'Image scope: resident frame + preprocessing + inference + postprocessing + overlay.',
'Video adds frame decode. Optional source resize is timed. Source opening, exports,',
'GUI display, tracking and camera capture are excluded; not camera end-to-end latency.',
'RSS is sampled process memory, not continuous peak or GPU memory.',
'', '## Model construction and provider output differences','']
s=json.loads((E/'supplemental.json').read_text())
for provider,m in s['model_load_ms'].items():
 lines.append(f"- {provider}: n={m['count']}, mean {m['mean']:.2f}, median {m['median']:.2f}, P95 {m['p95']:.2f}, std {m['std']:.2f} ms.")
comp=s['provider_comparison']
lines+=['', 'Construction includes ONNX read/check, class metadata and session creation;',
'five repeated constructions use warm OS caches and exclude interpreter startup.',
f"Provider raw output mean/max absolute difference: {comp['raw_mean_abs']:.6f} / {comp['raw_max_abs']:.6f}.",
'On this single image both emit five detections with the same class/rank sequence;',
'max corresponding box-coordinate difference is about 0.69 source pixels and max',
'objectness difference about 0.0047. Not bitwise/numerically equivalent and not an',
'accuracy validation. CPU remains the professor-parity baseline.',
'', '## Robustness / qualitative limitations','',
'| Deterministic image probe | Detections | Person predictions |',
'|---|---:|---:|']
for label,r in s['variants'].items():
 lines.append(f"| {label} | {r['detections']} | {r['persons']} |")
lines+=['','These counts are outputs, not true/false-positive or recall measurements.',
'Visual inspection of the baseline sample shows the bus box labeled airplane;',
'this is a qualitative model error worth investigating separately. Class indexing',
'and objectness presentation follow the original program. No labeled precision,',
'recall, mAP or real-person identity/physical-following claim is made.',
'Road-video full run had 10 frames with person predictions and 8 predicted track IDs;',
'neither count establishes that real people were correctly tracked.',
'', '## Remaining work in priority order','',
'1. Supply actual C2C model/firmware/network information, then implement version-matched',
'   bindings and verify real cereal/UI/Wi-Fi/SSH with rollback and hardware evidence.',
'2. Grant native camera permission and run bounded acquisition/open/close/disconnect tests;',
'   validate actual GUI target cycling/quit through visual interaction.',
'3. Collect annotated multi-person motion/occlusion/crossing clips; measure ID switches',
'   before choosing a more capable tracking algorithm.',
'4. Investigate baseline color/class/confidence conventions in a separate controlled',
'   experiment; retain current reference-parity baseline.',
'5. Add real adverse-scene/extended duration trials; prepare final report after hardware',
'   status and results are known.',
'', '## Verification summary','',
'**VERIFIED:** source audit, native environment, model/image/video file inference,',
'geometry/EOF/error handling, stage benchmarks, API-double lifecycle, P2 offline regression.',
'**PARTIALLY VERIFIED:** tracking, dashboard and robustness (limited sources/test doubles).',
'**BLOCKED:** actual Run2 hardware integration pending actual device information.',
'**NOT TESTED:** camera capture, real C2C transport/UI, P1 replay runtime this session,',
'annotated detection/tracking accuracy, physical human following.',
'No commit/push, professor source edits, P1/P2 dependency changes or volume deletion.']
(E/'STATUS.md').write_text('\n'.join(lines)+'\n')
print('Status tables generated from measured results.')
