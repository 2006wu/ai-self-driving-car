# Human work and exact existing-tool workflow

**Needed from the user:** three suitable original local clips (crossing, short occlusion, long occlusion), at least 100 consecutive labeled frames each, and an annotator plus a different human reviewer. No suitable accepted multi-person clip or reviewed annotation is currently available. Existing tools are sufficient; follow INPUT_CONTRACT.md before running the benchmark.

## 1. Supply and inspect the real inputs

Save genuine existing media at new repository-local paths such as `projects/project3/artifacts/benchmark-inputs/crossing.mp4`, `short-occlusion.mp4`, and `long-occlusion.mp4`. These are proposed paths; no such videos are created here. Verify visually that the first N decoded frames contain the required event, two people and before/after context. Record source provenance and any parent/excerpt mapping in a separately saved copy of benchmark-input.template.json. Do not substitute a still image, an overlay video or a copied scenario.

The workflow below shows crossing with N=100. Use the actual N≥100 needed to include the event and context, and repeat for the two other real scenarios. Do not mark unprovided inputs ready. All outputs must be new; existing tools refuse overwrites.

```sh
# Repository root, existing P3 environment. Run only after real source exists.
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline record projects/project3/artifacts/benchmark-inputs/crossing.mp4 --max-frames 100 --output reports/benchmark-crossing-dataset
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline validate reports/benchmark-crossing-dataset --verify-pixels --output reports/benchmark-crossing-quality.json
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline template reports/benchmark-crossing-dataset --output reports/benchmark-crossing-blank.json
```

Greedy remains the default for recording. Both trackers are later replayed from this **one bundle's** saved detections. A second Hungarian recording is unnecessary and could introduce different timings/source inference. No model training or robot interface is used.

## 2. Extract every original frame

The existing `extract` command accepts a comma-separated index list. Obtain the full list from the bundle, without modifying the bundle or any schema:

```sh
BENCHMARK_FRAMES=$(python3 - <<'PY'
import json
from pathlib import Path
m=json.loads(Path('reports/benchmark-crossing-dataset/manifest.json').read_text())
print(','.join(map(str,range(m['records']['count']))))
PY
)
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline extract reports/benchmark-crossing-dataset --frames "$BENCHMARK_FRAMES" --output reports/benchmark-crossing-original-frames
```

Extracted PNGs are unannotated original decoded pixels, with an index and blank template. They are not rendered overlays and are not human ground truth until labeled/reviewed. Retain all source/hash/frame references. Do not annotate a contact sheet or a detector overlay in place of these full-resolution original frames.

## 3. Annotate, then independently review

Save a new working annotation file. For every original frame:

- Assign persistent human person IDs unrelated to tracker IDs. Keep each person's identity across crossing and return; document uncertainty rather than guessing or copying a predicted ID.
- Enter continuous original-pixel `[x1,y1,x2,y2]` boxes for visible/partial people; use occlusion none/partial/full. A fully hidden person may retain its human ID with box=null. Do not invent a hidden box.
- Use the same target_person_id through the event; this is a human identity, independent of controller/selected track IDs. Annotate other people too, not just the target.
- An empty persons list only becomes an absence annotation after a human inspects the frame. The blank template's empty list is not a label.

A different human reviewer must inspect **every** frame, check identity consistency and event intervals against original video, and record disagreements/resolutions in the referenced review log. Only after actual annotation/review set per-frame reviewed=true, document status=reviewed, provenance.kind=human_annotation, actual annotator/reviewer and reference. Never use a model or Codex as the independent human reviewer. Tools validate the declaration; they cannot certify it happened.

No human identities, review timestamps, boxes or labels are filled by this task. The existing Milestone 2 empty templates remain draft. Existing synthetic example/test annotations remain synthetic/test-only and cannot be promoted.

## 4. Check coverage and acceptance before evaluation

Run the existing validator with the real reviewed file:

```sh
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline validate-annotations reports/benchmark-crossing-dataset reports/benchmark-crossing-reviewed.json
```

For each scenario, independently confirm that reviewed frame IDs are exactly `0..N-1`, all are reviewed, and N≥100. Count ≥300 unique frames across three scenarios using parent-source mappings; the same frame in several files counts once. Confirm actual distinct review identities and event evidence. Fill a new copy of the acceptance checklist from real evidence. The validator allows sparse labels and equal annotator/reviewer names, so its PASS alone is insufficient for this milestone.

Record coverage fields per scenario: recorded count, annotated count, reviewed count, missing/duplicate/out-of-order IDs, dense coverage fraction, frames with ≥2 human IDs with boxes, fully occluded rows without boxes, target ID, event intervals and human review provenance. Do not count draft frames as reviewed, or add the five-frame Milestone 2 subset to its overlapping 120-frame template.

## 5. Evaluate both trackers and reproduce

Only after the media, density and actual-review gates pass:

```sh
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline evaluate reports/benchmark-crossing-dataset --annotations reports/benchmark-crossing-reviewed.json --output reports/benchmark-crossing-comparison.json
# Same inputs, second new output: compare predictions/identity metrics, not measured latency bytes.
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline evaluate reports/benchmark-crossing-dataset --annotations reports/benchmark-crossing-reviewed.json --output reports/benchmark-crossing-comparison-repeat.json
```

Repeat for the short/long occlusion scenarios. Existing output contains a shared detector_input_sha256, per-method input hashes, predictions, IDF1, ID switches, track_fragmentations, target_recovery counts/rate, latency statistics and annotation_coverage. Trackers always process the complete recorded sequence. Report per-scenario metrics; do not naïvely average IDF1 as an aggregate score. If a pooled score is needed later, define a separate identity namespace per scenario and the pooling formula first; no suite aggregator is introduced here.

The evaluator excludes full-occlusion null boxes from GT box matching but does not infer ignore regions; unmatched predictions may still count. Fragmentation is matched→unmatched while GT present→matched, while recovery can include an absent target returning. Thus human occlusion labels do not automatically imply an evaluator recovery/fragmentation event. Report zero/undefined only as actually calculated, with denominators and this policy. Predictions or detection coverage never become human truth.

The evaluate CLI can exit successfully after writing a BLOCKED report when labels are invalid/missing; inspect real_accuracy_status and metrics rather than treating exit zero as benchmark acceptance. Sparse annotation coverage would produce sampled metrics, which fail this milestone's dense coverage criterion.

## 6. Completion decision

Until all three genuine scenarios and ≥300 independently reviewed dense frames are provided, state **PREPARED/BLOCKED** with real identity metrics N/A. Existing synthetic tracking regressions may verify software separately, but cannot satisfy the real benchmark. The next action is input acquisition and actual human annotation/review; additional models, Kalman/Re-ID or hardware work are outside this task.
