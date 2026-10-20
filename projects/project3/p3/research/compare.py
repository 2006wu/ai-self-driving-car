"""Compare selectable trackers on exactly the existing synthetic fixture inputs."""
import argparse
import json
import time
import platform
from ..scenarios import scenario_suite
from ..tracking_eval import evaluate_sequence
from ..evaluation import stats
from .tracking import create_tracker


def compare():
    result = {'scope': 'synthetic fixtures only; no real tracking accuracy',
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'timing_scope': 'perf_counter tracker.update only; 5 unmeasured + 30 measured replays per scenario',
              'methods': {}}
    for method in ('greedy_iou', 'hungarian'):
        output = []
        for scenario in scenario_suite()['scenarios']:
            source = scenario['frames']
            frames, timings = [], []
            # Recover the original detection visibility from baseline predictions:
            # baseline emits exactly one tracked row for each supplied detection.
            # Boxes preserve input order only imperfectly, so rebuild in GT order,
            # including only GT boxes present among tracked baseline predictions.
            inputs = []
            for row in source:
                visible_boxes = [p['box'] for p in row['predictions']]
                inputs.append([{'class_id': 0, 'box': g['box']} for g in row['ground_truth']
                               if g['box'] in visible_boxes])
            for replay in range(35):
                tracker = create_tracker(method)
                for row, detections in zip(source, inputs):
                    start = time.perf_counter()
                    tracks = tracker.update(detections)
                    elapsed = (time.perf_counter()-start)*1000
                    if replay >= 5: timings.append(elapsed)
                    if replay == 0:
                        frames.append({'frame': row['frame'], 'ground_truth': row['ground_truth'],
                                       'predictions': [{'id': t['id'], 'box': t['box']} for t in tracks if t['state'] == 'tracked']})
            metrics = evaluate_sequence(frames, 'synthetic_ground_truth', target_gt_id=1)
            if method == 'greedy_iou' and metrics != scenario['metrics']:
                raise AssertionError('reconstructed fixture changed baseline metrics')
            output.append({'scenario': scenario['scenario'], 'metrics': metrics, 'update_ms': stats(timings)})
        result['methods'][method] = output
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination'); args = parser.parse_args()
    result = compare()
    with open(args.destination, 'x') as stream: json.dump(result, stream, indent=2, allow_nan=False)
