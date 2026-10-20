"""Command replay only. No dynamics, hardware adapter, sockets or device imports."""
import math
from dataclasses import replace
from .controllers import Action


class SafetySupervisor:
    """Additional replay gate; cannot establish physical safety.

    Controller's legacy latch remains authoritative. Explicit replay rearm cannot
    clear a FollowController latch or fault. Emergency/fault/stale input relatches.
    """
    def __init__(self):
        self.latched = True
        self.faulted = False

    def rearm(self):
        if not self.faulted: self.latched = False

    def apply(self, action, *, emergency_stop=False, fault=False, age_seconds=0.):
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
