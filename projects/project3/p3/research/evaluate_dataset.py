"""Compare both existing trackers on identical recorded detector observations."""
import hashlib
import time

from ..evaluation import stats
from ..tracking_eval import evaluate_sequence
from .tracking import create_tracker
from .annotations import validate_annotations
from .dataset_v2 import canonical, load_bundle


def compare_dataset(directory, annotations=None, *, media_root=None):
    manifest, records = load_bundle(directory, media_root=media_root)
    gt, annotation_error = None, None
    if annotations is not None:
        try:
            validate_annotations(annotations, manifest, records)
            gt = {f['frame_id']: [{'id': p['person_id'], 'box': p['box']}
                                 for p in f['persons'] if p['box'] is not None] for f in annotations['frames']}
        except ValueError as error:
            annotation_error = str(error)
    inputs = [r['observations']['value']['detections'] for r in records]
    input_hash = hashlib.sha256(canonical(inputs).encode()).hexdigest()
    report = {'session_id': manifest['session_id'], 'records_sha256': manifest['records']['sha256'],
              'detector_input_sha256': input_hash, 'recorded_frames': len(records),
              'real_accuracy_status': 'TESTED: supplied reviewed annotations only' if gt is not None else 'BLOCKED: valid reviewed human annotations unavailable',
              'annotation_error': annotation_error, 'methods': {},
              'timing_scope': 'tracker.update only; 5 unmeasured and 30 measured full sequential replays',
              'scope': 'no closed loop or physical control; tracking uses all frames before sampled annotation evaluation'}
    for method in ('greedy_iou', 'hungarian'):
        latency, predictions = [], {}
        for repeat in range(35):
            tracker = create_tracker(method, threshold=manifest['identity']['configuration']['tracker_threshold'],
                                     max_missed=manifest['identity']['configuration']['tracker_max_missed'])
            for record, detections in zip(records, inputs):
                start = time.perf_counter()
                tracks = tracker.update(detections)
                duration = (time.perf_counter()-start)*1000
                if repeat >= 5: latency.append(duration)
                if repeat == 0:
                    predictions[record['frame_id']] = [{'id': t['id'], 'box': t['box']} for t in tracks if t['state'] == 'tracked']
        metrics = None
        if gt is not None:
            frames = [{'frame': i, 'ground_truth': rows, 'predictions': predictions[i]} for i, rows in gt.items()]
            metrics = evaluate_sequence(frames, 'human_ground_truth', target_gt_id=annotations['target_person_id'])
        report['methods'][method] = {'input_sha256': input_hash, 'tracking_ms': stats(latency),
                                     'metrics': metrics, 'predictions': predictions}
    report['annotation_coverage'] = None if gt is None else {
        'evaluated_frames': list(gt), 'fraction_of_recorded_frames': len(gt)/len(records),
        'fully_occluded_without_box_excluded': sum(p['box'] is None for f in annotations['frames'] for p in f['persons']),
        'policy': 'No interpolation. Metrics use only reviewed frames; full occlusion without a box is excluded from GT box matching. Predictions still count without a matching GT box; no occlusion ignore regions are inferred. Occlusion with a trusted box is included. Recovery/fragmentation cover the sampled sequence only.'}
    return report
