# Required benchmark inputs and acceptance contract

State: **PREPARED; inputs and real benchmark BLOCKED**. This is a research input specification, not evidence that any scenario has been supplied or reviewed. No runtime/schema changes are required.

## Required media

Supply three genuine, unrendered local video clips, with at least 100 consecutive annotated decoded frames per scenario and at least 300 **unique** densely annotated frames total. Each clip must contain at least two real people visible together before/after its event, with enough pixels for humans to assign identity and boxes. Do not use road video with no verified multi-person event, still-image repetition, synthetic footage, rendered overlays or detector boxes as original footage.

The initial three slots are:

| Requested scenario | Required human-verified event | Minimum context |
|---|---|---|
| crossing | At least two people's image trajectories cross or overlap, with persistent identities resolved before and after | At least 5 densely annotated frames before and after the event |
| short_occlusion | A target person is hidden by another person/object for 1–5 consecutive decoded frames, then returns with the same human identity | Before/after visibility and a documented frame interval |
| long_occlusion | A target person is hidden for at least 6 consecutive decoded frames, then returns with the same human identity | Before/after visibility and a documented frame interval |

Short/long thresholds are preregistered **frame-count research definitions**, chosen around max_missed=5; they are not elapsed-time/physical safety thresholds. Human occlusion is not the same as a detector miss. Record actual FPS only as decoder metadata; do not derive camera exposure timestamps. Optional measured exposure timestamps, if any, require a separate supported contract; none are invented here.

Use existing original clips whose first N≥100 decoded frames contain the event and context. The existing recorder processes a prefix starting at decoded index 0 and does not implement arbitrary start/end seeking. If only longer source footage exists, identify suitable real excerpts beforehand, retain the parent original/hash and mapping to parent decoded indices, and preserve the parent unchanged. No excerpt is created by this milestone. Clip frame ranges must not overlap in parent-source coordinates; duplicate/transcoded/re-encoded copies do not count as new unique footage. Three scenarios may come from one parent recording if distinct nonoverlapping spans genuinely meet the three event requirements.

Accepted local suffixes are those already supported by Frames: mp4/mov/avi/mkv/hevc/m4v/webm. Each file must decode through the claimed N frames using the existing environment. Preserve dimensions and original pixels; a strict pixel checksum may depend on decoder version. Retain source path, original bytes SHA256, byte count, source description, parent reference and exact index mapping for excerpts. Source provenance must establish genuine original footage rather than an overlay/reconstruction. No file, URL download or hardware capture is initiated by this preparation task.

## Required dataset and labels per scenario

- A completed existing v2 recorder bundle with original media available and pixel verification PASS; max_frames=N≥100; unchanged detector/model/threshold and tracker settings across scenarios. No selection schedule is needed for a tracking benchmark.
- A separate annotations/1.0 document made by the existing blank-template tool, bound to this exact bundle session/journal/media hashes. Annotate **every** recorded frame `0..N-1`; sparse subsets are not accepted for this milestone even though the general-purpose tool supports them.
- Persistent positive person IDs, image-space xyxy boxes, explicit occlusion labels, independent target_person_id for recovery, and reviewed frames. Full occlusion can use a null box instead of a guessed box. Omitted/out-of-frame identities and returning identities must be documented consistently.
- Actual annotator and a **different actual human reviewer**, with a review reference. Both must be recorded without placeholders; the reviewer must inspect all frames and resolve identity/occlusion disagreements. Do not promote AI/prediction labels to human-reviewed by setting flags. Human review cannot be inferred from a successful validator call.
- A source-bound scenario/review log recording event intervals, parent mapping, coverage, review identities, disagreements/resolutions and the evidence supporting each event. This is separate metadata in benchmark-input.template.json; it is not a replacement annotation schema or accepted CLI input.

The existing validator checks nonempty annotator/reviewer strings but does not enforce distinct people or prove review. The existing evaluator reports coverage but does not enforce this suite's 300-frame/three-scenario requirement. These are explicit human acceptance gates here; no duplicated validator/evaluator is introduced.

## Acceptance gates

1. **Media:** ≥3 accepted real scenarios; ≥100 consecutive annotated frames per scenario; ≥300 unique frames total; at least one crossing, one short occlusion and one long occlusion with human-confirmed intervals/context. All scenarios are multi-person; do not count copies or overlays.
2. **Provenance/review:** exact source/journal hashes, valid annotation schema, complete frame coverage, persistent identities, actual distinct annotator/reviewer, available review notes and resolved disagreements. Unknown/unresolvable target identity must be resolved or the scenario replaced; guessing is not accepted.
3. **Integrity:** existing `validate --verify-pixels` and `validate-annotations` PASS; dense reviewed frame set equals dataset frame set. Aggregate unique frames verified from original parent mappings. Structural PASS alone is insufficient.
4. **Comparison:** same saved detector observations and identical input hash for Greedy IoU and Hungarian; threshold=.3/max_missed=5; evaluator IoU=.5. Do not rerun YOLO independently for each tracker or tune on the benchmark.
5. **Metrics:** per-scenario IDF1, ID switches, fragmentation, target recovery (numerator/denominator) and tracker mean/median/P95/std/count latency. A target with no eligible completed gap has recovery N/A, never zero by substitution. At least one occlusion scenario must have an actually eligible completed recovery gap to assess recovery for the method; otherwise report N/A and the limitation, without fabricating a gap or result.
6. **Reproduction:** save exact CLI commands/environment/source hashes and annotation files, rerun on the same bundle/labels, and require identity metrics and predictions to match. Latency is remeasured, not required to be byte-identical; 5 warm-up + 30 measured full replays are provided by existing code. Never edit labels or tune trackers based on desired scores.
7. **Reporting:** disclose missing/occluded boxes and coverage, and separate synthetic regression from real human-verified results. A poor tracker result does not invalidate an honest benchmark. No invented minimum IDF1 or requirement that Hungarian outperform Greedy is imposed; this milestone measures behavior rather than guaranteeing improvement.

Benchmark completion requires all applicable gates and actual evidence. Current state fails media/human-data gates; no real comparison is executed. Machine-readable acceptance.json records this blocked state with null identity metrics. The template is deliberately incomplete; filling names/flags without actual review does not satisfy acceptance.
