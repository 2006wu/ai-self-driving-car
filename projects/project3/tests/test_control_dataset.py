"""Offline synthetic contracts; no physical acceptance claims."""
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from p3.research import control_dataset as cd
from p3.research import dataset_v2 as v2
from p3.research import dataset as v1
from p3.research.closed_loop import run_scenario
from p3.research.pid_controller import PIDFollowController


class ControlDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build(self, name='data', **kwargs):
        path = self.root/name
        cd.build_sim(path, scenarios=('straight_walk', 'occlusion', 'too_close'), steps=55, **kwargs)
        return path

    def rows(self, path):
        return [v1.loads(line) for split in cd.SPLITS for line in (path/f'samples-{split}.jsonl').read_text().splitlines()]

    def test_schema_good_bad(self):
        row = self.rows(self.build())[0]
        self.assertEqual(cd.validate_sample(row), row)
        for key in row:
            bad = copy.deepcopy(row); del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError): cd.validate_sample(bad)
        for key, value in [('schema', 'wrong'), ('step', -1), ('feature_vector', []), ('frame_ref', '/raw/pixels.png')]:
            bad = copy.deepcopy(row); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): cd.validate_sample(bad)
        for value in (float('nan'), float('inf'), True, .4):
            bad = copy.deepcopy(row); bad['teacher_action']['linear'] = value
            with self.assertRaises(ValueError): cd.validate_sample(bad)
        bad = copy.deepcopy(row); bad['sim_ground_truth']['for_model_input'] = True
        with self.assertRaises(ValueError): cd.validate_sample(bad)
        bad = copy.deepcopy(row); bad['safety']['supervisor_latched'] = True
        with self.assertRaises(ValueError): cd.validate_sample(bad)

    def test_splits_no_leak_and_order(self):
        path = self.build(episodes_per_scenario=3)
        manifest, _ = cd.validate(path)
        episodes = {}
        rows = self.rows(path)
        for row in rows:
            self.assertEqual(episodes.setdefault(row['episode_id'], row['split']), row['split'])
        self.assertEqual(set(episodes), set(manifest['episodes']))
        row = rows[0]
        ordered = sorted([r for r in rows if r['episode_id'] == row['episode_id']], key=lambda r: r['step'])
        bad = copy.deepcopy(ordered[1]); bad['split'] = 'test' if row['split'] != 'test' else 'train'
        with self.assertRaisesRegex(ValueError, 'leakage'): cd.validate_samples([row, bad])
        with self.assertRaisesRegex(ValueError, 'duplicate'): cd.validate_samples([row, row])
        with self.assertRaisesRegex(ValueError, 'nonmonotonic'): cd.validate_samples(ordered[::-1])
        self.assertEqual(cd.split_episode('same', (1, 0, 0)), 'train')
        with self.assertRaises(ValueError): cd.split_episode('same', (.7, .2, .2))

    def test_deterministic_bytes_and_refuse_existing(self):
        a, b = self.build('a', seed=17, perturb=True), self.build('b', seed=17, perturb=True)
        for path in a.iterdir(): self.assertEqual(path.read_bytes(), (b/path.name).read_bytes())
        with self.assertRaises(ValueError): cd.build_sim(a)
        self.assertEqual(cd.validate(a), cd.validate(b))

    def test_tampering(self):
        path = self.build()
        sample = next(p for p in path.glob('samples-*.jsonl') if p.stat().st_size)
        sample.write_text(sample.read_text()+'\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): cd.validate(path)

    def test_features_exclude_privileged_and_labels(self):
        row = self.rows(self.build())[0]
        vector = cd.features(row['observation'])
        row['sim_ground_truth']['distance_m'] = 999
        row['teacher_action']['linear'] = 0
        self.assertEqual(vector, cd.features(row['observation']))
        self.assertEqual(len(vector), len(cd.FEATURES))
        self.assertFalse(set(cd.FEATURES) & {'distance_m', 'bearing_rad', 'linear', 'angular'})

    def test_recorded_events_missing_and_exclusion(self):
        source = self.root/'events.jsonl'
        events = [{'event': 'frame', 'time_seconds': i*.1, 'frame': i, 'target': 1,
                   'decision': None if i == 1 else {'simulation_only': True, 'action': 'FOLLOW',
                    'speed': .3, 'turn': 0., 'state': 'TRACKING', 'reason': 'visible_unambiguous_target'}} for i in range(3)]
        source.write_text(''.join(v2.canonical(e)+'\n' for e in events))
        output = self.root/'recorded'
        cd.build_recorded([source], output)
        manifest, stats = cd.validate(output)
        self.assertEqual(manifest['excluded_without_teacher'], 1)
        self.assertEqual(sum(s['count'] for s in stats.values()), 2)
        for row in self.rows(output):
            self.assertEqual(row['timestamp']['semantics'], 'journal_emission')
            self.assertIsNone(row['frame_ref'])
            self.assertIsNone(row['observation']['target_visible'])
            self.assertIn('safety.final_gated_command', row['missing_fields'])
            self.assertEqual(row['source']['reference'], v2.digest(source))

    def test_bundle_adapter_uses_v2_reader_and_controller_target(self):
        record = {'session_id': 'offline-fixture', 'frame_id': 0,
            'timestamp': {'value': {'seconds': .1, 'clock': 'session_elapsed_monotonic', 'semantics': 'processing_complete'}},
            'rule_based_pseudo_labels': {'value': {'linear': 0., 'angular': 0., 'status': 'IDLE', 'reason': 'idle', 'units': 'normalized_simulation'}},
            'observations': {'value': {'camera_metadata': {'height': 300, 'width': 400}, 'tracks': [
                {'id': 1, 'state': 'tracked', 'box': [10, 20, 30, 40]}], 'selected_target': 1,
                'camera_frame_reference': v2.frame_uri('a'*64, 0)}},
            'selection': {'controller_target_id': None}, 'processing': {'age_at_decision_seconds': .02}}
        bundle = self.root/'bundle'; bundle.mkdir(); (bundle/'records.jsonl').write_text('fixture\n')
        with patch.object(v2, 'load_bundle', return_value=({}, [record])) as loader:
            output = self.root/'recorded'
            cd.build_recorded([bundle], output, media_root='')
            loader.assert_called_once_with(bundle, require_media=False, media_root='')
        cd.validate(output)
        row = self.rows(output)[0]
        self.assertFalse(row['observation']['target_visible'])
        self.assertIsNone(row['observation']['bbox_x1'])
        self.assertEqual(row['frame_ref'], v2.frame_uri('a'*64, 0))

    def test_stats_sanity(self):
        _, stats = cd.validate(self.build())
        self.assertEqual(sum(s['count'] for s in stats.values()), 330)
        self.assertTrue(any(s['stop_fraction'] for s in stats.values() if s['count']))
        for split in stats.values():
            for dist in split['features'].values():
                self.assertEqual(dist['count']+dist['missing'], split['count'])
                if dist['count']:
                    self.assertLessEqual(dist['min'], dist['mean']+1e-12)
                    self.assertLessEqual(dist['mean'], dist['max']+1e-12)
                    self.assertGreaterEqual(dist['std'], 0.)

    def test_hook_preserves_metrics(self):
        captured = []
        baseline = run_scenario(PIDFollowController(), 'occlusion', 60)
        hooked = run_scenario(PIDFollowController(), 'occlusion', 60, on_step=lambda *args: captured.append(args))
        self.assertEqual(baseline, hooked)
        self.assertEqual(len(captured), 60)
        self.assertEqual(captured[40][3].linear_velocity_command, 0.)
        self.assertTrue(captured[40][4])

    def test_cli_and_committed_sample(self):
        output = self.root/'cli'
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(cd.main(['build-sim', '--output', str(output), '--steps', '2']), 0)
            cd.main(['validate', str(output)])
            cd.main(['stats', str(output)])
        self.assertIn('stop_fraction', stream.getvalue())
        sample = Path(__file__).resolve().parents[1]/'p3/research/samples/control-dataset-sample'
        cd.validate(sample)
        self.assertLess(sum(p.stat().st_size for p in sample.iterdir()), 300_000)
        rebuilt = self.root/'rebuilt'
        with contextlib.redirect_stdout(io.StringIO()):
            cd.main(['build-sim', '--output', str(rebuilt), '--steps', '4', '--seed', '7'])
        for path in sample.iterdir(): self.assertEqual(path.read_bytes(), (rebuilt/path.name).read_bytes())


if __name__ == '__main__':
    unittest.main()
