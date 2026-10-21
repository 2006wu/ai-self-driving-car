"""Dependency-light motion tracking and explicitly synthetic evaluation checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from p3.tracking import Tracker
from p3.research.motion_tracking import KalmanIoUTracker
from p3.research.tracking import create_tracker
from p3.research.tracker_benchmark import generate_scenarios, run_benchmark


def person(x=0, class_id=0):
    return {'class_id': class_id, 'box': [x, 0, x+40, 80]}


class MotionTrackingTests(unittest.TestCase):
    def test_factory_and_defaults(self):
        self.assertIs(type(create_tracker()), Tracker)
        self.assertIsInstance(create_tracker('kalman_iou'), Tracker)
        with self.assertRaises(ValueError):
            create_tracker('unknown')
        for kwargs in ({'threshold': -1}, {'max_missed': True}, {'max_missed': -1},
                       {'center_distance_gate': -1}, {'center_distance_gate': float('nan')}):
            with self.assertRaises(ValueError):
                KalmanIoUTracker(**kwargs)

    def test_validation_is_atomic(self):
        tracker = KalmanIoUTracker()
        initial = tracker.update([person()])
        mean = tracker.filters[1][0].copy()
        for invalid in (None, {}, {'box': [0, 0, 1, 1]}, person(class_id='0'),
                        {'class_id': 0, 'box': [0, 0, 0, 1]},
                        {'class_id': 0, 'box': [0, 0, float('nan'), 1]}):
            with self.assertRaises(ValueError):
                tracker.update([person(5), invalid])
            self.assertEqual(list(tracker.tracks.values()), initial)
            self.assertTrue((tracker.filters[1][0] == mean).all())
        self.assertEqual(KalmanIoUTracker().update([person(class_id=1)]), [])

    def test_target_selection_matches_baseline(self):
        for cls in (Tracker, KalmanIoUTracker):
            tracker = cls(max_missed=1)
            self.assertEqual(tracker.target_state, 'none')
            tracker.update([person(), person(100)])
            self.assertEqual(tracker.target, 1)
            self.assertEqual(tracker.select_next(), 2)
            self.assertEqual(tracker.select(1), 1)
            for invalid in (True, 0, 3, '1'):
                with self.assertRaises(ValueError):
                    tracker.select(invalid)
            tracker.update([])
            self.assertEqual(tracker.target_state, 'missing')
            with self.assertRaises(ValueError):
                tracker.select(1)
            tracker.update([])
            self.assertEqual(tracker.target_state, 'lost')
            tracker.cancel_target()
            tracker.update([person()])
            self.assertIsNone(tracker.target)
            self.assertEqual(tracker.target_state, 'none')

    def test_coast_recover_delete_and_copy(self):
        tracker = KalmanIoUTracker(max_missed=3)
        for x in (0, 8, 16, 24):
            tracker.update([person(x)])
        previous = tracker.tracks[1]['box'][0]
        for missed in (1, 2, 3):
            tracks = tracker.update([])
            self.assertEqual(tracks[0]['state'], 'missing')
            self.assertEqual(tracks[0]['missed'], missed)
            self.assertGreater(tracks[0]['box'][0], previous)
            previous = tracks[0]['box'][0]
        self.assertEqual(tracker.update([person(56)])[0]['id'], 1)
        tracks = tracker.update([person(64)])
        tracks[0]['box'][0] = -999
        self.assertNotEqual(tracker.tracks[1]['box'][0], -999)
        for _ in range(4):
            tracker.update([])
        self.assertEqual(tracker.tracks, {})
        self.assertEqual(tracker.filters, {})
        self.assertEqual(tracker.target_state, 'lost')

    def test_optional_fallback(self):
        for gate, expected in ((None, 2), (1.5, 1)):
            tracker = KalmanIoUTracker(center_distance_gate=gate)
            tracker.update([person()])
            tracker.update([])
            visible = [t for t in tracker.update([person(50)]) if t['state'] == 'tracked']
            self.assertEqual(visible[0]['id'], expected)

    def test_synthetic_determinism_and_switches(self):
        self.assertEqual(generate_scenarios(), generate_scenarios())
        result = run_benchmark()
        self.assertEqual(result, run_benchmark())
        improvements = []
        for name in ('crossing', 'short_occlusion'):
            methods = result['scenarios'][name]['methods']
            baseline = methods['greedy_iou']['ID_switches']
            motion = methods['kalman_iou']['ID_switches']
            self.assertLessEqual(motion, baseline)
            improvements.append(motion < baseline)
        self.assertTrue(any(improvements))
        for scenario in result['scenarios'].values():
            for metrics in scenario['methods'].values():
                self.assertEqual(metrics['annotation_kind'], 'synthetic_ground_truth')

    def test_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'benchmark.json'
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
            command = [sys.executable, '-m', 'p3.research.tracker_benchmark', '--output', str(output)]
            first = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = output.read_bytes()
            self.assertEqual(json.loads(original), json.loads(json.dumps(run_benchmark())))
            second = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn('already exists', second.stderr)
            self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
