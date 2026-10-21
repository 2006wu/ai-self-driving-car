"""Small IoU association baseline; track IDs are not person identities."""
from .geometry import iou, valid_box


class Tracker:
    def __init__(self, threshold=.3, max_missed=5):
        if not 0 <= threshold <= 1 or isinstance(max_missed, bool) or not isinstance(max_missed, int) or max_missed < 0:
            raise ValueError('invalid tracking threshold/age')
        self.threshold, self.max_missed = threshold, max_missed
        self.tracks, self.next_id, self.target = {}, 1, None
        self.auto_select = True

    def update(self, detections):
        # Validate before mutation; malformed boxes never enter matching/render/control.
        for d in detections:
            if not isinstance(d, dict) or not isinstance(d.get('class_id'), int) or not valid_box(d.get('box')):
                raise ValueError('invalid detection/box')
        people = [d for d in detections if d['class_id'] == 0]
        candidates = []
        for track_id, track in self.tracks.items():
            for index, person in enumerate(people):
                overlap = float(iou(track['box'], [person['box']])[0])
                if overlap >= self.threshold:
                    candidates.append((overlap, track_id, index))
        used_tracks, used_people = set(), set()
        # One-to-one greedy global highest IoU; deterministic tie break.
        for _, track_id, index in sorted(candidates, key=lambda r:(-r[0],r[1],r[2])):
            if track_id in used_tracks or index in used_people:
                continue
            self.tracks[track_id].update(box=people[index]['box'], missed=0, state='tracked')
            used_tracks.add(track_id);used_people.add(index)
        for track_id in list(self.tracks):
            if track_id not in used_tracks:
                track = self.tracks[track_id]
                track['missed'] += 1
                track['state'] = 'missing'
                if track['missed'] > self.max_missed:
                    del self.tracks[track_id]
        for index, person in enumerate(people):
            if index not in used_people:
                track_id = self.next_id
                self.next_id += 1
                self.tracks[track_id] = {'id':track_id, 'box':person['box'], 'missed':0, 'state':'tracked'}
        if self.auto_select and self.target is None and self.tracks:
            self.target = max(self.tracks, key=lambda k:
                              (self.tracks[k]['box'][2]-self.tracks[k]['box'][0]) *
                              (self.tracks[k]['box'][3]-self.tracks[k]['box'][1]))
        return [dict(t,box=list(t['box'])) for t in self.tracks.values()]

    @property
    def target_state(self):
        if self.target is None: return 'none'
        return self.tracks.get(self.target, {'state':'lost'})['state']

    def select_next(self):
        visible = sorted(k for k,t in self.tracks.items() if t['state']=='tracked')
        if visible:
            self.target = visible[(visible.index(self.target)+1)%len(visible)] if self.target in visible else visible[0]
        return self.target

    def cancel_target(self):
        self.target = None
        self.auto_select = False

    def select(self, target_id):
        if isinstance(target_id, bool) or not isinstance(target_id, int) or target_id not in self.tracks or self.tracks[target_id]['state'] != 'tracked':
            raise ValueError('selected track must be a visible positive integer ID')
        self.target = target_id
        return target_id
