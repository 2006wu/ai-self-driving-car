"""Opt-in, fail-closed OpenCV network capture; never reconnects."""
import math
import queue
import threading
import time
from urllib.parse import urlsplit

import cv2
import numpy as np


class StreamFrames:
    """Worker owns capture, including release; native FFmpeg deadlines plus caller deadlines.

    Age measures local acquisition, not sensor time (MJPEG has no trusted timestamp).
    A backend ignoring native timeouts may retain its worker until it returns, but
    cannot delay STOP or deliver another frame after the caller deadline.
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
        self.opened = queue.Queue(maxsize=1)
        self.frames = queue.Queue(maxsize=1)
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
            self.fps = float(cap.get(cv2.CAP_PROP_FPS))
            self._worker_opened = True
            self.opened.put(None)
            while not self.closed.is_set():
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError('stream disconnected')
                if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
                        frame.ndim != 3 or frame.shape[2] != 3 or not frame.size):
                    raise RuntimeError('invalid stream frame; expected nonempty uint8 BGR')
                item = (time.monotonic(), frame)
                while not self.closed.is_set():
                    try:
                        self.frames.put(item, timeout=.01)
                        break
                    except queue.Full:
                        pass
        except BaseException as error:
            target = self.frames if getattr(self, '_worker_opened', False) else self.opened
            while not self.closed.is_set():
                try:
                    target.put(error, timeout=.01)
                    break
                except queue.Full:
                    pass
        finally:
            if cap is not None:
                cap.release()

    def __enter__(self):
        if self.stopped or self.thread is not None:
            raise RuntimeError('stream stopped; create a new session explicitly')
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        try:
            result = self.opened.get(timeout=self.open_timeout)
            if isinstance(result, BaseException):
                raise result
            return self
        except queue.Empty:
            self.close()
            raise TimeoutError('stream open timeout') from None
        except BaseException:
            self.close()
            raise

    def __iter__(self):
        return self

    def __next__(self):
        if self.stopped:
            raise RuntimeError('stream STOP latched; new session required')
        try:
            item = self.frames.get(timeout=self.stale_timeout)
            if isinstance(item, BaseException):
                raise item
            acquired, frame = item
            if time.monotonic()-acquired > self.stale_timeout:
                raise TimeoutError('stale stream frame')
            return frame
        except queue.Empty:
            self.close()
            raise TimeoutError('stale stream: frame acquisition timeout') from None
        except BaseException:
            self.close()
            raise

    def close(self):
        self.stopped = True
        self.closed.set()
        if self.thread is not None:
            self.thread.join(timeout=.02)

    def __exit__(self, *_):
        self.close()
