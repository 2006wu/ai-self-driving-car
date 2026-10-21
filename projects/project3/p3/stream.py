"""Opt-in latest-frame network capture; fail closed and never reconnect."""
import math
import threading
import time
from urllib.parse import urlsplit

import cv2
import numpy as np


class StreamFrames:
    """Continuously drain capture; retain at most one unconsumed frame.

    Acquisition age is local, not sensor time. Native reads have deadlines;
    a backend ignoring them may outlive close until its daemon worker returns.
    """
    image = None
    fps = 0.0

    def __init__(self, url, capture_factory=None, open_timeout=3., stale_timeout=.5):
        if urlsplit(url).scheme not in {'http', 'https', 'tcp', 'rtsp'} or not urlsplit(url).hostname:
            raise ValueError('stream requires an http(s), tcp or rtsp URL')
        if any(not math.isfinite(x) or x <= 0 for x in (open_timeout, stale_timeout)):
            raise ValueError('stream timeouts must be positive and finite')
        self.url, self.factory = url, capture_factory or cv2.VideoCapture
        self.open_timeout, self.stale_timeout = open_timeout, stale_timeout
        self.closed = threading.Event()
        self.condition = threading.Condition()
        self.opened = False
        self.error = None
        self.latest = None
        self.last_read = None
        self.dropped_frames = 0
        self.thread = None
        self.stopped = False

    def _worker(self):
        cap = None
        try:
            cap = self.factory(self.url, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, max(1, int(self.open_timeout*1000)),
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, max(1, int(self.stale_timeout*1000))])
            if not cap.isOpened():
                raise RuntimeError('stream could not open')
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except (AttributeError, cv2.error):
                pass  # Some backends do not implement buffer sizing.
            with self.condition:
                self.fps = float(cap.get(cv2.CAP_PROP_FPS))
                self.opened = True
                self.last_read = time.monotonic()
                self.condition.notify_all()
            while not self.closed.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError('stream disconnected')
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
                        frame.ndim != 3 or frame.shape[2] != 3 or not frame.size):
                    raise RuntimeError('invalid stream frame; expected nonempty uint8 BGR')
                with self.condition:
                    if self.closed.is_set():
                        break
                    if self.latest is not None:
                        self.dropped_frames += 1
                    self.latest = frame
                    self.last_read = time.monotonic()
                    self.condition.notify_all()
        except BaseException as error:
            with self.condition:
                self.error = error
                self.latest = None  # A disconnect takes priority over buffered imagery.
                self.condition.notify_all()
        finally:
            if cap is not None:
                cap.release()

    def __enter__(self):
        if self.stopped or self.thread is not None:
            raise RuntimeError('stream stopped; create a new session explicitly')
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + self.open_timeout
        try:
            with self.condition:
                while not self.opened and self.error is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('stream open timeout')
                    self.condition.wait(remaining)
                if not self.opened and self.error is not None:
                    raise self.error
            return self
        except BaseException:
            self.close()
            raise

    def __iter__(self):
        return self

    def __next__(self):
        if self.stopped:
            raise RuntimeError('stream STOP latched; new session required')
        try:
            with self.condition:
                while True:
                    if self.closed.is_set():
                        raise RuntimeError('stream STOP latched; new session required')
                    if self.error is not None:
                        raise self.error
                    remaining = self.stale_timeout - (time.monotonic() - self.last_read)
                    if remaining <= 0:
                        raise TimeoutError('stale stream: frame acquisition timeout')
                    if self.latest is not None:
                        frame, self.latest = self.latest, None
                        return frame
                    self.condition.wait(remaining)
        except BaseException:
            self.close()
            raise

    def close(self):
        self.stopped = True
        self.closed.set()
        with self.condition:
            self.latest = None
            self.condition.notify_all()
        if self.thread is not None:
            self.thread.join(timeout=.02)

    def __exit__(self, *_):
        self.close()
