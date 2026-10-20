# Milestone 3 — Human-Verified Tracking Benchmark

2026-10-20 (Asia/Taipei). Branch **develop**. HEAD **9a864c546f5121748079ad58df2879faf8ffb46c**.

**Overall: PREPARED / BLOCKED. The real human-verified benchmark is not complete.** Existing tools are sufficient, but no suitable accepted multi-person scenario suite or genuine reviewed identity annotations are available. No real IDF1, switches, fragmentation, recovery or benchmark latency result is reported. No source/runtime/default/interface was modified.

## Existing tools reviewed and reused

Read both required reports: `reports/ai-control-readiness-20261020/REPORT.md` and `reports/ai-control-milestone2-20261020/REPORT.md`. Reviewed current source rather than assuming report claims apply automatically.

| Existing source | Reused implementation | Boundary / acceptance implication |
|---|---|---|
| `projects/project3/p3/research/annotations.py` | annotation_template, extract_annotation_frames, validate_annotations | Blank original-source-bound labels; persistent person IDs, boxes, occlusion and target ID supported. Reviewed provenance must be nonempty, but distinct annotator/reviewer and actual human work are not proven by the validator. |
| `projects/project3/p3/research/dataset_v2.py` | load_bundle(..., verify_pixels=True), hash/record/order/source validation | Successfully revalidated preserved final M2 video/image bundles against original source bytes and decoded pixels. PASS is integrity, not true identities. |
| `projects/project3/p3/research/recorder.py` | Local-file recorder and processing-clock provenance | Suitable for future accepted source clips; decodes a prefix from index 0. No new recording needed for currently unsuitable media. Exposure time remains unknown. |
| `projects/project3/p3/research/evaluate_dataset.py` | compare_dataset; same stored detector inputs, Greedy/Hungarian, reviewed-label gate and coverage | Already supplies required metrics and latency. Allows sparse annotations, so this milestone additionally requires dense complete coverage and a suite-level human acceptance checklist. |
| `projects/project3/p3/research/offline.py` | record, validate, template, extract, validate-annotations, evaluate | Existing opt-in CLI is sufficient. No duplicated annotation tool/evaluator/recorder/framework or new CLI default added. |
| `projects/project3/p3/tracking_eval.py` | Existing identity/fragmentation/recovery definitions | Retained; no new metric formula or algorithm. Full-occlusion null GT boxes are excluded, not automatic ignore regions. Unmatched predictions may still count. |

The general-purpose annotation contract supports the needed small benchmark, but structural validation does not certify human truth, independence, event presence or a 300-frame/three-scenario quota. These are made explicit in [INPUT_CONTRACT.md](INPUT_CONTRACT.md), [HUMAN_WORKFLOW.md](HUMAN_WORKFLOW.md) and acceptance.json. No modification to Milestone 1/2 is necessary to prepare this blocked stage.

## Media inventory and inspection

Repository-local video discovery excluded dependency environments and .git. See [audit/media-inventory.json](audit/media-inventory.json) for exact paths, byte counts and SHA256 values. No external service, network search/download, Docker volume, camera or other hardware was accessed.

| Available source | Inspection | Benchmark disposition |
|---|---|---|
| `projects/project3/artifacts/inputs/usa.hevc` | Original local input, 37,534,986 bytes; completely re-decoded: 1,200 frames, decoder-reported FPS 25.0. Historical full log hash matches original source. | No accepted multi-person crossing/occlusion evidence. Excluded from the proposed real benchmark. |
| Six `artifacts/**/overlay.avi` files | Previously rendered output AVIs, listed with hashes. | Excluded as original footage; duplicates/overlays do not create new scenarios. |
| `projects/project3/artifacts/bus.jpg` | Real static image; historical YOLO output has four person detections. | Cannot measure trajectories, crossing or occlusion recovery; no video frames manufactured from it. |
| Other suitable original local videos | None found in the inspected repository-local video inventory. | BLOCKED; no invented substitute/download. |

Original USA SHA256: `98b2420f89426db2eaefd3b2fdbabcf4d2398d272b0874a973887d657875de3c`.

The full historical `stability-video-final/run.json` contains person detections at decoded indices **199, 459, 464, 471, 472, 479, 480, 481, 710, 893**, with at most one detected person per frame and **no multi-person detection frames**. This refines M2's first-120-frame result (zero person detections); it does not prove people are absent elsewhere or that these ten detections are correct.

An **AI visual survey, not human annotation**, inspected an original-frame contact sheet covering every 100th frame, every one of those ten historically detected frames, and the last frame: 23 sampled original frames total. These show highway roadway scenes; no suitable multi-person crossing/occlusion event was established in the survey. A sparse survey is not exhaustive human review of all pixels or proof that no small person exists. Suitability is **not established**, so the source is not admitted as a benchmark. Detector flags are explicitly observations, not GT or evidence of true people/occlusion.

[audit/audit-contact-sheet.jpg](audit/audit-contact-sheet.jpg) is a resized, captioned evidence visualization only. It is **not original benchmark media or an annotation artifact**. [audit/audit-frame-index.json](audit/audit-frame-index.json) maps every tile back to original decoded indices/dimensions. No rendered overlay was used as an original source.

## Annotation readiness and human work

[annotation-readiness.json](annotation-readiness.json) is the current coverage report:

| Item | Available | Accepted human-verified benchmark coverage |
|---|---:|---:|
| Accepted real scenarios | 0 | 0 / 3 required |
| M2 full USA blank template | 120 draft frames, 0 person labels, 0 reviewed frames | 0 |
| M2 extracted subset blank template | 5 draft frames overlapping those 120, 0 reviewed frames | 0 additional |
| Existing `annotation-example.json` | 2 explicitly synthetic example frames | 0 real frames |
| Actual reviewed human identity labels | None found in the inspected candidate artifacts | 0 / ≥300 required |

The M2 draft passed structural draft validation and was correctly **rejected** by the existing reviewed-human validation gate: “human annotations are not reviewed”. Both the 120-frame USA bundle and 1-frame image bundle passed strict original-pixel verification again. See [audit/existing-tool-validation.json](audit/existing-tool-validation.json). This tests readiness and refusal behavior, not a real benchmark.

Required human work:

1. Supply three genuine local video scenarios: crossing, short occlusion and long occlusion, with at least 100 consecutive annotatable frames each, meaningful before/after context and multiple people. The current road/image/overlay assets do not satisfy this contract.
2. Use the existing recorder/extractor to retain original frame references; label all unique ≥300 frames with persistent human identities, image-space boxes, occlusion, target identity and source provenance. Do not copy tracker IDs or treat empty draft lists as reviewed absence.
3. A **different human** independently inspects all frames and resolves identity/occlusion disagreements. Preserve actual annotator/reviewer IDs and review notes; do not insert fictional names/timestamps or merely toggle reviewed flags.
4. Confirm dense coverage, source/label integrity, independently reviewed event intervals and unique parent-source frame counts; only then execute the already-existing identical-input evaluation and reproduction commands.

The existing user-facing commands and exact steps are in [HUMAN_WORKFLOW.md](HUMAN_WORKFLOW.md). No annotation framework is needed. The new benchmark-input.template.json is deliberately incomplete suite/checklist metadata, not fake labels or an input accepted by the existing CLI. Every actual source, label, event and reviewer field remains null. Requested scenario names describe targets, not observed events.

## Acceptance criteria and current decision

[INPUT_CONTRACT.md](INPUT_CONTRACT.md) preregisters concrete requirements:

- ≥3 real multi-person video scenarios, each with ≥100 consecutive densely annotated frames and ≥300 **unique** frames overall. Nonoverlapping excerpts from one real parent can qualify with exact mapping; copies and overlapping/re-encoded duplicates do not count twice.
- At least one verified crossing, one short occlusion (1–5 consecutive decoded frames) and one long occlusion (≥6), with visible before/after context and resolvable persistent target identity. These are frame-count research definitions around max_missed=5, not physical durations or exposure timing.
- Valid human annotation provenance and actual distinct independent reviewer; 100% reviewed recorded-frame coverage. Existing validators intentionally do not enforce the entire suite contract; human acceptance checks remain required.
- Original media and all recorded pixels verify; annotations bind to exact session/media/journal hashes.
- Greedy IoU and Hungarian receive identical recorded detections, threshold=.3, max_missed=5, evaluator IoU=.5. No per-method YOLO rerun/tuning is introduced.
- Report IDF1, switches, fragmentation, recovery with eligible-gap counts, and tracker latency statistics. Undefined recovery remains N/A; do not substitute zero or manufacture a recovery gap. At least one actually eligible occlusion recovery gap is needed to assess that behavior.
- Repeating evaluation on identical bundles/labels must reproduce predictions and identity metrics. Runtime timings are remeasured and need not match bit-for-bit.

No score threshold or required Hungarian improvement is invented. An honestly measured tracker failure is a valid benchmark result. At present the required media, human review and density gates are **BLOCKED**, and real comparison/reproduction gates are **NOT TESTED**. Software regression PASS does not close those gates.

## Benchmark results

**No valid real human-verified benchmark was executed.** [acceptance.json](acceptance.json) records benchmark_complete=false and null fields below, rather than zero-valued or borrowed results.

| Method | IDF1 | ID switches | Fragmentation | Recovery | Benchmark runtime latency |
|---|---|---|---|---|---|
| Greedy IoU | N/A | N/A | N/A | N/A | N/A |
| Hungarian | N/A | N/A | N/A | N/A | N/A |

No new real-data metric or latency comparison was run for an unsuitable road clip. M2's no-person/static-image software timings remain in its historical report and are not represented as benchmark results. Existing synthetic fixture results likewise remain in M1/M2 under synthetic_ground_truth. P3 regressions execute synthetic fixtures as software tests, but they cannot satisfy any real scenario/annotation requirement. No Kalman, Re-ID, AI-Control training or physical-interface work was added.

## Test results and preservation

| Executed check | Result | Evidence |
|---|---|---|
| All Project 3 original/M1/M2 regressions | **156 PASS / 0 FAIL / 0 SKIP** | p3-tests.txt |
| Relevant Project 2 offline regression | **96 PASS / 0 FAIL** | p2-tests.txt |
| Existing M2 bundles, original/pixel integrity | **PASS**, 120-frame USA and 1-frame image | audit/existing-tool-validation.json |
| Existing draft rejected as reviewed human GT | **PASS** refusal test; actual human labels BLOCKED | Same validation file |
| Full source media decode | **1,200 frames**, historical/source hashes consistent | audit/media-inventory.json |
| Existing content preservation | Initial **499 files** checked; changed/missing list empty | preservation-after.json |
| Branch/HEAD/defaults/original CLI | Unchanged | checks.json and preservation manifests |

No new runtime code was necessary, so no new runtime tests or duplicated functionality were added. The evidence-only local-audit.py was executed on actual local assets; it reuses existing APIs and never assigns GT or computes benchmark metrics. Existing unit tests contain test-only authored labels; none are promoted to human evidence.

Snapshot scope includes current tracked/untracked M1/M2 work, reports/evidence, professor/course assets and existing Project 3 media, excluding generated bytecode. No Docker volume inspection/preservation claim is made. Project 2 regression scope is the relevant offline agent suite, not training or live API acceptance.

No hardware/camera operation, motor/API/SSH call, network change/download, model training, professor-source change, commit, push or branch merge was performed. Temporary regression fixtures are generated and cleaned up by existing tests; historical artifacts remain untouched.

## Files created and modified

Existing files modified: **NONE**. All additions are under `reports/ai-control-milestone3-20261020/`:

- PLAN.md, REPORT.md, INPUT_CONTRACT.md, HUMAN_WORKFLOW.md.
- benchmark-input.template.json, acceptance.json, annotation-readiness.json.
- local-audit.py and audit/{media-inventory.json,audit-contact-sheet.jpg,audit-frame-index.json,existing-tool-validation.json}.
- p3-tests.txt, p2-tests.txt, preservation-before.json, preservation-after.json, checks.json.

No file in `projects/project3/p3/`, tests, original CLI, professor assets or previous reports was changed. An ignored Python cache may be generated by regression imports.

## Reproduction

From repository root, with existing P3/P2 environments. Use a new audit directory; existing destinations are refused.

```sh
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python reports/ai-control-milestone3-20261020/local-audit.py --output reports/my-new-local-media-audit
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m unittest discover -s projects/project3/tests -v
projects/project2/agent/.venv/bin/python -m unittest discover -s projects/project2/agent -p '*_tests.py' -v
```

Benchmark recording/annotation/evaluation commands are **prepared**, not represented as executed with hypothetical input files. They are listed in HUMAN_WORKFLOW.md and reuse the existing offline CLI. Evaluate may exit zero while writing a BLOCKED report; check its real_accuracy_status and metrics as well as the suite acceptance requirements.

## Status boundaries and next milestone

- **IMPLEMENTED:** Existing M1/M2 tooling retained; evidence-only local audit script, explicit input contract, acceptance/coverage records and user instructions added.
- **TESTED:** Existing software regressions, source decode/hashes, M2 pixel integrity and refusal of draft labels.
- **PREPARED:** Three-scenario dense annotation/review protocol, input checklist and reproducible existing-tool commands.
- **BLOCKED:** Suitable accepted real clips and ≥300 genuinely human-labeled, independently reviewed frames. These are the next required inputs.
- **NOT TESTED:** Real human-verified benchmark accuracy, actual human identity consistency/reviewer agreement, real occlusion recovery and benchmark runtime. Physical control and model training remain outside scope.

Recommended next milestone is to **finish Milestone 3's human-data gate**, then run/report the frozen Greedy/Hungarian benchmark. After actual results exist, consider a separate evidence-led tracking improvement milestone; use observed failure cases to justify any motion model. Do not skip the human evidence requirement by starting AI training, inventing labels or adding hardware work.
