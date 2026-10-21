"""Offline pipeline instrumentation; fake capture only, no camera/network."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from p3.follow import FollowController
from p3.geometry import target_distance
from p3.pipeline import run
from p3.stream import StreamFrames
from p3.tracking import Tracker
from p3.research import real_session as rs, run2_acceptance as ra
from test_real_session import fixture


class Detector:
    def __init__(self, widths=(40, 60, 90, 130, 130), interrupt=False):
        self.widths, self.index, self.interrupt = widths, 0, interrupt

    def predict(self, image):
        if self.interrupt and self.index == 2:
            raise KeyboardInterrupt()
        width = self.widths[min(self.index, len(self.widths)-1)]
        self.index += 1
        if width is None:
            return [], {}
        return [{'box': [160-width/2, 30, 160+width/2, 200],
                 'class_id': 0, 'label': 'person', 'objectness': .9}], {}


class Run2LoggingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.video = self.root/'synthetic.avi'
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*'MJPG'), 20, (320, 240))
        self.assertTrue(writer.isOpened())
        for _ in range(5): writer.write(np.zeros((240, 320, 3), np.uint8))
        writer.release()
        self.output = self.root/'offline-run'

    def run_pipeline(self, detector=None, **kwargs):
        return run(detector or Detector(), self.video, self.output, tracker=Tracker(),
                   controller=FollowController(), target_id=1, record=False, **kwargs)

    def events(self):
        return rs.read_lines(self.output/'events.jsonl')

    def check_stop(self, source):
        events = self.events()
        stops = [e for e in events if e['event'] == 'operator_stop']
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]['source'], source)
        index = events.index(stops[0])
        commands = [e for e in events[index+1:] if e['event'] == 'simulated_control']
        self.assertTrue(commands)
        self.assertEqual((commands[-1]['speed'], commands[-1]['turn']), (0, 0))
        summary = rs.read_json(self.output/'run-status.json')
        self.assertGreaterEqual(summary['stop_recorded_time_seconds'], stops[0]['time_seconds'])
        metric = ra.evaluate(self.output)['items']['stop_latency']
        self.assertEqual(metric['status'], 'PASS')
        self.assertEqual(metric['value']['events'], 1)
        self.assertLess(metric['value']['max_seconds'], .05)

    def test_video_measures_and_gates_close_episode(self):
        rows = self.run_pipeline()
        items = ra.evaluate(self.output)['items']
        for name in ('stream_latency', 'frame_drops', 'too_close_stops'):
            self.assertEqual(items[name]['status'], 'PASS', items[name])
        self.assertEqual(items['tracker_continuity']['status'], 'NOT_MEASURED')
        stops = [e for e in self.events() if e['event'] == 'safety_stop']
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]['frame'], 3)
        for row in rows:
            self.assertEqual(row['stream_dropped_frames'], 0)
            self.assertGreaterEqual(row['age_at_decision_seconds'], 0)
            if row['too_close']:
                self.assertEqual(row['decision']['speed'], 0)
                self.assertEqual(row['decision']['safety_stop'], 'too_close')
        # session_end alone carries the final counter and version metadata too.
        (self.output/'run-status.json').unlink()
        self.assertEqual(ra.evaluate(self.output)['items']['frame_drops']['status'], 'PASS')

    def test_zero_close_events_means_measured_coverage(self):
        self.run_pipeline(Detector(widths=(40,)))
        metric = ra.evaluate(self.output)['items']['too_close_stops']
        self.assertEqual(metric['status'], 'PASS')
        self.assertEqual(metric['value']['events'], 0)

    def test_disappearing_target_does_not_log_too_close(self):
        rows = run(Detector(widths=(40, None, None, None, None)), self.video, self.output,
                   tracker=Tracker(max_missed=1), controller=FollowController(),
                   target_id=1, record=False)
        self.assertEqual([row['timing']['target_state'] for row in rows],
                         ['tracked', 'missing', 'lost', 'lost', 'lost'])
        self.assertTrue(all(row['target'] == 1 for row in rows))
        self.assertTrue(all(row['too_close'] is False for row in rows))
        events = self.events()
        self.assertTrue(all(e['too_close'] is False for e in events if e['event'] == 'frame'))
        self.assertFalse(any(e['event'] == 'safety_stop' for e in events))
        metric = ra.evaluate(self.output)['items']['too_close_stops']
        self.assertEqual(metric['value']['events'], 0)

    def test_close_episodes_do_not_latch_the_controller(self):
        rows = self.run_pipeline(Detector(widths=(40, 130, 40, 130, 40)))
        self.assertEqual([e['frame'] for e in self.events() if e['event'] == 'safety_stop'], [1, 3])
        self.assertEqual(rows[2]['decision']['speed'], .3)
        self.assertEqual(rows[4]['decision']['speed'], .3)

    def test_sigint(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_pipeline(Detector(interrupt=True))
        self.check_stop('sigint')

    def test_keyboard_quit(self):
        with patch('p3.pipeline.cv2.imshow'), patch('p3.pipeline.cv2.waitKey', return_value=ord('q')), \
                patch('p3.pipeline.cv2.destroyAllWindows'):
            self.run_pipeline(display=True)
        self.check_stop('keyboard')

    def test_stream_receipt_and_replacements_without_blocking_close(self):
        drained, finish = threading.Event(), threading.Event()
        class Capture:
            count = 0
            def isOpened(self): return True
            def set(self, *_): pass
            def get(self, *_): return 20.
            def release(self): pass
            def read(self):
                self.count += 1
                if self.count > 3:
                    drained.set()
                    finish.wait(2)
                    return False, None
                return True, np.zeros((240, 320, 3), np.uint8)
        class ReadyStream(StreamFrames):
            def __enter__(self):
                super().__enter__()
                if not drained.wait(1): raise RuntimeError('fake capture stalled')
                return self
        source = ReadyStream('http://fake.invalid/', capture_factory=lambda *_: Capture())
        try:
            with patch('p3.pipeline.StreamFrames', return_value=source):
                rows = run(Detector(), 'stream:http://fake.invalid/', self.output, max_frames=1,
                           tracker=Tracker(), controller=FollowController(), target_id=1, record=False)
            started = time.monotonic()
            source.close()
            self.assertLess(time.monotonic()-started, .05)
            row = rows[0]
            self.assertEqual(source.acquired_monotonic, source.last_read)
            self.assertEqual(row['stream_dropped_frames'], 2)
            self.assertGreaterEqual(row['age_at_decision_seconds'], 0)
            self.assertLessEqual(row['acquisition_time_seconds'], self.events()[1]['time_seconds'])
            items = ra.evaluate(self.output)['items']
            self.assertEqual(items['stream_latency']['status'], 'PASS')
            self.assertEqual(items['frame_drops']['status'], 'FAIL')
        finally:
            finish.set()
            source.close()
            source.thread.join(1)

    def test_explicit_fields_override_and_preserve_journal_defaults(self):
        self.run_pipeline()
        (self.output/'run2-measurements.json').write_text(json.dumps({
            'clock': 'session_elapsed_monotonic', 'frames': [{'frame': 0, 'age_seconds': 2.}]}))
        session = rs.load_session(self.output)
        self.assertEqual(session['measurements']['frames'][0]['age_seconds'], 2.)
        self.assertIn('too_close', session['measurements']['frames'][0])
        self.assertEqual(ra.evaluate(self.output)['items']['stream_latency']['status'], 'FAIL')

    def test_legacy_fixture_unchanged(self):
        path = fixture(self.root/'legacy')
        before = ra.evaluate(path)
        self.assertTrue(all(item['status'] == 'PASS' for item in before['items'].values()))
        (path/'run2-measurements.json').unlink()
        (path/'run-status.json').unlink()
        # A legacy session_end must not newly provide measurements when status is absent.
        with (path/'events.jsonl').open('a') as journal:
            journal.write(json.dumps({'event': 'session_end', 'time_seconds': 1.,
                                      'stream_dropped_frames': 0})+'\n')
        self.assertTrue(all(item['status'] == 'NOT_MEASURED' for item in ra.evaluate(path)['items'].values()))

    def test_distance_side_clipping_and_missing_target(self):
        self.assertEqual(target_distance([{'id': 1, 'state': 'tracked', 'box': [0, 10, 40, 80]}], 1, 320), 0.)
        self.assertEqual(target_distance([], 1, 320), 0.)
