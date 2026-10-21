"""Opt-in constant-velocity box tracking; IDs are never person identities."""
import math
import numpy as np

from ..geometry import iou, valid_box
from ..tracking import Tracker
from ..tracking_eval import maximum_assignment


def measurement(box):
    x1, y1, x2, y2 = box
    return np.array([(x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1], dtype=float)


def predicted_box(mean):
    center, size = mean[:2], np.maximum(mean[2:4], 1e-6)
    return np.concatenate((center-size/2, center+size/2)).tolist()


class KalmanIoUTracker(Tracker):
    """One frame per step, with optional missed-track center-distance recovery.

    Distance is normalized by the predicted box diagonal; None disables fallback.
    Unmatched predictions remain missing, including when selected as the target.
    """
    def __init__(self, threshold=.3, max_missed=5, center_distance_gate=1.5):
        super().__init__(threshold, max_missed)
        if center_distance_gate is not None and (not math.isfinite(center_distance_gate) or center_distance_gate < 0):
            raise ValueError('invalid center distance gate')
        self.center_distance_gate = center_distance_gate
        self.filters = {}
        self.transition = np.eye(8)
        self.transition[:4, 4:] = np.eye(4)

    def update(self, detections):
        for d in detections:
            if not isinstance(d, dict) or not isinstance(d.get('class_id'), int) or not valid_box(d.get('box')):
                raise ValueError('invalid detection/box')
        people = [d for d in detections if d['class_id'] == 0]
        ids = sorted(self.tracks)
        weights = []
        bonus = min(len(ids), len(people))+1
        for tid in ids:
            mean, covariance = self.filters[tid]
            mean = self.transition @ mean
            covariance = self.transition @ covariance @ self.transition.T + np.eye(8)*.1
            self.filters[tid] = mean, covariance
            box = predicted_box(mean)
            self.tracks[tid]['box'] = box
            row = []
            for person in people:
                overlap = float(iou(box, [person['box']])[0])
                distance = np.linalg.norm(measurement(person['box'])[:2]-mean[:2]) / np.linalg.norm(np.maximum(mean[2:4], 1e-6))
                fallback = (self.tracks[tid]['missed'] > 0 and self.center_distance_gate is not None and distance <= self.center_distance_gate)
                row.append(bonus+overlap if overlap >= self.threshold else (bonus+.001/(1+distance) if fallback else 0.))
            weights.append(row)
        matched_ids, matched_people = set(), set()
        for i, j in maximum_assignment(weights):
            tid = ids[i]
            mean, covariance = self.filters[tid]
            gain = np.linalg.solve(covariance[:4, :4]+np.eye(4), covariance[:4, :]).T
            mean = mean + gain @ (measurement(people[j]['box'])-mean[:4])
            covariance = covariance - gain @ covariance[:4, :]
            self.filters[tid] = mean, covariance
            self.tracks[tid].update(box=list(people[j]['box']), missed=0, state='tracked')
            matched_ids.add(tid)
            matched_people.add(j)
        for tid in ids:
            if tid not in matched_ids:
                track = self.tracks[tid]
                track['missed'] += 1
                track['state'] = 'missing'
                if track['missed'] > self.max_missed:
                    del self.tracks[tid]
                    del self.filters[tid]
        for j, person in enumerate(people):
            if j not in matched_people:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = dict(id=tid, box=list(person['box']), missed=0, state='tracked')
                self.filters[tid] = np.concatenate((measurement(person['box']), np.zeros(4))), np.diag([1.]*4+[100.]*4)
        if self.auto_select and self.target is None and self.tracks:
            self.target = max(self.tracks, key=lambda k:
                              (self.tracks[k]['box'][2]-self.tracks[k]['box'][0]) *
                              (self.tracks[k]['box'][3]-self.tracks[k]['box'][1]))
        return [dict(t, box=list(t['box'])) for t in self.tracks.values()]
