"""Simulation-only body command boundary, downstream of SafetySupervisor.

body_normalized units are uncalibrated, not metres/s or radians/s. This module
cannot establish that an Action passed a supervisor: callers must supply its
safe output. No real transport exists.
"""
import argparse
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import time

from .controllers import Action


@dataclass(frozen=True)
class BodyLimits:
    max_linear: float = 1.
    max_angular: float = 1.
    max_linear_accel: float = 1.
    max_angular_accel: float = 1.
    watchdog_timeout_s: float = .25

    def __post_init__(self):
        for name, value in asdict(self).items():
            if not _finite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and > 0')


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class BodyCommand:
    linear: float
    angular: float
    timestamp: float
    sequence: int
    source: str
    units: str = 'body_normalized'


class Transport(ABC):
    simulation_only = True

    @abstractmethod
    def send(self, command):
        """Record a BodyCommand; no physical transport is available."""


class MockTransport(Transport):
    def __init__(self):
        self.commands = []

    def send(self, command):
        self.commands.append(command)


class DryRunTransport(MockTransport):
    """In-memory recording only, identical to MockTransport."""


class RealTransport(Transport):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('No real transport exists; physical control is disabled')

    def send(self, command):
        raise NotImplementedError('No real transport exists')


def create_transport(kind='mock', *, simulation_only=True, allow_real=False):
    if kind == 'real':
        if simulation_only:
            raise ValueError('Real transport refused: simulation_only=True')
        if not allow_real:
            raise ValueError('Real transport refused: allow_real=False')
        return RealTransport()
    if kind == 'mock':
        return MockTransport()
    if kind == 'dry_run':
        return DryRunTransport()
    raise ValueError(f'unknown transport: {kind}')


def _slew(previous, target, acceleration, dt):
    # Decreasing magnitude is immediate. Reversals brake to zero first, then
    # accelerate in the opposite direction from zero within this tick's budget.
    if previous * target < 0:
        previous = 0.
    if abs(target) <= abs(previous):
        return target
    return math.copysign(min(abs(target), abs(previous) + acceleration * dt), target)


class BodyInterface:
    simulation_only = True

    def __init__(self, transport=None, limits=None, *, clock=time.monotonic,
                 simulation_only=True):
        if simulation_only is not True:
            raise ValueError('BodyInterface requires simulation_only=True')
        self.transport = transport if transport is not None else create_transport()
        if type(self.transport) not in (MockTransport, DryRunTransport):
            raise ValueError('Only in-memory mock/dry_run transports are supported')
        self.limits = limits or BodyLimits()
        self.clock = clock
        self.history = []
        self.faulted = False
        self.estop_latched = False
        self.estop_reason = None
        self._zero_received = False
        self._last_time = None
        self._fresh_time = None
        self._target = (0., 0.)
        self._source = 'none'
        self._input_reason = 'watchdog_zero'
        self._previous = (0., 0.)

    def _now(self, now):
        value = self.clock() if now is None else now
        if not _finite(value) or value < 0 or (self._last_time is not None and value < self._last_time):
            raise ValueError('finite nonnegative monotonic time required')
        return value

    def estop(self, reason, *, now=None):
        self.estop_latched = True
        self.estop_reason = str(reason)
        # A pre-latch zero is not sufficient to reset the latch.
        self._zero_received = False
        return self.tick(now=now)

    def reset_estop(self):
        if not self._zero_received:
            raise ValueError('reset refused: receive an explicit zero command first')
        self.estop_latched = False
        self.estop_reason = None

    def tick(self, action=None, *, now=None):
        """Emit on every tick. None means no new command (watchdog polling).

        First tick has dt=0; after a gap longer than the watchdog, acceleration
        restarts from zero with dt=0. Equal timestamps cannot add acceleration.
        Invalid/backwards clock values raise before sending any command.
        """
        now = self._now(now)
        dt = 0. if self._last_time is None else now - self._last_time
        gap = self._last_time is None or dt > self.limits.watchdog_timeout_s
        if gap:
            dt = 0.
            self._previous = (0., 0.)
        if action is not None:
            self._fresh_time = now
            self._zero_received = False
            self._target = (0., 0.)
            self._input_reason = 'invalid_input'
            self._source = 'invalid'
            if (isinstance(action, Action) and action.units == 'normalized_simulation'
                    and type(action.valid) is bool
                    and isinstance(action.source_controller, str)
                    and isinstance(action.status, str)
                    and _finite(action.linear_velocity_command)
                    and _finite(action.angular_velocity_command)):
                self._source = action.source_controller
                values = (action.linear_velocity_command, action.angular_velocity_command)
                self._zero_received = values == (0., 0.)
                if action.status != 'TRACKING':
                    self._input_reason = 'supervisor_stop' if self._zero_received else 'invalid_input'
                elif not action.valid:
                    self._input_reason = 'invalid_input'
                else:
                    # Clamp before scaling to avoid overflow from huge finite input.
                    v, w = max(0., min(.3, values[0])), max(-.5, min(.5, values[1]))
                    self._target = (v / .3 * self.limits.max_linear,
                                    w / .5 * self.limits.max_angular)
                    self._input_reason = 'clamped' if (v, w) != values else 'ok'
            if self._input_reason == 'invalid_input':
                self.faulted = True
                self._zero_received = False
        reasons = []
        if self.estop_latched:
            target = (0., 0.)
            reasons.append('estop_latched')
        elif self._fresh_time is None or now - self._fresh_time > self.limits.watchdog_timeout_s:
            target = (0., 0.)
            reasons.append('watchdog_zero')
        else:
            target = self._target
            reasons.append(self._input_reason)
        # Safety zeros bypass slew limiting. _slew also permits per-axis braking.
        output = tuple(_slew(p, t, a, dt) for p, t, a in zip(
            self._previous, target, (self.limits.max_linear_accel, self.limits.max_angular_accel)))
        if output != target:
            if reasons == ['ok']:
                reasons = []
            reasons.append('rate_limited')
        command = BodyCommand(*output, now, len(self.history), self._source)
        self.transport.send(command)
        self.history.append({**asdict(command), 'reasons': reasons,
                             'faulted': self.faulted, 'estop_reason': self.estop_reason})
        self._previous, self._last_time = output, now
        return command


def _summary(interface, kind):
    rows = interface.history
    deltas = [(abs(b['linear'] - a['linear']), abs(b['angular'] - a['angular']))
              for a, b in zip(rows, rows[1:])]
    return {'simulation_only': True, 'transport': kind, 'units': 'body_normalized',
            'calibration': 'uncalibrated', 'scope': 'offline simulation',
            'command_count': len(rows),
            'counts_per_reason': dict(Counter(r for row in rows for r in row['reasons'])),
            'max_abs_delta_per_tick': {'linear': max((d[0] for d in deltas), default=0.),
                                       'angular': max((d[1] for d in deltas), default=0.)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    sim = sub.add_parser('replay-sim')
    sim.add_argument('--scenario', default='too_close')
    sim.add_argument('--controller', choices=('pid', 'rule'), default='pid')
    sim.add_argument('--steps', type=int, default=100)
    log = sub.add_parser('replay-log')
    log.add_argument('file', type=Path)
    for child in (sim, log):
        child.add_argument('--output', type=Path, required=True)
        child.add_argument('--transport', choices=('mock', 'dry_run', 'real'), default='mock')
    args = parser.parse_args(argv)
    try:
        interface = BodyInterface(create_transport(args.transport))
        if args.output.exists():
            raise ValueError(f'output already exists: {args.output}')
        if args.mode == 'replay-sim':
            from .closed_loop import run_scenario
            from .controllers import RuleBasedController
            from .pid_controller import PIDFollowController
            controller = PIDFollowController() if args.controller == 'pid' else RuleBasedController()
            run_scenario(controller, args.scenario, args.steps,
                         on_step=lambda step, obs, proposed, safe, *rest: interface.tick(
                             safe, now=obs.timestamp_monotonic_seconds))
        else:
            # Recorded proposals pass through a new supervisor, never directly
            # into the interface. No log record can automatically rearm a latch.
            from .simulation import SafetySupervisor
            supervisor = SafetySupervisor()
            supervisor.rearm()
            with args.file.open() as stream:
                for line in stream:
                    row = json.loads(line)
                    action = Action(**row['action'])
                    safe = supervisor.apply(action, emergency_stop=action.status != 'TRACKING')
                    interface.tick(safe, now=row['timestamp'])
        result = _summary(interface, args.transport)
        args.output.mkdir(parents=True)
        with (args.output / 'commands.jsonl').open('x') as stream:
            for row in interface.history:
                stream.write(json.dumps(row, allow_nan=False, sort_keys=True) + '\n')
        with (args.output / 'summary.json').open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False, sort_keys=True)
            stream.write('\n')
    except (ValueError, TypeError, OSError, KeyError, NotImplementedError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    main()
