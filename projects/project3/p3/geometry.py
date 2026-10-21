"""Dependency-light box geometry shared by detection, tracking and evaluation."""
import math
import numpy as np


def target_distance(tracks, target_id, width, hfov_degrees=70., person_width_m=.5):
    """Width-based camera depth; missing or side-clipped targets yield zero.

    With no selection, conservatively consider all visible tracks (replay policy).
    """
    distances = []
    for track in tracks:
        if track.get('state') != 'tracked' or (target_id is not None and track.get('id') != target_id):
            continue
        x1, y1, x2, y2 = track['box']
        if (not all(math.isfinite(v) for v in (x1, y1, x2, y2))
                or x2 <= x1 or y2 <= y1 or x1 <= 0 or x2 >= width):
            distances.append(0.)
        else:
            focal = width/(2*math.tan(math.radians(hfov_degrees)/2))
            distances.append(person_width_m*focal/(x2-x1))
    return min(distances) if distances else 0.


def iou(box, boxes):
    boxes = np.asarray(boxes, dtype=float).reshape(-1, 4)
    intersection = np.maximum(0, np.minimum(box[2:], boxes[:, 2:]) - np.maximum(box[:2], boxes[:, :2])).prod(axis=1)
    area = np.maximum(0, np.asarray(box)[2:] - np.asarray(box)[:2]).prod()
    areas = np.maximum(0, boxes[:, 2:] - boxes[:, :2]).prod(axis=1)
    union = area + areas - intersection
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


def valid_box(box, width=None, height=None):
    try:
        x1, y1, x2, y2 = box
        if not all(math.isfinite(float(v)) for v in box) or x2 <= x1 or y2 <= y1:
            return False
        if width is not None and not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            return False
        return True
    except (TypeError, ValueError, OverflowError):
        return False

