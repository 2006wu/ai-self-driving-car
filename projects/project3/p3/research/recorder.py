"""Opt-in sequential local-file recorder. No capture device or hardware outputs."""
import hashlib
import platform
import time
from pathlib import Path

import cv2
import numpy as np

from ..detection import Detector
from ..pipeline import Frames
from .controllers import Observation, RuleBasedController
from .tracking import create_tracker
from .dataset import CATEGORIES, envelope, missing, require, integer
from .dataset_v2 import (VERSION, BUNDLE_VERSION, canonical, digest, json_write, session_id,
                         frame_uri, validate_record, validate_records, quality_report)


def implementation_fingerprint():
    root = Path(__file__).resolve().parents[1]
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob('*.py'))}


def record_media(source, destination, *, max_frames=120, method='greedy_iou',
                 selection_schedule=None, detector=None, detector_fingerprint=None, clock=time.perf_counter):
    """Sequential decoded indices start at zero; measured clocks vary per run.

    Dependency injection is for offline tests, with an explicit detector identity.
    Selection schedule maps integer frame indices to track IDs, or None to cancel.
    It never supplies human ground truth or demonstration labels.
    """
    source, destination = Path(source).resolve(), Path(destination)
    require(source.is_file(), 'local source media required (no URL/device index)')
    require(integer(max_frames, 1), 'positive frame bound required')
    schedule = {} if selection_schedule is None else dict(selection_schedule)
    require(all(integer(k) and k < max_frames and (v is None or integer(v, 1)) for k, v in schedule.items()), 'invalid selection schedule')
    tracker, controller = create_tracker(method), RuleBasedController()
    # Refuse an existing directory before constructing inference resources.
    destination.mkdir(parents=True, exist_ok=False)
    count, records = 0, []
    try:
        media_hash = digest(source)
        if detector is None:
            detector = Detector()
            detector_fingerprint = {'kind': 'YOLOv5n_flat_ONNX', 'model_sha256': detector.info['model_sha256'],
                'input': detector.info['input'], 'providers': detector.info['providers'],
                'confidence_objectness': detector.conf, 'threads': detector.info['threads']}
        require(isinstance(detector_fingerprint, dict) and bool(detector_fingerprint.get('kind'))
                and bool(detector_fingerprint.get('reference', detector_fingerprint.get('model_sha256'))), 'detector provenance required')
        config = {'tracker_method': method, 'tracker_threshold': .3, 'tracker_max_missed': 5,
                  'controller': 'rule_based', 'units': 'normalized_simulation', 'max_frames': max_frames,
                  'selection_schedule': {str(k): v for k, v in sorted(schedule.items())},
                  'detector': detector_fingerprint,
                  'decoder': {'opencv': cv2.__version__, 'numpy': np.__version__}}
        identity = {'media_sha256': media_hash, 'configuration': config,
                    'implementation': implementation_fingerprint()}
        sid = session_id(identity)
        origin = clock()
        def now(): return clock()-origin
        termination = 'frame_limit'
        with (destination/'records.jsonl').open('x', encoding='utf-8') as journal:
            with Frames(str(source), camera=False) as frames:
                iterator = iter(frames)
                for index in range(max_frames):
                    started = now()
                    try: image = next(iterator)
                    except StopIteration:
                        termination = 'EOF'
                        break
                    decoded = now()
                    # Hash before inference; reject mutation by injected/custom detectors.
                    pixels = hashlib.sha256(image.tobytes()).hexdigest()
                    detections, _ = detector.predict(image)
                    detected = now()
                    tracks = tracker.update(detections)
                    tracked = now()
                    event, requested = 'none', None
                    if index in schedule:
                        requested = schedule[index]
                        if requested is None:
                            event = 'cancel'; tracker.cancel_target(); action = controller.cancel()
                        else:
                            event = 'select'; tracker.select(requested); action = controller.select(requested, tracks)
                    else:
                        action = controller.predict(Observation(None, tracks, image.shape[:2], tracked-started))
                    decided = now()
                    require(hashlib.sha256(image.tobytes()).hexdigest() == pixels, 'detector mutated original decoded pixels')
                    uri = frame_uri(media_hash, index)
                    target = next((t for t in tracks if t['id'] == tracker.target), None)
                    record = {'schema_version': VERSION, 'session_id': sid, 'frame_id': index,
                        'timestamp': envelope({'seconds': decided, 'clock': 'session_elapsed_monotonic',
                                               'semantics': 'processing_complete'}, {'kind': 'observation', 'reference': uri}),
                        'data_source': {'kind': 'offline_media', 'reference': 'sha256:'+media_hash},
                        'frame_reference': {'media_sha256': media_hash, 'decoded_index': index,
                            'width': image.shape[1], 'height': image.shape[0], 'decoded_bgr_sha256': pixels},
                        'processing': {'clock': 'session_elapsed_monotonic', 'read_start': started,
                            'decode_end': decoded, 'detection_end': detected, 'tracking_end': tracked,
                            'decision_end': decided, 'age_at_decision_seconds': tracked-started},
                        'capture_timestamp': missing('Camera exposure/capture clock unavailable from local decoding'),
                        'selection': {'tracker_target_id': tracker.target, 'controller_target_id': controller.legacy.target,
                                      'event': event, 'requested_target_id': requested},
                        'legacy_decision': action.metadata,
                        'operator_command': missing('No operator selection scheduled') if event == 'none' else envelope(
                            event + (':'+str(requested) if event == 'select' else ''),
                            {'kind': 'offline_selection_schedule', 'reference': uri}),
                        'emergency_stop': missing('No physical emergency-stop measurement')}
                    for category in CATEGORIES: record[category] = missing('Not measured/annotated by offline recorder')
                    record['observations'] = envelope({'camera_frame_reference': uri,
                        'camera_metadata': {'width': image.shape[1], 'height': image.shape[0], 'color_space': 'BGR'},
                        'detections': detections, 'tracks': tracks, 'selected_target': tracker.target,
                        'target_box': target['box'] if target else None}, {'kind': 'observation', 'reference': uri})
                    record['rule_based_pseudo_labels'] = envelope({'linear': action.linear_velocity_command,
                        'angular': action.angular_velocity_command, 'units': action.units,
                        'controller_type': 'rule_based', 'source_controller': 'FollowController',
                        'status': action.status, 'reason': action.metadata['reason']}, {'kind': 'rule_based', 'reference': uri})
                    validate_record(record)
                    # Round-trip snapshot prevents subsequent tracker/detector mutation from altering prior rows.
                    payload = canonical(record)
                    from .dataset import loads
                    records.append(loads(payload))
                    journal.write(payload+'\n'); journal.flush()
                    count += 1
        validate_records(records)
        require(all(k < count for k in schedule), 'scheduled selection beyond available frames')
        require(digest(source) == media_hash, 'source media changed during recording')
        final = controller.stop(termination).metadata
        manifest = {'bundle_version': BUNDLE_VERSION, 'session_id': sid, 'identity': identity,
                    'media': {'path': str(source), 'sha256': media_hash, 'bytes': source.stat().st_size},
                    'records': {'file': 'records.jsonl', 'count': count, 'sha256': digest(destination/'records.jsonl')},
                    'termination': {'reason': termination, 'final_decision': final},
                    'runtime': {'python': platform.python_version(), 'platform': platform.platform()}}
        json_write(destination/'manifest.json', manifest)
        quality = quality_report(destination)
        require(quality['status'] == 'PASS', 'post-record validation failed: '+str(quality))
        json_write(destination/'quality.json', quality)
        return manifest
    except BaseException as error:
        # Partial journals are retained for diagnosis; never accepted as completed datasets.
        final = controller.stop('recording_failed', fault=True).metadata
        json_write(destination/'failure.json', {'status': 'FAIL', 'error': type(error).__name__,
                   'message': str(error), 'completed_rows': count, 'final_decision': final})
        raise
