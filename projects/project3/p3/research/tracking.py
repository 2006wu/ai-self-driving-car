"""Optional research trackers; baseline/default tracker is unchanged."""
from ..tracking import Tracker
from ..geometry import iou, valid_box
from ..tracking_eval import maximum_assignment


class HungarianTracker(Tracker):
    def update(self, detections):
        for d in detections:
            if not isinstance(d, dict) or not isinstance(d.get('class_id'), int) or not valid_box(d.get('box')):
                raise ValueError('invalid detection/box')
        people = [d for d in detections if d['class_id'] == 0]
        ids = sorted(self.tracks)
        bonus = min(len(ids), len(people)) + 1
        weights = []
        for tid in ids:
            overlaps = iou(self.tracks[tid]['box'], [p['box'] for p in people])
            weights.append([bonus+float(s) if s >= self.threshold else 0. for s in overlaps])
        pairs = maximum_assignment(weights)
        matched_ids, matched_people = set(), set()
        for i, j in pairs:
            tid = ids[i]
            self.tracks[tid].update(box=people[j]['box'], missed=0, state='tracked')
            matched_ids.add(tid)
            matched_people.add(j)
        for tid in list(self.tracks):
            if tid not in matched_ids:
                track = self.tracks[tid]
                track['missed'] += 1
                track['state'] = 'missing'
                if track['missed'] > self.max_missed:
                    del self.tracks[tid]
        for j, person in enumerate(people):
            if j not in matched_people:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {'id': tid, 'box': person['box'], 'missed': 0, 'state': 'tracked'}
        if self.auto_select and self.target is None and self.tracks:
            self.target = max(self.tracks, key=lambda k:
                              (self.tracks[k]['box'][2]-self.tracks[k]['box'][0]) *
                              (self.tracks[k]['box'][3]-self.tracks[k]['box'][1]))
        return [dict(t, box=list(t['box'])) for t in self.tracks.values()]


def create_tracker(method='greedy_iou', **kwargs):
    if method == 'greedy_iou':
        return Tracker(**kwargs)
    if method == 'hungarian':
        return HungarianTracker(**kwargs)
    if method == 'kalman_iou':
        from .motion_tracking import KalmanIoUTracker
        return KalmanIoUTracker(**kwargs)
    raise ValueError('unknown tracker method')
