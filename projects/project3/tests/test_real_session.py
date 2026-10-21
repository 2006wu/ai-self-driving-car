"""Synthetic local journals only; never open media or hardware."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from p3.research import control_dataset as cd, dataset_v2 as v2, real_session as rs


def fixture(root, simulated=True):
    root.mkdir()
    events, frames = [], []
    for i in range(4):
        decision = {'simulation_only': True, 'state': 'TRACKING', 'reason': 'visible_unambiguous_target',
                    'target_id': 1, 'action': 'STOP' if i >= 2 else 'FOLLOW',
                    'speed': 0. if i >= 2 else .2, 'turn': 0.}
        frame = {'frame': i, 'target': 1, 'decision': decision, 'timing': {},
                 'tracks': [{'id': 1, 'state': 'tracked', 'box': [10, 10, 20, 30]}]}
        frames.append(frame)
        events.append({'event': 'simulated_control', 'time_seconds': .1*i+.04, **decision, 'frame': i})
        events.append({'event': 'frame', 'time_seconds': .1*i+.05, 'frame': i,
                       'target': 1, 'decision': decision, 'timing': {}, 'stream_dropped_frames': 0})
    (root/'events.jsonl').write_text(''.join(v2.canonical(e)+'\n' for e in events))
    v2.json_write(root/'run.json', {'camera': False, 'input': 'stream:REDACTED', 'frames': frames})
    v2.json_write(root/'run-status.json', {'input_kind': 'network_stream', 'stream_dropped_frames': 0})
    if simulated: v2.json_write(root/'session-provenance.json', {'kind': 'simulated'})
    v2.json_write(root/'run2-measurements.json', {'clock': 'session_elapsed_monotonic',
        'operator_stops': [{'time_seconds': .2}],
        'frames': [{'frame': i, 'age_seconds': .04, 'too_close': i == 2, 'target_identity': 'person-A'}
                   for i in range(4)]})
    return root


class RealSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_real_conversion_validates(self):
        session = fixture(self.root/'session', simulated=False)  # authored fixture shaped like a real input log
        out = self.root/'dataset'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rs.main(['to-control-dataset', str(session), '--output', str(out)]), 0)
        manifest, _ = cd.validate(out)
        for split in cd.SPLITS:
            for line in (out/f'samples-{split}.jsonl').read_text().splitlines():
                row = rs.v1.loads(line)
                self.assertEqual(row['provenance']['kind'], 'real')
                self.assertEqual(row['provenance'], manifest['episodes'][row['episode_id']]['provenance'])
                self.assertEqual(row['teacher_action']['linear'], .2 if row['step'] < 2 else 0)
                self.assertIsNone(row['safety']['final_gated_command'])
        self.assertIn('recorded software rule output', manifest['created_from']['teacher_labels'])

    def test_missing_teacher_and_timestamp_refused(self):
        for field in ('decision', 'time_seconds'):
            session = fixture(self.root/field)
            events = rs.read_lines(session/'events.jsonl')
            frame = next(e for e in events if e['event'] == 'frame')
            frame[field] = None
            (session/'events.jsonl').write_text(''.join(v2.canonical(e)+'\n' for e in events))
            with self.assertRaises(ValueError):
                rs.to_control_dataset(session, self.root/('out-'+field))
            self.assertFalse((self.root/('out-'+field)).exists())

    def test_unknown_provenance_override_refused(self):
        session = fixture(self.root/'session')
        (session/'session-provenance.json').write_text('{"kind":"real"}')
        with self.assertRaises(ValueError): rs.load_session(session)

    def test_simulated_sample_unchanged(self):
        out = self.root/'rebuilt'
        cd.build_sim(out, steps=4, seed=7)
        sample = Path(__file__).resolve().parents[1]/'p3/research/samples/control-dataset-sample'
        for path in sample.iterdir():
            self.assertEqual(path.read_bytes(), (out/path.name).read_bytes())
        cd.validate(sample)

    def test_converter_bad_input_exit(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            rs.main(['to-control-dataset', str(self.root/'missing'), '--output', str(self.root/'out')])
        self.assertEqual(cm.exception.code, 2)

    def test_actual_offline_recorder_bundle(self):
        # Existing fixture creates local synthetic pixels with an injected detector.
        from test_milestone2 import OfflineFixture
        recording = OfflineFixture('runTest')
        recording.setUp()
        self.addCleanup(recording.doCleanups)
        out = self.root/'bundle-export'
        rs.to_control_dataset(recording.bundle, out)
        manifest, _ = cd.validate(out)
        self.assertEqual(manifest['created_from']['provenance']['kind'], 'simulated')
        rows = [rs.v1.loads(line) for split in cd.SPLITS
                for line in (out/f'samples-{split}.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['observation']['frame_width'], 320)
        self.assertEqual(rows[0]['timestamp']['semantics'], 'processing_complete')
        self.assertIsNotNone(rows[0]['frame_ref'])
