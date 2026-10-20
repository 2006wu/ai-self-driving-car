# Human annotation workflow

Status: **IMPLEMENTED / TESTED workflow; real annotated tracking evaluation BLOCKED.**

No reviewed human person-identity annotations were found for the available original Project 3 local media. The recorded USA road sample contains no YOLO person detections; a different genuine multi-person clip will be needed for a useful person-tracking study. The bus sample has people but is a single static image and cannot measure temporal identity stability.

The supplied `annotation-template.json` references all 120 recorded USA frames and contains **no labels**. `annotation-frames/` contains five lossless original-decoded PNGs (frames 0,30,60,90,119), an index with original frame references and a separate five-frame blank template. These frames have no boxes/overlays added. An empty draft is not a reviewed claim that a frame has no people. No detector or tracker output is copied into annotations.

## Procedure

1. Use a new recorder destination for the original clip. Preserve the original media, dataset manifest and journal. Validate with `--verify-pixels` before annotation.
2. Create a blank template, optionally selecting a small strictly increasing set of frame indices. Extract the corresponding original PNGs. For dense temporal metrics, annotate every frame of a short clip. A sparse subset is permitted but metrics/recovery/fragmentation apply only to that sampled sequence.
3. A human assigns positive integer `person_id` values consistently across frames. These are human persistent identities, never automatically borrowed from tracker IDs. Do not reuse one ID for different people within a clip. Record image-space continuous `[x1,y1,x2,y2]` boxes inside original dimensions.
4. For each person, provide exactly `person_id`, `box`, and `occlusion`: `none`, `partial`, or `full`. A fully occluded person may have `box: null` when no trustworthy box exists. That preserves identity annotation without inventing a box. An absent/out-of-frame person may be omitted; add it again with the same ID upon genuine return. Visible/partial people require a box. A trusted human box for a fully occluded person is accepted but should not be guessed.
5. Set `target_person_id` to the human target identity for recovery metrics, or null when no target is defined. It is independent of the recorder's selected track/controller target. Complete every requested frame; `persons: []` with `reviewed: true` is an explicit human-reviewed absence annotation.
6. Record an actual annotator, reviewer and evidence/review reference in provenance; change its kind from `pending_human_annotation` to `human_annotation` only after actual annotation. Set each completed frame's `reviewed` to true and document status to `reviewed` after review. Keep identity decisions and difficult occlusion cases in the referenced review notes.
7. Save to a **new file**, preserving the supplied blank template. Run validate-annotations, then evaluate both trackers against that file. The validator checks structure and supplied provenance; human review is still needed to establish label truth and correct identities. Merely setting flags cannot establish trustworthy ground truth.

## Annotation contract

Version `comma_body_annotations/1.0` contains exact dataset session ID, journal SHA256 and media SHA256; status; provenance kind/annotator/reviewer/reference; nullable target_person_id; and strictly increasing unique frame records. Each frame contains frame_id, original frame reference, original dimensions, reviewed boolean and persons list. Each person contains identity, box and occlusion label. The validator rejects wrong source/run, dimensions, bounds, degenerate/NaN boxes, invalid/duplicate identities, unsupported occlusion, missing provenance, unreviewed frames and unknown target identity. Drafts can be inspected with Python `validate_annotations(..., require_reviewed=False)` but cannot produce real accuracy metrics.

## Commands

From repository root, with existing P3 environment; use new destinations:

```sh
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline template reports/ai-control-milestone2-20261020/usa-verified --frames 0,30,60,90,119 --output reports/my-blank-annotations.json
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline extract reports/ai-control-milestone2-20261020/usa-verified --frames 0,30,60,90,119 --output reports/my-annotation-images
# After actual human annotation/review, using a separately saved completed file:
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline validate-annotations reports/ai-control-milestone2-20261020/usa-verified reports/my-reviewed-annotations.json
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python -m p3.research.offline evaluate reports/ai-control-milestone2-20261020/usa-verified --annotations reports/my-reviewed-annotations.json --output reports/my-reviewed-tracking-results.json
```

## Evaluation boundaries

Both methods replay the exact same stored detector outputs through **all** recorded frames. Evaluation then selects the reviewed annotation frames without inventing intervening labels. Metrics use the existing evaluator with IoU threshold .5 and explicit human_ground_truth provenance. Full occlusion with null box is excluded from GT box matching; predictions still count as unmatched predictions when applicable. No ignore-region, visibility weighting or amodal-box inference is invented. A reviewed occlusion box is included normally. Coverage and excluded occlusion count are reported. This is not full MOTChallenge preprocessing.

Without valid reviewed annotations, IDF1, switches, fragmentation and recovery are all unavailable (`metrics: null`); only predictions/latency and BLOCKED status are reported. Synthetic regression fixtures keep synthetic_ground_truth status and remain separate from this real-data workflow. The authored values in automated tests are explicitly test-only contract fixtures and are never delivered as human annotations of real media.
