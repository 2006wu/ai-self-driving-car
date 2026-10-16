"""Explicit timing scopes and reproducible bounded file-input benchmarks."""
import platform
import time
from pathlib import Path
from importlib.metadata import version

import cv2
import numpy as np
import onnxruntime as ort
import psutil

from .detection import Detector, sha256
from .pipeline import Frames, render


def stats(values):
    a = np.asarray(values, dtype=float)
    if not len(a) or not np.isfinite(a).all():
        raise ValueError('statistics need nonempty finite observations')
    return {'mean': float(a.mean()), 'median': float(np.median(a)),
            'p95': float(np.percentile(a, 95)), 'std': float(a.std()), 'count': len(a)}


def environment():
    return {'python': platform.python_version(), 'machine': platform.machine(),
            'platform': platform.platform(), 'providers': ort.get_available_providers(),
            'packages': {name: version(name) for name in ['numpy','onnx','onnxruntime','opencv-python','psutil']},
            'camera': 'NOT TESTED: opt-in AVFoundation on macOS',
            'timing_clock': 'time.perf_counter monotonic seconds',
            'source_sha256': {str(p.relative_to(Path(__file__).parents[1])): sha256(p)
                              for p in Path(__file__).parent.glob('*.py')}}


def benchmark(source, samples=30, warmup=5, provider='CPUExecutionProvider', conf=.3, resolution=None,
              tracking=False, simulate_follow=False):
    if samples < 2 or warmup < 1:
        raise ValueError('benchmark requires samples >= 2 and warmup >= 1')
    if simulate_follow and not tracking:
        raise ValueError('follow simulation requires tracking')
    from .tracking import Tracker
    from .follow import FollowController
    tracker = Tracker() if tracking else None
    controller = FollowController() if simulate_follow else None
    detector = Detector(provider=provider, conf=conf)
    rows, confidences, counts, person_counts = [], [], [], []
    process = psutil.Process()
    rss_before = process.memory_info().rss
    with Frames(source) as frames:
        iterator = iter(frames)
        first = next(iterator, None)
        if first is None:
            raise ValueError('empty benchmark input')
        for _ in range(warmup):
            detector.predict(cv2.resize(first,resolution) if resolution else first)
        # Reopen video after warm-up so measured frames always start at index 0.
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    with Frames(source) as frames:
        iterator = iter(frames)
        for _ in range(samples):
            start = time.perf_counter()
            if frames.image is not None:
                # Repeated resident image; disk decode happened before loop.
                image = frames.image
            else:
                image = next(iterator, None)
                if image is None:
                    break
            if resolution:
                image = cv2.resize(image, resolution)
            acquired = time.perf_counter()
            detections, timing = detector.predict(image)
            tracking_start = time.perf_counter()
            tracks = tracker.update(detections) if tracker else []
            tracking_end = time.perf_counter()
            if controller:
                if controller.target is None and tracker.target is not None:
                    controller.select(tracker.target, tracks)
                timing['follow'] = controller.update(tracks, image.shape)
            decision_end = time.perf_counter()
            timing['target_state'] = tracker.target_state if tracker else 'disabled'
            render_start = time.perf_counter()
            rendered = render(image, detections, timing, tracks, tracker.target if tracker else None)
            assert rendered.shape == image.shape
            end = time.perf_counter()
            timing.update({'capture_or_resize_ms': (acquired-start)*1000,
                           'render_ms': (end-render_start)*1000,
                           'tracking_ms': (tracking_end-tracking_start)*1000,
                           'decision_ms': (decision_end-tracking_end)*1000,
                           'e2e_ms': (end-start)*1000,
                           'rss_bytes': process.memory_info().rss})
            rows.append(timing)
            counts.append(len(detections))
            person_counts.append(sum(d['class_id']==0 for d in detections))
            confidences.extend(d['objectness'] for d in detections)
    if len(rows) < 2:
        raise ValueError('fewer than two measured frames; benchmark not valid')
    summary = {key: stats([r[key] for r in rows]) for key in rows[0] if isinstance(rows[0][key], (int,float))}
    return {'environment': environment(), 'model': detector.info, 'input': str(Path(source).resolve()),
            'input_sha256': sha256(source), 'requested_samples': samples, 'warmup': warmup,
            'confidence_threshold': conf, 'source_resolution_override': resolution,
            'model_resolution': [640,416], 'metrics': summary, 'rss_before_measured_bytes': rss_before,
            'inference_fps': 1000/summary['inference_ms']['mean'],
            'file_pipeline_fps': 1000/summary['e2e_ms']['mean'],
            'tracking_enabled':tracking,'simulated_follow_enabled':simulate_follow,
            'cpu_percent_one_core':100*(time.process_time()-cpu_start)/(time.perf_counter()-wall_start),
            'application_skipped_frames':0,'camera_sensor_dropped_frames':None,
            'person_count':stats(person_counts),
            'detection_count': stats(counts),
            'objectness_distribution': stats(confidences) if confidences else None,
            'scope': ('Resident image retrieval' if Path(source).suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.webp','.tif','.tiff'} else 'Video decode') +
                     ' + optional source resize + preprocess + inference + postprocess + overlay rendering. ' +
                     ('Includes optional tracking and simulated decision when enabled. '
                      'Excludes model load, export IO, GUI display and camera capture. '
                      'CPU utilization covers measured file-loop wall time including source opening; per-frame E2E excludes opening.'),
            'memory_scope': 'Process RSS sampled after each measured frame; not device/GPU memory or continuous peak.',
            'accuracy': 'No labels: precision/recall/mAP NOT EVALUATED', 'observations': rows}
