"""YoloPC-compatible BGR/direct-resize/objectness/class-agnostic NMS baseline."""
import ast
import hashlib
import time
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort

from .geometry import iou

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / 'external/aJLL/bodyjim/yolov5n_flat.onnx'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def decode(raw, conf=0.3, threshold=0.45):
    """Preserve professor objectness filtering, ranking and class-agnostic NMS."""
    if not 0 <= conf <= 1 or not 0 <= threshold <= 1:
        raise ValueError('confidence and IoU thresholds must be in [0,1]')
    raw = np.asarray(raw)
    if raw.size != 16380 * 85 or not np.isfinite(raw).all():
        raise ValueError('expected finite flat YOLO output with 16380×85 values')
    predictions = raw.reshape(-1, 85)
    predictions = predictions[predictions[:, 4] > conf]
    if not len(predictions):
        return np.empty((0, 6), dtype=np.float32)
    boxes = predictions[:, :4].copy()
    boxes[:, :2] = predictions[:, :2] - predictions[:, 2:4] / 2
    boxes[:, 2:4] = predictions[:, :2] + predictions[:, 2:4] / 2
    order = predictions[:, 4].argsort().tolist()
    keep = []
    while order:
        index = order.pop()
        keep.append(index)
        if order:
            overlaps = iou(boxes[index], boxes[order])
            order = [value for j, value in enumerate(order) if overlaps[j] <= threshold]
    return np.column_stack((boxes[keep], predictions[keep, 4], predictions[keep, 5:].argmax(axis=1)))


def map_boxes(rows, width, height):
    """Rows use continuous xyxy coordinates; clip to image edges, not indices."""
    result = np.array(rows, dtype=float, copy=True).reshape(-1, 6)
    result[:, [0, 2]] = np.clip(result[:, [0, 2]] * width / 640, 0, width)
    result[:, [1, 3]] = np.clip(result[:, [1, 3]] * height / 416, 0, height)
    return result


class Detector:
    def __init__(self, model=MODEL, provider='CPUExecutionProvider', conf=0.3, threads=1):
        start = time.perf_counter()
        if not Path(model).is_file():
            raise FileNotFoundError(f'ONNX model missing: {model}; no automatic download')
        if provider not in ort.get_available_providers():
            raise ValueError(f'provider {provider} unavailable; found {ort.get_available_providers()}')
        if not 0 <= conf <= 1 or threads < 1:
            raise ValueError('confidence must be in [0,1] and threads >= 1')
        self.model = Path(model)
        proto = onnx.load(model)
        onnx.checker.check_model(proto)
        metadata = {item.key: item.value for item in proto.metadata_props}
        self.classes = ast.literal_eval(metadata['names'])
        if len(self.classes) != 80 or self.classes[0] != 'person':
            raise ValueError('expected 80 COCO class names')
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model), sess_options=options, providers=[provider])
        # ORT may append CPU fallback. Do not present this as pure GPU execution.
        if provider not in self.session.get_providers():
            raise RuntimeError(f'requested provider inactive: {self.session.get_providers()}')
        self.input = self.session.get_inputs()[0]
        if self.input.shape != [1, 3, 416, 640] or self.input.type != 'tensor(float)':
            raise ValueError(f'unsupported model input: {self.input.shape} {self.input.type}')
        if self.session.get_outputs()[0].shape != [1, 1392300]:
            raise ValueError('unsupported model output')
        self.conf = conf
        self.load_ms = (time.perf_counter() - start) * 1000
        self.info = {'model_sha256': sha256(model), 'input': self.input.shape,
                     'output': self.session.get_outputs()[0].shape,
                     'providers': self.session.get_providers(), 'requested_provider': provider,
                     'threads': threads, 'classes': self.classes, 'load_ms': self.load_ms}

    @staticmethod
    def preprocess(image):
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or not image.size:
            raise ValueError('expected nonempty uint8 BGR H×W×3 image')
        resized = cv2.resize(image, (640, 416))
        return np.ascontiguousarray(resized.transpose(2, 0, 1)[None], dtype=np.float32) / 255

    def predict(self, image):
        start = time.perf_counter()
        tensor = self.preprocess(image)
        pre = time.perf_counter()
        raw = self.session.run(None, {self.input.name: tensor})[0]
        infer = time.perf_counter()
        rows = decode(raw, self.conf)
        mapped = map_boxes(rows, image.shape[1], image.shape[0])
        detections = [{'box': row[:4].tolist(), 'objectness': float(row[4]),
                       'class_id': int(row[5]), 'label': self.classes[int(row[5])]} for row in mapped]
        end = time.perf_counter()
        return detections, {'preprocess_ms': (pre-start)*1000, 'inference_ms': (infer-pre)*1000,
                            'postprocess_ms': (end-infer)*1000}
