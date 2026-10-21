"""Synthetic pinhole/unicycle experiments, never vehicle acceptance.

World x is forward, y is left. Positive heading/turn is CCW; image x is right.
speed=.3 maps to max_linear m/s; turn=.5 maps to max_angular rad/s.
"""
import math
from dataclasses import asdict, dataclass
from .controllers import Observation
from .simulation import SafetySupervisor, CommandReplay

SCENARIOS = ('straight_walk', 'turn', 'stop_go', 'lateral_step', 'occlusion', 'too_close')


@dataclass(frozen=True)
class SimConfig:
    dt: float = .1
    image_width: int = 640
    image_height: int = 480
    hfov_degrees: float = 70.
    person_height: float = 1.7
    person_width: float = .5
    max_linear: float = 1.
    max_angular: float = 1.5
    desired_distance: float = 1.7851850084276433
    safety_distance: float = .65
    occlusion_start: int = 40
    occlusion_steps: int = 10

    def __post_init__(self):
        for key, value in asdict(self).items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'invalid simulation parameter: {key}')
        if not 1 < self.hfov_degrees < 179 or self.safety_distance >= self.desired_distance:
            raise ValueError('invalid FOV or distance')
        for key in ('image_width', 'image_height', 'occlusion_start', 'occlusion_steps'):
            if type(getattr(self, key)) is not int:
                raise ValueError(f'{key} must be integer')

    def to_dict(self):
        return asdict(self)


def person_position(scenario, t):
    """Authored trajectories. No collision clamp or hidden emergency brake.

    Occlusion has no automatic reselection. too_close approaches to .9m then
    stops, outside the .65m threshold. There is no person/robot collision solver.
    """
    if scenario == 'too_close':
        return max(.9, 1.3-.08*t), 0.
    x, y = 3.2+.35*t, -.75
    if scenario == 'turn':
        y += .5*math.sin(.3*t)
    elif scenario == 'stop_go':
        x = 3.2+.35*(min(t, 4.)+max(0., t-8.))
    elif scenario == 'lateral_step':
        y += .6*min(1., max(0., (t-5.)/.8))
    return x, y


def render_person(robot, person, config):
    """Clipped pixel boxes; centre behind/outside horizontal FOV is invisible."""
    x, y, heading = robot
    dx, dy = person[0]-x, person[1]-y
    depth = math.cos(heading)*dx+math.sin(heading)*dy
    left = -math.sin(heading)*dx+math.cos(heading)*dy
    half = math.radians(config.hfov_degrees)/2
    if depth <= 0 or abs(math.atan2(left, depth)) > half:
        return []
    w, h = config.image_width, config.image_height
    focal = w/(2*math.tan(half))
    cx = w/2-focal*left/depth
    bw, bh = focal*config.person_width/depth, focal*config.person_height/depth
    return [{'id': 1, 'state': 'tracked', 'box': [max(0., cx-bw/2),
            max(0., h/2-bh/2), min(float(w), cx+bw/2), min(float(h), h/2+bh/2)]}]


def _rms(values):
    return math.sqrt(sum(v*v for v in values)/len(values)) if values else None


def run_scenario(controller, scenario, steps=200, config=None, seed=None,
                 operator_reselect_steps=(), on_step=None):
    """Select once at start. Optional step numbers explicitly model operator r.

    Settled: both errors stay within .05 offset/.2m through end of run.
    Lateral overshoot: metres crossing past initial bearing's side.
    Distance overshoot: metres closer than desired distance.
    Seed is recorded; current experiment contains no randomness.
    """
    if scenario not in SCENARIOS or type(steps) is not int or steps <= 0:
        raise ValueError('invalid scenario or steps')
    if seed is not None and type(seed) is not int:
        raise ValueError('seed must be integer or None')
    if any(type(i) is not int or not 0 <= i < steps for i in operator_reselect_steps):
        raise ValueError('invalid operator reselect step')
    c = config or SimConfig()
    robot = [0., 0., 0.]
    gate = SafetySupervisor(hfov_degrees=c.hfov_degrees, person_width_m=c.person_width)
    replay = CommandReplay()
    controller.select(1, render_person(robot, person_position(scenario, 0.), c))
    gate.rearm()  # UI r uses select(current_id, tracks); no weakened legacy latch.
    offsets, errors, distances, cross_track, settled, rows = [], [], [], [], [], []
    tracking = lost = stops = latched = faults = 0
    for step in range(steps):
        t = step*c.dt
        person = person_position(scenario, t)
        tracks = render_person(robot, person, c)
        if scenario == 'occlusion' and c.occlusion_start <= step < c.occlusion_start+c.occlusion_steps:
            tracks = []
        if step in operator_reselect_steps:
            controller.select(1, tracks)
            gate.rearm()
        observation = Observation(t, tracks, (c.image_height, c.image_width), 0., target_id=1)
        proposed = controller.predict(observation)
        # Mirror the authoritative legacy STOP into the independent replay latch.
        safe = gate.apply(proposed, emergency_stop=proposed.status != 'TRACKING',
                          age_seconds=0., observation=observation)
        replay.submit(safe)
        v = safe.linear_velocity_command/.3*c.max_linear
        omega = safe.angular_velocity_command/.5*c.max_angular
        distance = math.hypot(person[0]-robot[0], person[1]-robot[1])
        left = -math.sin(robot[2])*(person[0]-robot[0])+math.cos(robot[2])*(person[1]-robot[1])
        offset = None if not tracks else (tracks[0]['box'][0]+tracks[0]['box'][2]-c.image_width)/c.image_width
        if offset is not None:
            offsets.append(offset)
        errors.append(distance-c.desired_distance)
        distances.append(distance)
        cross_track.append(left)
        settled.append(offset is not None and abs(offset) <= .05 and abs(errors[-1]) <= .2)
        tracking += proposed.status == 'TRACKING'
        lost += proposed.status in ('TARGET_TEMPORARILY_LOST', 'TARGET_LOST')
        stops += proposed.status != 'TRACKING'
        latched += gate.latched or controller.legacy.latched
        faults += gate.faulted
        rows.append([safe.linear_velocity_command, safe.angular_velocity_command])
        if on_step is not None:
            on_step(step, observation, proposed, safe, gate.latched, gate.faulted,
                    {'distance_m': distance,
                     'bearing_rad': math.atan2(left, math.cos(robot[2])*(person[0]-robot[0])
                                               + math.sin(robot[2])*(person[1]-robot[1]))})
        angle = robot[2]
        if abs(omega) > 1e-12:
            robot[0] += v/omega*(math.sin(angle+omega*c.dt)-math.sin(angle))
            robot[1] += v/omega*(math.cos(angle)-math.cos(angle+omega*c.dt))
        else:
            robot[0] += v*c.dt*math.cos(angle)
            robot[1] += v*c.dt*math.sin(angle)
        robot[2] += omega*c.dt
    endpoint = person_position(scenario, steps*c.dt)
    distances.append(math.hypot(endpoint[0]-robot[0], endpoint[1]-robot[1]))
    delta = [sum(abs(b-a) for a,b in zip(rows[i-1], rows[i])) for i in range(1, steps)]
    jerk = [sum(abs(rows[i][j]-2*rows[i-1][j]+rows[i-2][j]) for j in (0,1)) for i in range(2, steps)]
    last_unsettled = max((i for i, ok in enumerate(settled) if not ok), default=-1)
    return {'centering_rms': _rms(offsets), 'distance_rms_m': _rms(errors),
            'distance_final_error_m': distances[-1]-c.desired_distance,
            'distance_overshoot_m': max(0., c.desired_distance-min(distances)),
            'lateral_overshoot_m': max(0., max(cross_track)) if cross_track[0] < 0 else max(0., -min(cross_track)),
            'settling_time_s': (last_unsettled+1)*c.dt if last_unsettled < steps-1 else None,
            'mean_delta_command': sum(delta)/len(delta) if delta else 0.,
            'mean_jerk': sum(jerk)/len(jerk) if jerk else 0.,
            'safety_stop_steps': stops, 'latched_steps': latched,
            'supervisor_fault_steps': faults, 'min_distance_m': min(distances),
            'too_close_stop_steps': gate.too_close_stop_steps,
            'safety_pass': min(distances) >= c.safety_distance and faults == 0,
            'tracking_steps': tracking, 'lost_steps': lost,
            'visible_steps': len(offsets), 'steps': steps, 'seed': seed,
            'operator_reselect_steps': list(operator_reselect_steps)}
