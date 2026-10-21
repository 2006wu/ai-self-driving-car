"""Synthetic capture and localhost MJPEG checks; no camera or external network."""
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

try:
    import cv2
    import numpy as np
    from p3.stream import StreamFrames
except ImportError as error:
    cv2 = None
    IMPORT_ERROR = str(error)


@unittest.skipIf(cv2 is None, 'cv2/numpy unavailable: '+globals().get('IMPORT_ERROR', ''))
class StreamTests(unittest.TestCase):
    def fake(self, frames=(), opened=True, delay=0):
        class Capture:
            released = False
            def isOpened(self): return opened
            def get(self, _): return 15
            def read(self):
                time.sleep(delay)
                return next(self.frames, (False, None))
            def release(self): self.released = True
        cap = Capture()
        cap.frames = iter(frames)
        return cap

    def source(self, cap, **kwargs):
        return StreamFrames('http://127.0.0.1:1/', lambda *args: cap, **kwargs)

    def released(self, source, cap):
        source.thread.join(1)
        self.assertTrue(cap.released)

    def test_open_failure(self):
        cap = self.fake(opened=False)
        source = self.source(cap)
        with self.assertRaisesRegex(RuntimeError, 'open'):
            with source: pass
        self.released(source, cap)

    def test_open_timeout_late_cleanup(self):
        cap = self.fake()
        def factory(*args):
            time.sleep(.06)
            return cap
        source = StreamFrames('http://localhost/', factory, open_timeout=.01)
        with self.assertRaisesRegex(TimeoutError, 'open timeout'):
            with source: pass
        self.released(source, cap)
        with self.assertRaises(RuntimeError): source.__enter__()

    def test_stalled_read_latches(self):
        cap = self.fake([(True, np.zeros((4, 4, 3), np.uint8))], delay=.06)
        source = self.source(cap, stale_timeout=.01)
        with source:
            with self.assertRaises(TimeoutError): next(source)
            with self.assertRaisesRegex(RuntimeError, 'latched'): next(source)
        self.released(source, cap)

    def test_queued_frame_stale(self):
        self.check_latest(stale=True)

    def test_disconnect_and_cleanup(self):
        cap = self.fake([(True, np.zeros((4, 4, 3), np.uint8))])
        source = self.source(cap)
        with source:
            source.thread.join(1)
            with self.assertRaisesRegex(RuntimeError, 'disconnected'): next(source)
        self.released(source, cap)

    def test_invalid_frames(self):
        for frame in [None, np.array([]), np.zeros((2, 2)), np.zeros((2, 2, 4), np.uint8)]:
            with self.subTest(frame=repr(frame)):
                cap = self.fake([(True, frame)])
                source = self.source(cap)
                with source:
                    with self.assertRaisesRegex(RuntimeError, 'invalid stream frame'): next(source)
                self.released(source, cap)

    def test_consumer_error_cleanup(self):
        cap = self.fake()
        source = self.source(cap)
        with self.assertRaises(ValueError):
            with source: raise ValueError('consumer')
        self.released(source, cap)

    def test_pipeline_disconnect_final_stop(self):
        from p3.pipeline import run
        from p3.follow import FollowController
        cap = self.fake()
        source = self.source(cap)
        with tempfile.TemporaryDirectory() as folder, patch('p3.pipeline.StreamFrames', return_value=source):
            with self.assertRaisesRegex(RuntimeError, 'disconnected'):
                run(None, 'stream:http://localhost/', folder, tracker=object(), controller=FollowController())
            rows = [json.loads(line) for line in (Path(folder)/'events.jsonl').read_text().splitlines()]
            final = [r for r in rows if r['event'] == 'simulated_control'][-1]
            self.assertEqual((final['action'], final['speed'], final['turn']), ('STOP', 0, 0))
            summary = json.loads((Path(folder)/'run-status.json').read_text())
            self.assertEqual(summary['stream_dropped_frames'], 0)
            self.assertEqual(rows[-1]['stream_dropped_frames'], 0)
        self.released(source, cap)

    def check_latest(self, stale=False, disconnect=False):
        """Release a whole synthetic backlog while the consumer is paused."""
        ready, drain, drained, finish = (threading.Event() for _ in range(4))
        cap = self.fake()
        cap.index = 0
        settings = []
        cap.set = lambda key, value: settings.append((key, value))
        def read():
            if cap.index == 0:
                ready.set()
                if not drain.wait(2): raise RuntimeError('test gate timed out')
            if cap.index < 100:
                value = cap.index
                cap.index += 1
                return True, np.full((4, 4, 3), value, np.uint8)
            drained.set()
            if not finish.wait(2): raise RuntimeError('test gate timed out')
            return False, None
        cap.read = read
        source = self.source(cap, stale_timeout=.05)
        try:
            with source:
                self.assertTrue(ready.wait(1))
                drain.set()
                self.assertTrue(drained.wait(1))
                self.assertEqual(source.dropped_frames, 99)
                self.assertIn((cv2.CAP_PROP_BUFFERSIZE, 1), settings)
                if disconnect:
                    finish.set()
                    source.thread.join(1)
                    start = time.monotonic()
                    with self.assertRaisesRegex(RuntimeError, 'disconnected'): next(source)
                    self.assertLess(time.monotonic()-start, source.stale_timeout)
                elif stale:
                    # Advance only the acquisition clock; no scheduling-dependent sleep.
                    with patch('p3.stream.time.monotonic', return_value=source.last_read+.051):
                        with self.assertRaisesRegex(TimeoutError, 'stale'): next(source)
                else:
                    self.assertTrue((next(source) == 99).all())
                    # A consumed frame cannot be reused when no new data arrives.
                    start = time.monotonic()
                    with self.assertRaisesRegex(TimeoutError, 'stale'): next(source)
                    self.assertLess(time.monotonic()-start, .15)
                with self.assertRaisesRegex(RuntimeError, 'latched'): next(source)
        finally:
            drain.set()
            finish.set()
            self.released(source, cap)
        self.assertFalse(source.thread.is_alive())
        self.assertTrue(source.thread.daemon)

    def test_latest_only_and_stalled_source(self):
        self.check_latest()

    def test_backlog_disconnect_preempts_pending_frame(self):
        self.check_latest(disconnect=True)

    def test_helper_capture_and_output_rates(self):
        helper = Path(__file__).resolve().parents[1]/'tools/mac-webcam-stream.sh'
        # Docker's /tmp is noexec; executable stubs use the writable artifacts mount.
        with tempfile.TemporaryDirectory(dir=helper.parents[1]/'artifacts') as folder:
            root = Path(folder)
            for name, body in [('uname', 'echo Darwin'),
                               ('ffmpeg', 'printf "%s\\n" "$@"')]:
                path = root/name
                path.write_text('#!/bin/sh\n'+body+'\n')
                path.chmod(0o755)
            env = dict(os.environ, PATH=str(root)+':'+os.environ['PATH'])
            for rate in [None, '15', '30']:
                with self.subTest(rate=rate):
                    args = subprocess.check_output(
                        ['bash', str(helper)]+(['--fps', rate] if rate else []),
                        env=env, text=True).splitlines()
                    self.assertEqual(args[args.index('-framerate')+1], '30')
                    self.assertEqual(args[args.index('-r')+1], rate or '30')
                    self.assertLess(args.index('-framerate'), args.index('-i'))
                    self.assertGreater(args.index('-r'), args.index('-i'))
                    self.assertIn('-an', args)
                    self.assertEqual(args[-1], 'http://127.0.0.1:8081/')

    def test_loopback_mjpeg(self):
        if not cv2.videoio_registry.hasBackend(cv2.CAP_FFMPEG):
            self.skipTest('OpenCV FFMPEG backend unavailable')
        ok, jpeg = cv2.imencode('.jpg', np.full((48, 64, 3), 90, np.uint8))
        self.assertTrue(ok)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(jpeg)).encode()+b'\r\n\r\n'+jpeg.tobytes()+b'\r\n')
                        self.wfile.flush()
                        time.sleep(.03)
                    self.wfile.write(b'--frame--\r\n')
                except (BrokenPipeError, ConnectionResetError): pass
        try:
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        except PermissionError as error:
            self.skipTest(f'sandbox forbids localhost sockets: {error}')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with StreamFrames(f'http://127.0.0.1:{server.server_port}/', stale_timeout=2) as source:
                for _ in range(3):
                    self.assertEqual(next(source).shape, (48, 64, 3))
            source.thread.join(3)
            self.assertFalse(source.thread.is_alive())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)
