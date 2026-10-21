# Synchronized offline dataset contract v2.0

Authoritative validator: `projects/project3/p3/research/dataset_v2.py`.

**Versioning:** record `schema_version = comma_body_research/2.0`; bundle `bundle_version = comma_body_bundle/2.0`. Schema v1.0 and the old event exporter are byte-identical to Milestone 1. v2 requires full observations, sequential decoded frame references and new processing timestamp semantics, so it is intentionally a separate incompatible version. Passing a v2 record to the v1 validator fails. The v2 validator reuses v1 category/geometry/unit checks through an internal validation projection only; it never rewrites stored v2 timestamps as v1 timestamps.

A completed bundle contains `manifest.json`, `records.jsonl`, and `quality.json`. A failure retains a partial journal and `failure.json`; the validator refuses a bundle containing that marker. A missing manifest is incomplete. Files/directories are exclusively created. The recorder does not copy or modify source media. The manifest stores the original media location, byte length and SHA256. With `--media-root` or `P3_MEDIA_ROOT`, `path` is relative to that directory and `path_kind` is `relative`. Otherwise `path` is absolute and `path_kind` is `absolute`. Manifests recorded before `path_kind` existed still validate: an absolute `path` with no `path_kind` is treated as absolute. Records use content hashes, not filesystem paths. `load_bundle` still requires the original bytes. `quality_report` and `python -m p3.research.offline validate` check the journal and recorded hashes even when that file is absent, and report absence as `WARN` rather than `FAIL`. `--require-media` and `--verify-pixels` make that absence a `FAIL`. A file that is present with a different size or SHA256 is `FAIL`. A byte-identical copy can be checked with `--media-root`: a relative path is joined to that root, and a missing legacy absolute path matches the same suffix or file name under the root when the bytes match. A candidate file under that root with a different size or SHA256 is `FAIL` (`media found under media root but hash mismatch`). Relative paths are never resolved against the process cwd.

## Manifest

| Field | Meaning |
|---|---|
| bundle_version | Fixed bundle schema |
| session_id | `offline-` + SHA256(canonical identity JSON) |
| identity.media_sha256 | Original encoded source bytes |
| identity.configuration | Detector kind/model hash/providers/input/objectness threshold/threads; decoder OpenCV/NumPy versions; tracker method/threshold/max_missed; rule-based controller; normalized units; frame bound; explicit selection schedule |
| identity.implementation | SHA256 of existing p3 and research Python sources, sorted by module-relative filename |
| media | Original path (`path`, and `path_kind` of `absolute` or `relative` when written by the current recorder), SHA256, byte count |
| records | Fixed `records.jsonl`, row count and SHA256 |
| termination | EOF or frame_limit, plus final original-controller simulated STOP |
| runtime | Python/platform strings |

The session denotes a **logical processing recipe**, not a unique wall-clock execution. Identical original bytes and configuration/implementation give identical session/frame IDs across locations and reruns. A different tracker/configuration/source/implementation yields another session. Actual measured processing times, output decisions affected by measured staleness, and journal hashes can differ between runs. Annotation references bind to the exact journal hash as well as logical session/media, so an old annotation document cannot silently attach to a different run. The manifest is not signed; integrity detects corruption, not a malicious actor able to rewrite all data and checksums.

## Per-frame record

Required original v1 category names remain: `session_id`, `frame_id`, `timestamp`, `data_source`, `observations`, `rule_based_pseudo_labels`, `human_demonstrations`, `robot_measurements`, `ground_truth`, `operator_command`, `emergency_stop`, plus the v2 `schema_version` and extensions below. Unknown top-level record keys fail validation.

| Field | v2 contract |
|---|---|
| frame_id | Contiguous zero-based decoded order, beginning at 0; no sampling/skipping in recorder |
| frame_reference | Original media SHA256, decoded_index (equal to frame_id), width/height, SHA256 of decoded uint8 BGR `image.tobytes()` |
| observations | Sourced `{value, provenance}` envelope: original frame content URI, dimensions/color space, all YOLO detections, all person tracks including missing rows, tracker-selected target and its latest box (null after expiry/no target) |
| timestamp | Sourced envelope with seconds = decision_end; clock = session_elapsed_monotonic; semantics = processing_complete |
| processing | Clock plus measured read_start, decode_end, detection_end, tracking_end, decision_end; age_at_decision_seconds = tracking_end - read_start |
| capture_timestamp | Explicit missing envelope and reason: camera exposure/capture timestamp is unavailable |
| selection | Tracker target ID and controller target ID recorded separately; event none/select/cancel and requested_target_id |
| legacy_decision | Original FollowController dictionary including state/reason/target/action/speed/turn/simulation_only |
| rule_based_pseudo_labels | Original normalized speed/turn mapped to linear/angular fields, source FollowController, rule_based type, status/reason, sourced to this frame; always normalized_simulation units |
| operator_command | Explicit offline selection-schedule event and provenance, or missing. This is not a human motor demonstration. |
| human_demonstrations / robot_measurements / ground_truth / emergency_stop | Missing envelopes with reasons. Offline recorder cannot populate these with predictions, software STOP or inferred measurements. Human annotations live in a separately validated artifact. |
| data_source | offline_media and SHA256 reference |

Frame URI is `sha256:ENCODED_MEDIA_HASH#decoded_frame=N`. It always refers to the original media, not a rendered overlay. Frame dimensions describe decoded pixels, not the fixed model tensor. YOLO objectness remains objectness rather than class probability. Person tracking IDs remain association IDs, distinct from human identities. A selected tracker target can coexist with an IDLE controller; only explicit schedule events arm/rearm the original rule controller. Selection frames first emit the original zero output. Cancel disables tracker automatic selection and stops the controller.

## Timestamp semantics

A single `time.perf_counter` monotonic origin is sampled per recording after detector construction. Source opening can precede the first read_start offset. Boundaries enclose sequential read/decode, pixel fingerprinting plus YOLO, tracking, and decision computation. `processing_complete` means **decision-stage completion**, not exposure time or completion of file export. Record validation, pixel mutation checks and journal writes occur later and are not in decision_end. The next read_start includes intervening work. Values are elapsed seconds, not Unix time.

Age passed into the controller is the measured tracking_end-read_start interval, including file decode and computation. It is recorded and never forced to zero to obtain a movement decision. Explicit select/cancel uses the original controller API; no subsequent update is hidden within a selection frame. No PTS/FPS-to-exposure conversion, wall-clock inference or simulated odometry is used. No cross-device synchronization is claimed.

## Validation and quality

`validate_record` checks required fields, reference association, original pixel dimensions, finite ordered processing times, timestamp/provenance equality, control source/type/status/units/bounds and legacy decision consistency, target references, boxes, track age/state, and category isolation. `validate_records` additionally checks one session/media, contiguous unique frame IDs and nonoverlapping ordered processing intervals.

`load_bundle` checks journal hash/count, content-derived session identity, configuration/provenance, schedule consistency, completion and final zero simulated output. When the original file is required (the direct-call default, or `verify_pixels=True`), it also checks that file's length and hash. `verify_pixels=True` re-decodes the source in order and verifies every recorded frame's dimensions/BGR pixel hash. Decoder changes may correctly trigger failure; use the recorded decoder environment rather than silently accepting different pixels. EOF on unknown-length native streams can still be indistinguishable from a decode failure, inherited from Frames. If those bytes are absent, `verify_pixels=True` fails instead of reporting the pixels as verified.

Quality reports contain PASS, WARN or FAIL. WARN means the recorded rows and hashes checked out and the original file was not available (`original_media` is `missing`, `media_hash_verified` is false). FAIL is reserved for integrity problems, including a present file that does not match. Counts cover frames, detections, person detections, visible tracks, selection events and FOLLOW rows, plus checksum verification, optional pixel verification and explicit missing categories. PASS certifies executed structural/media checks only. WARN does not certify the original bytes. Neither certifies annotation truth, person identity, physical safety or training readiness.
