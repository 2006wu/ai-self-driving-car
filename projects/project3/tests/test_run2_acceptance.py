import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from p3.research import real_session as rs, run2_acceptance as ra, dataset_v2 as v2
from test_real_session import fixture


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.session = fixture(self.root/'session')

    def update(self, name, fn):
        path = self.session/name
        obj = rs.read_json(path)
        fn(obj)
        path.write_text(v2.canonical(obj)+'\n')

    def test_pass_report_and_cli(self):
        report, json = self.root/'report.md', self.root/'result.json'
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = ra.main([str(self.session), '--report', str(report), '--json', str(json)])
        self.assertEqual(code, 0)
        self.assertEqual(report.read_text(), output.getvalue())
        self.assertIn('Run2 acceptance — simulated', report.read_text())
        self.assertIn('NOT a hardware acceptance', report.read_text())
        self.assertEqual(rs.read_json(json)['overall'], 'PASS')
        self.assertTrue(all(x['status'] == 'PASS' for x in ra.evaluate(self.session)['items'].values()))

    def test_fail_slow_stop_and_drops(self):
        self.update('run2-measurements.json', lambda x: x['operator_stops'][0].update(time_seconds=0))
        self.update('run-status.json', lambda x: x.update(stream_dropped_frames=5))
        result = ra.evaluate(self.session)
        for name in ('stop_latency', 'frame_drops'):
            self.assertEqual(result['items'][name]['status'], 'FAIL')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ra.main([str(self.session)]), 1)

    def test_missing_measurements_never_pass(self):
        (self.session/'run2-measurements.json').unlink()
        (self.session/'run-status.json').unlink()
        result = ra.evaluate(self.session)
        self.assertTrue(all(x['status'] == 'NOT_MEASURED' for x in result['items'].values()))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ra.main([str(self.session)]), 1)

    def test_partial_age_coverage_and_no_close_events(self):
        self.update('run2-measurements.json', lambda x: x.update(frames=x['frames'][:1]))
        result = ra.evaluate(self.session)
        for name in ('stream_latency', 'too_close_stops', 'tracker_continuity'):
            self.assertEqual(result['items'][name]['status'], 'NOT_MEASURED')

    def test_too_close_violation_and_continuity(self):
        self.update('run2-measurements.json', lambda x: x['frames'][0].update(too_close=True))
        self.update('run.json', lambda x: x['frames'][1].update(tracks=[]))
        result = ra.evaluate(self.session)
        self.assertEqual(result['items']['too_close_stops']['status'], 'FAIL')
        self.assertEqual(result['items']['tracker_continuity']['status'], 'FAIL')

    def test_invalid_measurements_and_thresholds(self):
        for value in (-1, float('nan'), True):
            with self.assertRaises(ValueError): ra.Thresholds(max_stop_latency=value)
        self.update('run2-measurements.json', lambda x: x['frames'][0].update(age_seconds=-1))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            ra.main([str(self.session)])
        self.assertEqual(cm.exception.code, 2)

    def test_id_switch_for_same_person(self):
        def switch(run):
            run['frames'][1]['target'] = 2
            run['frames'][1]['tracks'][0]['id'] = 2
        self.update('run.json', switch)
        result = ra.evaluate(self.session)
        self.assertEqual(result['items']['tracker_continuity']['status'], 'FAIL')
        self.assertEqual(result['items']['tracker_continuity']['value']['id_switches'], 2)

    def test_stop_without_command_evidence_is_not_measured(self):
        events = [e for e in rs.read_lines(self.session/'events.jsonl') if e['event'] != 'simulated_control']
        (self.session/'events.jsonl').write_text(''.join(v2.canonical(e)+'\n' for e in events))
        self.assertEqual(ra.evaluate(self.session)['items']['stop_latency']['status'], 'NOT_MEASURED')

    def test_report_refuses_existing_path(self):
        report = self.root/'existing.md'
        report.write_text('preserve')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            ra.main([str(self.session), '--report', str(report)])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(report.read_text(), 'preserve')

    def test_module_exit_codes(self):
        for path, expected in ((self.session, 0), (self.root/'missing', 2)):
            proc = subprocess.run([sys.executable, '-m', 'p3.research.run2_acceptance', str(path)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, expected, proc.stderr)
        (self.session/'run2-measurements.json').unlink()
        proc = subprocess.run([sys.executable, '-m', 'p3.research.run2_acceptance', str(self.session)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
