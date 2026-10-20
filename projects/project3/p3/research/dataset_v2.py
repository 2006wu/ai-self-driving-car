"""Independent synchronized offline contract. Version 1 remains unchanged."""
import copy
import hashlib
import json
import os
from pathlib import Path

from . import dataset as v1

VERSION = 'comma_body_research/2.0'
BUNDLE_VERSION = 'comma_body_bundle/2.0'
STAGES = ('read_start', 'decode_end', 'detection_end', 'tracking_end', 'decision_end')
EXTRA = {'frame_reference', 'processing', 'selection', 'capture_timestamp', 'legacy_decision'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def json_write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(canonical(value)+'\n')


def is_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def session_id(identity):
    return 'offline-'+hashlib.sha256(canonical(identity).encode()).hexdigest()


def frame_uri(media_hash, index):
    return f'sha256:{media_hash}#decoded_frame={index}'


class OriginalMediaMissing(ValueError):
    """Recorded media path is absent. Distinct from a hash or size mismatch."""


def resolve_root(media_root):
    """Explicit root wins. None falls back to P3_MEDIA_ROOT. Blank disables it."""
    if media_root is not None:
        text = str(media_root).strip()
        return Path(text).expanduser().resolve() if text else None
    text = os.environ.get('P3_MEDIA_ROOT', '').strip()
    return Path(text).expanduser().resolve() if text else None


def stored_media_path(source, media_root=None):
    """Absolute path, or a POSIX path relative to the configured media root."""
    source = Path(source).resolve()
    root = resolve_root(media_root)
    if root is None:
        return str(source), 'absolute'
    try:
        relative = source.relative_to(root)
    except ValueError as error:
        raise ValueError('source media is outside the configured media root') from error
    text = relative.as_posix()
    if text in ('', '.'):
        raise ValueError('source media is outside the configured media root')
    return text, 'relative'


def _lexical_within(root, candidate):
    root_norm = os.path.normpath(str(Path(root).resolve()))
    cand_norm = os.path.normpath(str(candidate))
    try:
        return os.path.commonpath([root_norm, cand_norm]) == root_norm
    except ValueError:
        return False


def _match_media_file(candidate, media):
    """Return the file when size and SHA256 match. Absent is None; a mismatch raises."""
    if not candidate.exists():
        return None
    if (not candidate.is_file() or candidate.stat().st_size != media['bytes']
            or digest(candidate) != media['sha256']):
        raise ValueError('media integrity failure')
    return candidate.resolve()


def resolve_original_media(media, media_root=None):
    """Locate original bytes without treating a missing file as corruption.

    Relative paths resolve only against the media root, never the process cwd.
    An existing manifest path that differs in size or SHA256 fails immediately.
    A missing legacy absolute path may match a byte-identical file under the
    media root (same path suffix or file name). A candidate file that is present
    there with a different size or SHA256 is a hash mismatch, not a missing file.
    """
    if not isinstance(media, dict):
        raise ValueError('invalid media reference')
    raw = media.get('path')
    v1.require(isinstance(raw, str) and bool(raw) and raw == raw.strip() and '\x00' not in raw, 'invalid media path')
    kind = media.get('path_kind')
    if kind is None:
        kind = 'absolute' if Path(raw).is_absolute() else 'relative'
    v1.require(kind in {'absolute', 'relative'}, 'invalid media path_kind')
    v1.require(is_hash(media.get('sha256')) and type(media.get('bytes')) is int and media['bytes'] >= 0,
               'media size/hash required')
    root = resolve_root(media_root)
    if kind == 'relative':
        v1.require(not Path(raw).is_absolute(), 'relative media path must not be absolute')
        if root is None:
            return None
        candidate = root / raw
        v1.require(_lexical_within(root, candidate), 'media path escapes media root')
        return _match_media_file(candidate, media)
    primary = Path(raw)
    v1.require(primary.is_absolute(), 'absolute media path required')
    if primary.exists():
        return _match_media_file(primary, media)
    if root is None:
        return None
    parts = primary.parts
    start = 1 if primary.is_absolute() else 0
    seen = set()
    for index in range(start, len(parts)):
        candidate = root.joinpath(*parts[index:])
        if not _lexical_within(root, candidate):
            continue
        key = os.path.normpath(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_file():
            continue
        if candidate.stat().st_size == media['bytes'] and digest(candidate) == media['sha256']:
            return candidate.resolve()
        raise ValueError('media found under media root but hash mismatch')
    return None


def validate_record(record):
    try:
        v1.require(isinstance(record, dict) and record.get('schema_version') == VERSION, 'v2 record required')
        v1.finite_tree(record)
        projection = {k: copy.deepcopy(v) for k, v in record.items() if k not in EXTRA}
        projection['schema_version'] = v1.VERSION
        # Reuse v1 geometry/units/category checks without changing v1 timestamp semantics.
        projection['timestamp'] = v1.missing('v2 processing timestamp validated separately')
        v1.validate_record(projection)
        v1.require(set(record) == set(projection) | EXTRA, 'missing/unknown v2 fields')
        ref = record['frame_reference']
        v1.require(set(ref) == {'media_sha256', 'decoded_index', 'width', 'height', 'decoded_bgr_sha256'}, 'frame reference fields')
        v1.require(is_hash(ref['media_sha256']) and is_hash(ref['decoded_bgr_sha256'])
                   and ref['decoded_index'] == record['frame_id'] and v1.integer(ref['decoded_index'])
                   and v1.integer(ref['width'], 1) and v1.integer(ref['height'], 1), 'invalid frame reference')
        uri = frame_uri(ref['media_sha256'], record['frame_id'])
        observations = record['observations']
        v1.require(observations['provenance']['kind'] == 'observation'
                   and observations['provenance']['reference'] == uri, 'observation provenance mismatch')
        obs = observations['value']
        v1.require(obs is not None and obs['camera_frame_reference'] == uri, 'missing media frame reference')
        v1.require(obs['camera_metadata'] == {'width': ref['width'], 'height': ref['height'], 'color_space': 'BGR'}
                   and isinstance(obs['detections'], list) and isinstance(obs['tracks'], list), 'missing observations')
        tracks = obs['tracks']
        for tr in tracks:
            v1.require(v1.integer(tr.get('missed')) and ((tr['state'] == 'tracked') == (tr['missed'] == 0)), 'inconsistent missed age')
        selection = record['selection']
        v1.require(set(selection) == {'tracker_target_id', 'controller_target_id', 'event', 'requested_target_id'}, 'selection fields')
        for key in ('tracker_target_id', 'controller_target_id', 'requested_target_id'):
            v1.require(selection[key] is None or v1.integer(selection[key], 1), 'invalid selection ID')
        v1.require(selection['event'] in {'none', 'select', 'cancel'}, 'invalid selection event')
        v1.require((selection['requested_target_id'] is not None) == (selection['event'] == 'select'), 'selection request mismatch')
        v1.require(obs['selected_target'] == selection['tracker_target_id'], 'tracker target mismatch')
        target = next((t for t in tracks if t['id'] == obs['selected_target']), None)
        v1.require(obs['target_box'] == (target['box'] if target else None), 'target box mismatch')
        processing = record['processing']
        v1.require(set(processing) == set(STAGES) | {'clock', 'age_at_decision_seconds'}, 'processing fields')
        v1.require(processing['clock'] == 'session_elapsed_monotonic', 'processing clock')
        values = [processing[k] for k in STAGES]
        v1.require(all(v1.number(v) and v >= 0 for v in values) and values == sorted(values), 'invalid processing order')
        v1.require(v1.number(processing['age_at_decision_seconds'])
                   and processing['age_at_decision_seconds'] == processing['tracking_end']-processing['read_start'], 'invalid decision age')
        v1.require(record['timestamp'] == v1.envelope(
            {'seconds': processing['decision_end'], 'clock': 'session_elapsed_monotonic', 'semantics': 'processing_complete'},
            {'kind': 'observation', 'reference': uri}), 'invalid processing timestamp/provenance')
        v1.require(record['capture_timestamp']['value'] is None
                   and record['capture_timestamp']['provenance']['kind'] == 'missing'
                   and bool(record['capture_timestamp']['provenance']['reason']), 'capture time unavailable in this contract')
        pseudo = record['rule_based_pseudo_labels']
        v1.require(pseudo['value'] is not None and pseudo['provenance']['reference'] == uri, 'missing control provenance')
        decision = record['legacy_decision']
        v1.require(set(decision) == {'state', 'reason', 'target_id', 'action', 'speed', 'turn', 'simulation_only'}
                   and decision['simulation_only'] is True, 'invalid legacy decision')
        v1.require((decision['target_id'] is None or v1.integer(decision['target_id'], 1))
                   and v1.number(decision['speed']) and v1.number(decision['turn'])
                   and decision['target_id'] == selection['controller_target_id'], 'controller target mismatch')
        if decision['state'] == 'TRACKING':
            v1.require(any(t['id'] == decision['target_id'] and t['state'] == 'tracked' for t in tracks),
                       'tracking controller requires visible selected track')
        v1.require((decision['action'] == 'STOP') == (decision['speed'] == decision['turn'] == 0)
                   and decision['action'] in {'STOP', 'FOLLOW'}, 'inconsistent action')
        v1.require(pseudo['value'] == {'linear': decision['speed'], 'angular': decision['turn'],
                    'units': 'normalized_simulation', 'controller_type': 'rule_based',
                    'source_controller': 'FollowController', 'status': decision['state'], 'reason': decision['reason']}, 'decision mismatch')
        for name in ('ground_truth', 'human_demonstrations', 'robot_measurements', 'emergency_stop'):
            v1.require(record[name]['value'] is None, 'recorder cannot supply human/physical ground truth')
        v1.require(record['data_source'] == {'kind': 'offline_media', 'reference': 'sha256:'+ref['media_sha256']}, 'source mismatch')
        expected_operator = v1.missing('No operator selection scheduled') if selection['event'] == 'none' else v1.envelope(
            selection['event'] + (':'+str(selection['requested_target_id']) if selection['event'] == 'select' else ''),
            {'kind': 'offline_selection_schedule', 'reference': uri})
        v1.require(record['operator_command'] == expected_operator, 'operator provenance mismatch')
        return record
    except (KeyError, TypeError, OverflowError, AttributeError) as error:
        raise ValueError('malformed synchronized record') from error


def validate_records(records):
    v1.require(isinstance(records, list) and bool(records), 'nonempty ordered records required')
    v1.require(all(isinstance(r, dict) for r in records), 'records must be objects')
    previous, sid, media = -1., records[0].get('session_id'), None
    for index, record in enumerate(records):
        validate_record(record)
        v1.require(record['session_id'] == sid and record['frame_id'] == index, 'duplicate/missing/out-of-order frame')
        ref = record['frame_reference']
        if media is None: media = ref['media_sha256']
        v1.require(ref['media_sha256'] == media, 'mixed source media')
        v1.require(record['processing']['read_start'] >= previous, 'timestamps out of order across frames')
        previous = record['processing']['decision_end']
    return records


def load_bundle(directory, *, verify_pixels=False, media_root=None, require_media=True):
    """Validate a completed bundle, and original media bytes when they are required.

    Journal hash, order and manifest identity are always checked. Direct callers
    still require the original file. quality_report passes require_media=False so
    a missing file can be reported separately from corruption.
    """
    try:
        directory = Path(directory)
        v1.require(not (directory/'failure.json').exists(), 'failed recording is not a completed dataset')
        manifest = v1.loads((directory/'manifest.json').read_text())
        v1.require(manifest['bundle_version'] == BUNDLE_VERSION, 'unsupported bundle')
        identity, media = manifest['identity'], manifest['media']
        v1.require(manifest['session_id'] == session_id(identity), 'session identity mismatch')
        v1.require(manifest['records']['file'] == 'records.jsonl', 'invalid records location')
        path = directory/'records.jsonl'
        v1.require(digest(path) == manifest['records']['sha256'], 'record integrity failure')
        records = validate_records([v1.loads(line) for line in path.read_text().splitlines()])
        v1.require(len(records) == manifest['records']['count'], 'record count mismatch')
        source = resolve_original_media(media, media_root=media_root)
        v1.require(media['sha256'] == identity['media_sha256'] == records[0]['frame_reference']['media_sha256'],
                   'media reference mismatch')
        if source is None and (require_media or verify_pixels):
            raise OriginalMediaMissing('missing original media reference: '+media['path'])
        v1.require(all(r['session_id'] == manifest['session_id'] for r in records), 'session mismatch')
        config = identity['configuration']
        v1.require(config['tracker_method'] in {'greedy_iou', 'hungarian'} and config['controller'] == 'rule_based'
                   and config['units'] == 'normalized_simulation' and v1.integer(config['max_frames'], 1)
                   and len(records) <= config['max_frames']
                   and v1.number(config['tracker_threshold']) and 0 <= config['tracker_threshold'] <= 1
                   and v1.integer(config['tracker_max_missed']), 'invalid configuration')
        v1.require(isinstance(identity['implementation'], dict) and bool(identity['implementation'])
                   and all(isinstance(k, str) and is_hash(v) for k, v in identity['implementation'].items()), 'implementation provenance missing')
        detector = config['detector']
        v1.require(isinstance(detector, dict) and isinstance(detector.get('kind'), str) and bool(detector['kind'])
                   and bool(detector.get('reference', detector.get('model_sha256'))), 'detector provenance missing')
        schedule = config['selection_schedule']
        v1.require(isinstance(schedule, dict) and all(isinstance(k, str) and k.isdecimal()
                   and str(int(k)) == k and int(k) < len(records) and (v is None or v1.integer(v, 1))
                   for k, v in schedule.items()), 'invalid selection schedule')
        for r in records:
            requested = schedule.get(str(r['frame_id']), 'none')
            v1.require(r['selection']['event'] == ('cancel' if requested is None else 'none' if requested == 'none' else 'select')
                       and r['selection']['requested_target_id'] == (requested if type(requested) is int else None), 'schedule mismatch')
        final = manifest['termination']['final_decision']
        v1.require(final['action'] == 'STOP' and final['speed'] == final['turn'] == 0
                   and final['simulation_only'] is True, 'final simulated STOP missing')
        v1.require(manifest['termination']['reason'] in {'EOF', 'frame_limit'}, 'incomplete recording')
        if verify_pixels:
            from ..pipeline import Frames
            with Frames(str(source), camera=False) as frames:
                iterator = iter(frames)
                for record in records:
                    image = next(iterator)
                    ref = record['frame_reference']
                    v1.require(image.shape[:2] == (ref['height'], ref['width'])
                               and hashlib.sha256(image.tobytes()).hexdigest() == ref['decoded_bgr_sha256'], 'decoded frame integrity failure')
        return manifest, records
    except (KeyError, TypeError, OverflowError, AttributeError, OSError, UnicodeError, StopIteration) as error:
        raise ValueError('invalid/incomplete bundle: '+str(error)) from error


def quality_report(directory, *, verify_pixels=False, media_root=None, require_media=False):
    """PASS when recorded data and original bytes check out.

    WARN when the journal and recorded hashes are intact but the original file
    is absent. FAIL on corruption, including a present file with the wrong size
    or SHA256. verify_pixels or require_media also fails when that file is absent.
    WARN is not a pass of the media bytes.
    """
    try:
        manifest, records = load_bundle(directory, verify_pixels=False, media_root=media_root, require_media=False)
        warnings, media_verified, pixels_verified = [], False, False
        try:
            load_bundle(directory, verify_pixels=verify_pixels, media_root=media_root, require_media=True)
            media_verified, pixels_verified = True, verify_pixels
        except OriginalMediaMissing as missing:
            if verify_pixels or require_media:
                reason = 'decoded pixel verification failed: ' if verify_pixels else 'original media required: '
                raise ValueError(reason + str(missing)) from missing
            warnings.append(str(missing))
        counts = {'detections': sum(len(r['observations']['value']['detections']) for r in records),
                  'person_detections': sum(d['class_id'] == 0 for r in records for d in r['observations']['value']['detections']),
                  'visible_track_rows': sum(t['state'] == 'tracked' for r in records for t in r['observations']['value']['tracks']),
                  'selection_events': sum(r['selection']['event'] != 'none' for r in records),
                  'simulated_follow_rows': sum(r['legacy_decision']['action'] == 'FOLLOW' for r in records)}
        return {'status': 'WARN' if warnings else 'PASS', 'schema_version': VERSION, 'session_id': manifest['session_id'],
                'frames': len(records), 'ordered_contiguous_frames': True, 'media_hash_verified': media_verified,
                'original_media': 'missing' if warnings else 'present', 'warnings': warnings,
                'record_hash_verified': True, 'decoded_pixels_verified': pixels_verified, **counts,
                'capture_timestamps_available': 0, 'human_annotation_status': 'BLOCKED: no human labels in recorder',
                'missing_categories': ['capture_timestamp', 'human_demonstrations', 'robot_measurements', 'ground_truth', 'emergency_stop'],
                'scope': 'structural integrity and recorded hashes; original media bytes were not present'
                         if warnings else 'structural/media integrity; no physical safety or truth certification'}
    except ValueError as error:
        return {'status': 'FAIL', 'errors': [str(error)]}
