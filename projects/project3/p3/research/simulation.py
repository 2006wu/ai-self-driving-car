"""Command replay only. No dynamics, hardware adapter, sockets or device imports."""
import math
from dataclasses import replace
from .controllers import Action
from ..geometry import target_distance


class SafetySupervisor:
    """Additional replay gate; cannot establish physical safety.

    Controller's legacy latch remains authoritative. Explicit replay rearm cannot
    clear a FollowController latch or fault. Emergency/fault/stale input relatches.
    """
    def __init__(self, too_close_distance_m=1., hfov_degrees=70., person_width_m=.5):
        """Non-latching distance stop, with no hysteresis.

        The default 1m lies between SimConfig's .65m pass threshold and
        1.785m desired distance, leaving margin for a .1s step at 1m/s.
        Horizontal image-edge clipping may underestimate box width, so it
        uses a conservative zero estimate, as do missing target boxes.
        Vertical clipping does not affect the width-based estimate.
        Distance is camera depth, not radial range.
        """
        for value in (too_close_distance_m, hfov_degrees, person_width_m):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('finite positive safety geometry required')
        if not 1 < hfov_degrees < 179:
            raise ValueError('invalid horizontal FOV')
        self.too_close_distance_m = too_close_distance_m
        self.hfov_degrees = hfov_degrees
        self.person_width_m = person_width_m
        self.too_close_stop_steps = 0
        self.latched = True
        self.faulted = False

    def _distance(self, observation):
        if observation is None:
            return None  # Compatibility with command-only replay callers.
        _, width = observation.frame_dimensions
        return target_distance(observation.tracks, observation.target_id, width,
                               self.hfov_degrees, self.person_width_m)

    def rearm(self):
        if not self.faulted: self.latched = False

    def apply(self, action, *, emergency_stop=False, fault=False, age_seconds=0., observation=None):
        valid = (isinstance(action, Action) and action.units == 'normalized_simulation'
                 and type(action.valid) is bool and action.valid
                 and all(type(v) in (int, float) and math.isfinite(v) for v in
                         (action.linear_velocity_command, action.angular_velocity_command))
                 and 0 <= action.linear_velocity_command <= .3 and abs(action.angular_velocity_command) <= .5
                 and (action.status == 'TRACKING' or
                      action.linear_velocity_command == action.angular_velocity_command == 0))
        self.faulted |= bool(fault) or not valid
        if emergency_stop or self.faulted or not math.isfinite(age_seconds) or not 0 <= age_seconds <= .5:
            self.latched = True
        if self.latched:
            return Action(0., 0., 'STOP', 'safety_supervisor', False,
                          metadata={'reason': 'replay_gate_latched', 'faulted': self.faulted})
        distance = self._distance(observation)
        if distance is not None and distance < self.too_close_distance_m:
            self.too_close_stop_steps += 1
            return replace(action, linear_velocity_command=0.,
                           metadata={**action.metadata, 'safety_stop': 'too_close',
                                     'estimated_distance_m': distance})
        return replace(action)


class CommandReplay:
    simulation_only = True

    def __init__(self):
        self.history = []

    def submit(self, action):
        if not isinstance(action, Action) or action.units != 'normalized_simulation':
            raise ValueError('normalized simulation action required')
        if not all(type(v) in (int, float) and math.isfinite(v) for v in
                   (action.linear_velocity_command, action.angular_velocity_command)):
            raise ValueError('finite command required')
        if not 0 <= action.linear_velocity_command <= .3 or abs(action.angular_velocity_command) > .5:
            raise ValueError('command outside simulation limits')
        if action.status != 'TRACKING' and (action.linear_velocity_command or action.angular_velocity_command):
            raise ValueError('motion requires TRACKING status')
        if not action.valid and (action.linear_velocity_command or action.angular_velocity_command):
            raise ValueError('invalid nonzero action')
        self.history.append(action)
        return action


class PhysicalRobotInterface:
    """Disabled boundary only; implementation and device calibration are BLOCKED."""
    def __init__(self):
        raise RuntimeError('Physical control is disabled; no adapter implemented')
