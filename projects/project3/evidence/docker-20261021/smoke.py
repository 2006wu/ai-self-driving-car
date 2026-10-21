import json
from collections import Counter
from pathlib import Path
import platform
import sys
import numpy as np
from p3.detection import Detector
from p3.follow import FollowController
from p3.pipeline import run
from p3.research.tracking import create_tracker
from p3.research.tracker_benchmark import run_benchmark

output = Path(sys.argv[1]) if len(sys.argv) == 2 else Path('artifacts/docker-validation-20261021')
output.mkdir(parents=True, exist_ok=True)
if any(output.iterdir()):
    raise FileExistsError('choose a new or empty output directory: ' + str(output))
result = {'platform': platform.platform(), 'python': sys.version,
          'scope': 'Offline files, synthetic boxes and software simulation only', 'runs': {}}
# Integration of predicted missing tracks with the existing latched stop policy.
tracker, controller = create_tracker('kalman_iou'), FollowController()
for x in (140, 144, 148):
    tracks = tracker.update([{'class_id': 0, 'box': [x, 100, x+40, 200]}])
    if x == 140:
        assert controller.select(1, tracks)['action'] == 'STOP'
    assert controller.update(tracks, (300, 320))['action'] == 'FOLLOW'
tracks = tracker.update([])
assert tracker.target_state == 'missing'
assert controller.update(tracks, (300, 320))['action'] == 'STOP'
tracks = tracker.update([{'class_id': 0, 'box': [156, 100, 196, 200]}])
assert tracker.target_state == 'tracked'
assert controller.update(tracks, (300, 320))['reason'] == 'explicit_confirmation_required'
assert controller.select(1, tracks)['action'] == 'STOP'
assert controller.update(tracks, (300, 320))['state'] == 'TRACKING'
result['kalman_follow_loss_recovery'] = 'PASS'

benchmark = run_benchmark()
with (output/'synthetic.json').open('x') as stream:
    json.dump(benchmark, stream, indent=2, allow_nan=False)
print('Synthetic benchmark: PASS', flush=True)
detector = Detector()
result['model'] = detector.info
for method in ('greedy_iou', 'kalman_iou'):
    for kind, source, limit, selected in (
        ('image', 'artifacts/bus.jpg', 1, 1),
        ('video', 'artifacts/inputs/usa.hevc', 300, None)):
        name = method+'-'+kind
        destination = output/name
        records = run(detector, source, destination, tracker=create_tracker(method),
                      controller=FollowController(), target_id=selected,
                      max_frames=limit, record=False)
        assert len(records) == limit
        assert all(r['decision']['simulation_only'] for r in records)
        if selected is None:
            assert all(r['decision']['action'] == 'STOP' for r in records)
        journal = [json.loads(line) for line in (destination/'events.jsonl').read_text().splitlines()]
        controls = [e for e in journal if e['event'] == 'simulated_control']
        assert controls[-1]['action'] == 'STOP'
        assert controls[-1]['speed'] == controls[-1]['turn'] == 0
        timings = np.array([r['timing']['inference_ms'] for r in records])
        summary = {'frames': len(records), 'detections': sum(len(r['detections']) for r in records),
                   'person_detections': sum(d['class_id'] == 0 for r in records for d in r['detections']),
                   'mean_inference_ms': float(timings.mean()), 'final_stop': 'PASS',
                   'decision_reasons': dict(Counter(r['decision']['reason'] for r in records))}
        with (destination/'run.json').open('x') as stream:
            json.dump({'summary': summary, 'frames': records}, stream, allow_nan=False)
        result['runs'][name] = summary
        print(name, summary, flush=True)
for kind in ('image', 'video'):
    baseline = json.loads((output/('greedy_iou-'+kind)/'run.json').read_text())['frames']
    motion = json.loads((output/('kalman_iou-'+kind)/'run.json').read_text())['frames']
    assert [r['detections'] for r in baseline] == [r['detections'] for r in motion]
result['detector_parity_between_trackers'] = 'PASS'
with (output/'summary.json').open('x') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
print('Docker integration smoke: PASS', flush=True)
