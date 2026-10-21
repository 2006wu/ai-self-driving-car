"""Fail-closed *simulation only*. Commands are dimensionless, never sent to hardware."""
import math
from .geometry import iou, valid_box


class FollowController:
    """Any loss/ambiguity latches STOP until explicit user selection/confirmation.

    An IoU ID is not identity: even reappearance of the same ID never auto-resumes.
    Width is an image-size proxy, not a metric distance estimate. No reverse motion.
    """
    def __init__(self, lost_after=5, overlap_stop=.15, max_age_seconds=.5):
        if isinstance(lost_after, bool) or not isinstance(lost_after, int) or lost_after < 0 or not 0 <= overlap_stop <= 1:
            raise ValueError('invalid follow policy')
        if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
            raise ValueError('invalid frame age limit')
        self.max_age_seconds = max_age_seconds
        self.lost_after, self.overlap_stop = lost_after, overlap_stop
        self.target = None
        self.state, self.reason, self.missed = 'IDLE', 'not_selected', 0
        self.latched, self.faulted = True, False

    def output(self, speed=0., turn=0.):
        return {'state': self.state, 'reason': self.reason, 'target_id': self.target,
                'action': 'STOP' if speed == turn == 0 else 'FOLLOW',
                'speed': float(speed), 'turn': float(turn), 'simulation_only': True}

    def stop(self, reason='stop', fault=False):
        self.latched = True
        self.faulted |= fault
        self.state, self.reason = 'STOP', reason
        return self.output()

    def cancel(self):
        self.target = None
        return self.stop('user_cancelled')

    def select(self, target_id, tracks):
        if self.faulted:
            return self.stop('fault_requires_new_session')
        if isinstance(target_id, bool) or not isinstance(target_id, int) or target_id <= 0:
            return self.stop('invalid_tracking_id')
        visible = [t for t in tracks if t.get('id') == target_id and t.get('state') == 'tracked']
        if len(visible) != 1 or not valid_box(visible[0].get('box')):
            return self.stop('target_not_visible')
        if any(t.get('state') == 'tracked' and t.get('id') != target_id and
               float(iou(visible[0]['box'], [t['box']])[0]) >= self.overlap_stop for t in tracks):
            self.target = target_id
            return self.stop('selection_ambiguous')
        self.target, self.missed, self.latched = target_id, 0, False
        self.state, self.reason = 'TARGET_SELECTED', 'explicit_selection'
        return self.output()

    def update(self, tracks, shape, age_seconds=0.):
        if not math.isfinite(age_seconds) or age_seconds < 0 or age_seconds > self.max_age_seconds:
            return self.stop('stale_or_invalid_frame_age')
        try:
            height, width = shape[:2]
            if width <= 0 or height <= 0:
                raise ValueError('invalid frame shape')
            ids = [t['id'] for t in tracks]
            if len(ids) != len(set(ids)) or any(isinstance(i, bool) or not isinstance(i, int) or i <= 0 for i in ids):
                raise ValueError('invalid_tracking_id')
            if any(not valid_box(t.get('box'), width, height) or t.get('state') not in {'tracked', 'missing'} for t in tracks):
                raise ValueError('invalid_track')
        except (KeyError, TypeError, ValueError):
            return self.stop('invalid_tracking_data', fault=True)
        if self.faulted:
            return self.stop('fault_requires_new_session')
        if self.target is None:
            return self.output()
        target = next((t for t in tracks if t['id'] == self.target and t['state'] == 'tracked'), None)
        if target is None:
            self.missed += 1
            self.latched = True
            self.state = 'TARGET_TEMPORARILY_LOST' if self.missed <= self.lost_after else 'TARGET_LOST'
            self.reason = 'target_not_visible'
            return self.output()
        visible = [t for t in tracks if t['state'] == 'tracked' and t['id'] != self.target]
        if any(float(iou(target['box'], [t['box']])[0]) >= self.overlap_stop for t in visible):
            return self.stop('overlapping_persons_reselect_required')
        if self.latched:
            return self.stop('explicit_confirmation_required')
        self.state, self.reason, self.missed = 'TRACKING', 'visible_unambiguous_target', 0
        x1, _, x2, _ = target['box']
        offset = ((x1+x2)/2-width/2)/(width/2)
        width_fraction = (x2-x1)/width
        # Heuristic simulation, not a vehicle calibration/controller.
        turn = max(-.5, min(.5, -offset*.5)) if abs(offset) > .1 else 0.
        speed = .3 if width_fraction < .2 and abs(offset) <= .1 else 0.
        return self.output(speed, turn)
