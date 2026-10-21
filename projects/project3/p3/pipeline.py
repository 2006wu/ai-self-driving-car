"""Bounded file/camera input and overlay dashboard. No device-control output."""
import time
import json
import math
import psutil
from pathlib import Path

import cv2
import numpy as np
from .stream import StreamFrames
from .geometry import target_distance

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff'}
VIDEO_SUFFIXES = {'.mp4', '.mov', '.avi', '.mkv', '.hevc', '.m4v', '.webm'}
TOO_CLOSE_DISTANCE_M = 1.0  # Mirrors SafetySupervisor's default distance threshold.


class Frames:
    def __init__(self, source, camera=False):
        self.source, self.camera, self.cap = source, camera, None
        self.image = None
        self.fps = 0.0
        self.expected_frames = 0
        self.decoded = 0
        self.acquired_monotonic = None
        self.dropped_frames = 0  # No application replacement for sequential file/camera reads.

    def __enter__(self):
        try:
            return self._open()
        except BaseException:
            if self.cap is not None:
                self.cap.release()
            raise

    def _open(self):
        if self.camera:
            index = int(self.source)
            if index < 0:
                raise ValueError('camera index must be >= 0')
            self.cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        else:
            path = Path(self.source)
            if not path.is_file():
                raise FileNotFoundError(f'input missing: {path}')
            if path.suffix.lower() in IMAGE_SUFFIXES:
                self.image = cv2.imread(str(path))
                if self.image is None:
                    raise ValueError(f'image decode failed: {path}')
            elif path.suffix.lower() in VIDEO_SUFFIXES:
                self.cap = cv2.VideoCapture(str(path))
            else:
                raise ValueError(f'unsupported input format: {path.suffix}')
        if self.cap is not None:
            if not self.cap.isOpened():
                raise RuntimeError('input could not open; for camera check hardware/macOS permission')
            self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            if not self.camera:
                count = float(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.expected_frames = int(count) if math.isfinite(count) and count > 0 else 0
        return self

    def __iter__(self):
        if self.image is not None:
            self.acquired_monotonic = time.monotonic()
            yield self.image
            return
        while True:
            ok, frame = self.cap.read()
            if not ok:
                if self.camera:
                    raise RuntimeError('camera frame acquisition failed/disconnected')
                if self.expected_frames and self.decoded < self.expected_frames:
                    raise RuntimeError('video read failed before advertised EOF')
                break  # unknown-length files cannot distinguish decode failure from EOF
            if frame is None or not isinstance(frame, np.ndarray) or not frame.size:
                raise RuntimeError('empty camera/video frame')
            self.decoded += 1
            self.acquired_monotonic = time.monotonic()
            yield frame

    def __exit__(self, *_):
        if self.cap is not None:
            self.cap.release()


def render(image, detections, timing, tracks=(), target=None):
    frame = image.copy()
    for det in detections:
        x1, y1, x2, y2 = np.round(det['box']).astype(int)
        x2, y2 = min(x2, frame.shape[1]-1), min(y2, frame.shape[0]-1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        text = f"{det['label']} obj={det['objectness']:.2f}"
        label_width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, .45, 1)[0][0]
        label_x = max(0, min(x1, frame.shape[1]-label_width-2))
        cv2.putText(frame, text, (label_x, max(18, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, .45, (0,220,0), 1)
    for tr in tracks:
        x, y = np.round(tr['box'][:2]).astype(int)
        text = f"ID {tr['id']} {tr['state']}" + (' TARGET' if tr['id'] == target else '')
        label_width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, .45, 1)[0][0]
        x = max(0, min(x, frame.shape[1]-label_width-2))
        cv2.putText(frame, text, (x, min(frame.shape[0]-5, max(20,y+20))), cv2.FONT_HERSHEY_SIMPLEX, .45, (0,200,255), 1)
    persons = sum(d['label']=='person' for d in detections)
    inference = timing.get('inference_ms', 0)
    total = timing.get('previous_frame_e2e_ms', 0)
    lines = [f"PC local | persons={persons} target={target} ({timing.get('target_state', 'none')})",
             f'infer={inference:.1f}ms ({1000/inference if inference else 0:.1f}FPS) | ' +
             (f'prev process={total:.1f}ms ({1000/total:.1f}FPS)' if total else 'prev process=n/a'),
             'q:quit n:next c:cancel r:confirm s:snapshot | C2C NOT CONNECTED']
    if timing.get('follow'):
        d = timing['follow']
        lines.append(f"SIM ONLY {d['state']} {d['action']} v={d['speed']:.2f} turn={d['turn']:.2f}")
        lines.append('reason='+d['reason'])
    for i, line in enumerate(lines):
        cv2.rectangle(frame, (0, i*22), (min(frame.shape[1]-1, 800), i*22+22), (25,25,25), -1)
        cv2.putText(frame, line, (5,17+i*22), cv2.FONT_HERSHEY_SIMPLEX, .42, (255,255,255), 1)
    return frame


def run(detector, source, output, camera=False, max_frames=300, display=False, tracker=None,
        controller=None, target_id=None, max_seconds=None, record=True):
    """One existing detector pipeline, bounded capture, local simulation/event logs.

    Run deadline is checked between frames. StreamFrames additionally bounds
    acquisition waits. No vehicle API or robot binding exists here.
    """
    if max_frames < 1 or (max_seconds is not None and (not math.isfinite(max_seconds) or max_seconds <= 0)):
        raise ValueError('positive finite run limits required')
    if controller is not None and tracker is None:
        raise ValueError('follow simulation requires tracking')
    if target_id is not None and controller is None:
        raise ValueError('target-id requires follow simulation')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(f'output directory must be empty: {output}')
    records, writer, failure = [], None, None
    capture = None
    operator_stop_time = stop_recorded_time = None
    close_episode = False
    status, reason, screenshot_count = 'PASS', 'frame_limit', 0
    session_start, cpu_start = time.monotonic(), time.process_time()
    process = psutil.Process()
    journal = (output/'events.jsonl').open('x')
    def emit(kind, value):
        event = {'event': kind, 'time_seconds': time.monotonic()-session_start, **value}
        journal.write(json.dumps(event, allow_nan=False)+'\n')
        journal.flush()
        return event['time_seconds']
    try:
        if controller:
            emit('simulated_control', controller.output())
        if camera and str(source).startswith('stream:'):
            raise ValueError('--camera and stream: are mutually exclusive')
        capture = StreamFrames(source[7:]) if str(source).startswith('stream:') else Frames(source, camera)
        with capture as frames:
            iterator = iter(frames)
            for index in range(max_frames):
                if max_seconds is not None and time.monotonic()-session_start >= max_seconds:
                    reason = 'time_limit'
                    break
                start = time.monotonic()
                try:
                    image = next(iterator)
                except StopIteration:
                    reason = 'EOF'
                    break
                acquired = time.monotonic()
                receipt = frames.acquired_monotonic
                detections, timing = detector.predict(image)
                from .follow import valid_box
                if any(not valid_box(d.get('box'), image.shape[1], image.shape[0]) or
                       not math.isfinite(d.get('objectness', float('nan'))) or
                       not 0 <= d.get('objectness', -1) <= 1 for d in detections):
                    raise ValueError('invalid detector output')
                before_tracking = time.monotonic()
                tracks = tracker.update(detections) if tracker else []
                after_tracking = time.monotonic()
                selected_now = controller is not None and target_id is not None and index == 0
                decision = None
                if controller:
                    if selected_now:
                        tracker.select(target_id)
                        decision = controller.select(target_id, tracks)
                    else:
                        decision = controller.update(tracks, image.shape, time.monotonic()-start)
                    timing['follow'] = decision
                after_decision = time.monotonic()
                timing['target_state'] = tracker.target_state if tracker else 'disabled'
                timing['previous_frame_e2e_ms'] = records[-1]['timing']['e2e_ms'] if records else 0
                frame = render(image, detections, timing, tracks, tracker.target if tracker else None)
                key = -1
                if display:
                    cv2.imshow('Project3 | perception only', frame)
                    key = cv2.waitKey(1) & 0xff
                if key == ord('q'):
                    operator_stop_time = time.monotonic()-session_start
                    emit('operator_stop', {'time_seconds': operator_stop_time, 'source': 'keyboard'})
                    reason = 'user_quit'
                    if controller: decision = controller.stop(reason)
                elif key == ord('c'):
                    if tracker: tracker.cancel_target()
                    if controller: decision = controller.cancel()
                elif key == ord('n') and tracker:
                    chosen = tracker.select_next()
                    if controller: decision = controller.select(chosen, tracks)
                elif key == ord('r') and controller:
                    decision = controller.select(controller.target, tracks)
                selected = controller.target if controller else tracker.target if tracker else None
                too_close = (selected is not None and
                             any(t['id'] == selected and t['state'] == 'tracked' for t in tracks) and
                             target_distance(tracks, selected, image.shape[1]) < TOO_CLOSE_DISTANCE_M)
                if controller and too_close:
                    # Gate the output copy; preserve FollowController's selection/latch semantics.
                    decision = dict(decision, speed=0., safety_stop='too_close',
                                    action='STOP' if decision['turn'] == 0 else 'FOLLOW')
                decision_time = time.monotonic()
                if controller:
                    timing['follow'] = decision
                    command_time = emit('simulated_control', dict(decision, frame=index))
                    if too_close and not close_episode:
                        emit('safety_stop', {'time_seconds': command_time, 'frame': index, 'reason': 'too_close'})
                    if key in [ord('q'), ord('c'), ord('n'), ord('r')]:
                        frame = render(image, detections, timing, tracks, tracker.target)
                    elif too_close:
                        frame = render(image, detections, timing, tracks, tracker.target)
                close_episode = too_close
                rendered = time.monotonic()
                timing.update({'capture_ms': (acquired-start)*1000,
                               'tracking_ms': (after_tracking-before_tracking)*1000,
                               'decision_ms': (after_decision-after_tracking)*1000,
                               'render_gui_ms': (rendered-after_decision)*1000,
                               'e2e_ms': (rendered-start)*1000,
                               'rss_bytes': process.memory_info().rss})
                export_start = time.monotonic()
                if index == 0:
                    if not cv2.imwrite(str(output/'preview.png'), frame):
                        raise RuntimeError('preview write failed')
                if key == ord('s'):
                    path = output/f'screenshot-{index:06d}.png'
                    if not cv2.imwrite(str(path), frame): raise RuntimeError('screenshot write failed')
                    screenshot_count += 1
                    emit('screenshot', {'frame': index, 'file': path.name})
                if frames.image is None and record:
                    if writer is None:
                        fps = frames.fps if np.isfinite(frames.fps) and frames.fps > 0 else 20
                        writer = cv2.VideoWriter(str(output/'overlay.avi'), cv2.VideoWriter_fourcc(*'MJPG'), fps,
                                                 (frame.shape[1], frame.shape[0]))
                        if not writer.isOpened(): raise RuntimeError('video output could not open')
                    writer.write(frame)
                timing['export_ms'] = (time.monotonic()-export_start)*1000
                timing['loop_ms'] = (time.monotonic()-start)*1000
                row = {'frame': index, 'detections': detections, 'tracks': tracks,
                       'target': tracker.target if tracker else None, 'decision': decision, 'timing': timing,
                       'acquisition_time_seconds': receipt-session_start,
                       'age_at_decision_seconds': decision_time-receipt, 'too_close': too_close,
                       'stream_dropped_frames': frames.dropped_frames}
                records.append(row)
                emit('frame', {'frame': index, 'target': row['target'], 'target_state': timing['target_state'],
                               'decision': decision, 'timing': timing,
                               **{k: row[k] for k in ('acquisition_time_seconds', 'age_at_decision_seconds',
                                                     'too_close', 'stream_dropped_frames')}})
                if key == ord('q'): break
        if not records:
            raise ValueError('input yielded zero frames (empty/corrupt video)')
        return records
    except BaseException as error:
        if isinstance(error, KeyboardInterrupt):
            operator_stop_time = time.monotonic()-session_start
            emit('operator_stop', {'time_seconds': operator_stop_time, 'source': 'sigint'})
        status = 'INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'FAIL'
        reason = 'user_interrupt' if isinstance(error, KeyboardInterrupt) else type(error).__name__
        failure = str(error)
        emit('error', {'type': type(error).__name__, 'message': failure})
        raise
    finally:
        # Highest priority final observable output is always zero, including EOF/limits/errors.
        cleanup_errors = []
        if controller:
            final_stop = controller.stop(reason, fault=status=='FAIL')
            try:
                stop_recorded_time = emit('simulated_control', final_stop)
            except Exception as error: cleanup_errors.append('stop journal: '+str(error))
        if writer is not None:
            try: writer.release()
            except Exception as error: cleanup_errors.append(str(error))
        if display:
            try: cv2.destroyAllWindows()
            except Exception as error: cleanup_errors.append(str(error))
        elapsed = time.monotonic()-session_start
        summary = {'status': status if not cleanup_errors else 'FAIL', 'termination': reason,
                   'error': failure, 'cleanup_errors': cleanup_errors, 'frames': len(records),
                   'camera': camera, 'display': display, 'record': record, 'screenshots': screenshot_count,
                   'wall_seconds': elapsed, 'cpu_percent_one_core': 100*(time.process_time()-cpu_start)/elapsed,
                   'application_skipped_frames': 0, 'sensor_dropped_frames': None,
                   'stream_dropped_frames': 0,
                   'run2_logging': {'version': 1, 'clock': 'session_elapsed_monotonic'},
                   'operator_stop_time_seconds': operator_stop_time,
                   'stop_recorded_time_seconds': stop_recorded_time,
                   'frame_drop_scope': 'No application frame skipping; camera sensor drops unavailable.',
                   'simulation_only': controller is not None, 'physical_control': False,
                   'timing_scope': 'e2e excludes export IO; loop includes image/video export; wall also includes source opening/journal',
                   'deadline_scope': ('stream open/read caller deadlines; run limit checked between frames'
                                      if str(source).startswith('stream:') else
                                      'checked between frames; does not interrupt blocked native capture')}
        if str(source).startswith('stream:'):
            summary["input_kind"] = "network_stream"
            summary["application_skipped_frames"] = getattr(capture, "dropped_frames", 0)
            summary["stream_dropped_frames"] = summary["application_skipped_frames"]
            summary['frame_drop_scope'] = 'Latest-frame replacement count; upstream buffering/sensor drops unknown.'
        (output/'run-status.json').write_text(json.dumps(summary, indent=2, allow_nan=False))
        try:
            emit('session_end', summary)
        finally:
            journal.close()
        if cleanup_errors and failure is None: raise RuntimeError('cleanup failed: '+str(cleanup_errors))
