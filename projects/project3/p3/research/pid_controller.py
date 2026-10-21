"""Opt-in normalized PID research controller; no physical control bindings."""
import json
import math
from dataclasses import asdict, dataclass, fields
from ..follow import FollowController
from .controllers import Action


@dataclass(frozen=True)
class PIDConfig:
    lateral_kp: float = .85
    lateral_ki: float = .06
    lateral_kd: float = .12
    longitudinal_kp: float = 6.
    longitudinal_ki: float = 1.
    longitudinal_kd: float = .1
    target_fraction: float = .2
    size_axis: str = 'width'
    lateral_deadband: float = .015
    longitudinal_deadband: float = .003
    integral_limit: float = .4
    derivative_tau: float = .15
    nominal_dt: float = .1
    speed_limit: float = .3
    turn_limit: float = .5
    speed_slew: float = 1.2  # normalized command / second
    turn_slew: float = 1.5

    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == 'size_axis':
                if value not in ('width', 'height'):
                    raise ValueError('size_axis must be width or height')
                continue
            if type(value) not in (float, int) or not 0 <= value <= 100:
                raise ValueError(f'{f.name} out of range')
        for name in ('target_fraction', 'nominal_dt', 'speed_limit', 'turn_limit', 'speed_slew', 'turn_slew'):
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} must be positive')
        if not (self.target_fraction <= 1 and self.nominal_dt <= 1 and
                self.speed_limit <= .3 and self.turn_limit <= .5 and
                self.lateral_deadband <= 1 and self.longitudinal_deadband <= 1):
            raise ValueError('fraction, dt or output limit out of range')

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_json(cls, path):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f'duplicate key: {key}')
                result[key] = value
            return result
        with open(path) as stream:
            data = json.load(stream, object_pairs_hook=unique)
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError('unknown configuration keys or invalid object')
        return cls(**data)


def clamp(value, low, high):
    return max(low, min(high, value))


class PIDAxis:
    """Derivative on measurement; conditional integration includes slew saturation.

    Integral stores error-seconds. A setpoint change never enters the derivative.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.integral = self.derivative = self.output = 0.
        self.measurement = None

    def step(self, measurement, target, dt, *, kp, ki, kd, deadband,
             integral_limit, tau, low, high, slew):
        error = target - measurement
        if abs(error) <= deadband:
            error = 0.
        raw_d = 0. if self.measurement is None else -(measurement - self.measurement) / dt
        alpha = dt / (tau + dt)
        self.derivative += alpha * (raw_d - self.derivative)
        self.measurement = measurement
        p, d = kp * error, kd * self.derivative
        candidate = clamp(self.integral + error * dt, -integral_limit, integral_limit)
        lower, upper = max(low, self.output - slew * dt), min(high, self.output + slew * dt)
        proposed = p + ki * candidate + d
        if not ((proposed > upper and error > 0) or (proposed < lower and error < 0)):
            self.integral = candidate
        i = ki * self.integral
        self.output = clamp(p + i + d, lower, upper)
        return self.output, {'p': p, 'i': i, 'd': d, 'error': error,
                             'integral': self.integral}


class PIDFollowController:
    def __init__(self, config=None, **policy):
        self.config = config or PIDConfig()
        if not isinstance(self.config, PIDConfig):
            raise ValueError('config must be PIDConfig')
        self.legacy = FollowController(**policy)
        self.lateral, self.longitudinal = PIDAxis(), PIDAxis()
        self.timestamp = None

    def _reset(self):
        self.lateral.reset()
        self.longitudinal.reset()
        self.timestamp = None

    @staticmethod
    def _action(output, speed=0., turn=0., **metadata):
        zero_terms = {'p': 0., 'i': 0., 'd': 0., 'error': 0., 'integral': 0.}
        return Action(float(speed), float(turn), output['state'], 'pid', True,
                      metadata={'legacy': dict(output), 'state': output['state'],
                                'reason': output['reason'],
                                'lateral': dict(zero_terms),
                                'longitudinal': dict(zero_terms), **metadata})

    def select(self, target_id, tracks):
        self._reset()
        try:
            return self._action(self.legacy.select(target_id, tracks))
        except (KeyError, TypeError, ValueError, OverflowError):
            return self.stop('invalid_tracking_data', fault=True)

    def cancel(self):
        self._reset()
        return self._action(self.legacy.cancel())

    def stop(self, reason='stop', fault=False):
        self._reset()
        return self._action(self.legacy.stop(reason, fault))

    def predict(self, observation):
        output = self.legacy.update(observation.tracks, observation.frame_dimensions,
                                    observation.age_seconds)
        if output['state'] != 'TRACKING':
            self._reset()
            return self._action(output)
        stamp = observation.timestamp_monotonic_seconds
        c = self.config
        dt = c.nominal_dt
        if stamp is not None:
            if type(stamp) not in (int, float) or not 0 <= stamp <= 1e308:
                return self.stop('invalid_timestamp')
            if self.timestamp is not None:
                dt = stamp - self.timestamp
                if not math.isfinite(dt) or dt < 0:
                    return self.stop('invalid_dt')
                if dt == 0:
                    dt = c.nominal_dt
                elif dt < 1e-9:
                    return self.stop('invalid_dt')  # avoid numerical derivative overflow
        self.timestamp = stamp
        track = next(t for t in observation.tracks if t['id'] == self.legacy.target)
        x1, y1, x2, y2 = track['box']
        h, w = observation.frame_dimensions[:2]
        offset = (x1 + x2 - w) / w
        fraction = (x2-x1)/w if c.size_axis == 'width' else (y2-y1)/h
        if not all(math.isfinite(v) for v in (offset, fraction)):
            return self.stop('invalid_pid_measurement', fault=True)
        common = dict(dt=dt, integral_limit=c.integral_limit, tau=c.derivative_tau)
        turn, lateral = self.lateral.step(offset, 0., kp=c.lateral_kp,
            ki=c.lateral_ki, kd=c.lateral_kd, deadband=c.lateral_deadband,
            low=-c.turn_limit, high=c.turn_limit, slew=c.turn_slew, **common)
        # A smaller box than the target requests forward motion.
        speed, longitudinal = self.longitudinal.step(fraction, c.target_fraction,
            kp=c.longitudinal_kp, ki=c.longitudinal_ki, kd=c.longitudinal_kd,
            deadband=c.longitudinal_deadband, low=0., high=c.speed_limit,
            slew=c.speed_slew, **common)
        if fraction >= c.target_fraction:
            speed = 0.  # Close stop overrides slew and accumulated integral.
            self.longitudinal.reset()
        return self._action(output, speed, turn, lateral=lateral,
                            longitudinal=longitudinal, dt=dt, size_fraction=fraction)
