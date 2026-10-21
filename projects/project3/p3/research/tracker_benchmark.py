"""Seeded synthetic box benchmark, without images, detectors or human annotations."""
import argparse
import json
from pathlib import Path

import numpy as np

from .tracking import create_tracker
from ..tracking_eval import evaluate_sequence

METHODS = ('greedy_iou', 'hungarian', 'kalman_iou')
PARAMETERS = {'frames': 30, 'box_width': 40, 'box_height': 80,
              'crossing_speed': 8, 'crossing_start': 284, 'fast_speed': 22, 'warmup_frames': 5, 'occlusion_frames': [10, 11, 12],
              'dropout_frames': [8, 17], 'jitter_std': 2.,
              'tracker': {'threshold': .3, 'max_missed': 5}, 'evaluation_iou': .5}


def generate_scenarios(seed=2026):
    """Ground truth stays present during occlusion/dropout to count missed boxes.

    All positions are synthetic pixels. Occlusion removes target detections only;
    no visibility preprocessing is claimed. Detection order is seeded and shuffled.
    """
    scenarios = {}
    for offset, name in enumerate(('crossing', 'fast_lateral', 'short_occlusion', 'jitter', 'dropout')):
        scenario_seed = seed+offset
        rng = np.random.default_rng(scenario_seed)
        frames = []
        for frame in range(PARAMETERS['frames']):
            positions = [(1, 40+8*frame, 80)]
            if name == 'crossing':
                positions.append((2, PARAMETERS['crossing_start']-8*frame, 80))
            if name == 'fast_lateral':
                positions = [(1, 40+8*min(frame, PARAMETERS['warmup_frames'])+PARAMETERS['fast_speed']*max(0, frame-PARAMETERS['warmup_frames']), 80)]
            truth, detections = [], []
            for identity, x, y in positions:
                box = [x, y, x+PARAMETERS['box_width'], y+PARAMETERS['box_height']]
                truth.append({'id': identity, 'box': box})
                if name == 'short_occlusion' and frame in PARAMETERS['occlusion_frames']:
                    continue
                if name == 'dropout' and frame in PARAMETERS['dropout_frames']:
                    continue
                noise = rng.normal(0, PARAMETERS['jitter_std'], 2) if name == 'jitter' else np.zeros(2)
                detections.append({'class_id': 0, 'box': (np.array(box)+np.tile(noise, 2)).tolist()})
            rng.shuffle(detections)
            frames.append({'frame': frame, 'ground_truth': truth, 'detections': detections})
        scenarios[name] = {'seed': scenario_seed, 'frames': frames}
    return scenarios


def evaluate_tracker(frames, method):
    tracker = create_tracker(method, **PARAMETERS['tracker'])
    evaluated = []
    for frame in frames:
        tracks = tracker.update(frame['detections'])
        # Coasting boxes are not detections or evidence that a target is visible.
        predictions = [{'id': t['id'], 'box': t['box']} for t in tracks if t['state'] == 'tracked']
        evaluated.append({'frame': frame['frame'], 'ground_truth': frame['ground_truth'],
                          'predictions': predictions})
    return evaluate_sequence(evaluated, annotation_kind='synthetic_ground_truth',
                             iou_threshold=PARAMETERS['evaluation_iou'], target_gt_id=1)


def run_benchmark(seed=2026):
    return {'annotation_kind': 'synthetic_ground_truth', 'seed': seed,
            'scope': 'Synthetic boxes only; no real identity or physical safety evidence.',
            'parameters': PARAMETERS,
            'scenarios': {name: {'seed': scenario['seed'],
                                'methods': {method: evaluate_tracker(scenario['frames'], method)
                                            for method in METHODS}}
                          for name, scenario in generate_scenarios(seed).items()}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output already exists; choose a new path')
    result = run_benchmark(args.seed)
    try:
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except FileExistsError:
        parser.error('output already exists; choose a new path')


if __name__ == '__main__':
    main()
