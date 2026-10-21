"""Synthetic controller math and replay safety, never hardware acceptance."""
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from p3.research.controllers import Observation, RuleBasedController
from p3.research.pid_controller import PIDConfig, PIDAxis, PIDFollowController
from p3.research.closed_loop import SCENARIOS, SimConfig, render_person, run_scenario
from p3.research.pid_sim import main, compare
from p3.research.simulation import SafetySupervisor


def track(offset=.25, fraction=.1, identity=1):
    center = 320*(1+offset)
    return {'id': identity, 'state': 'tracked',
            'box': [center-320*fraction, 100., center+320*fraction, 400.]}


def observation(tracks=None, timestamp=0., age=0.):
    return Observation(timestamp, [track()] if tracks is None else tracks, (480, 640), age)


def axis_step(axis, measurement=0., target=1., dt=.1, **kwargs):
    config = dict(kp=1., ki=1., kd=1., deadband=0., integral_limit=10.,
                  tau=0., low=-100., high=100., slew=1000.)
    config.update(kwargs)
    return axis.step(measurement, target, dt, **config)


class PIDMathTests(unittest.TestCase):
    def test_terms_and_filter(self):
        axis = PIDAxis()
        out, terms = axis_step(axis)
        self.assertAlmostEqual(terms['p'], 1.)
        self.assertAlmostEqual(terms['i'], .1)
        self.assertEqual(terms['d'], 0.)
        out, terms = axis_step(axis, measurement=.2, tau=.1)
        self.assertAlmostEqual(terms['d'], -1.)
        self.assertAlmostEqual(out, .8+.18-1.)

    def test_derivative_no_setpoint_kick(self):
        axis = PIDAxis()
        axis_step(axis, measurement=.1)
        _, terms = axis_step(axis, measurement=.1, target=2.)
        self.assertEqual(terms['d'], 0.)

    def test_anti_windup_and_integral_clamp(self):
        axis = PIDAxis()
        for _ in range(50):
            out, terms = axis_step(axis, high=.3, low=0.)
        self.assertEqual(terms['integral'], 0.)
        self.assertEqual(out, .3)
        axis.reset()
        for _ in range(50):
            _, terms = axis_step(axis, kp=0., kd=0., integral_limit=.2)
        self.assertEqual(terms['integral'], .2)
        # Slew saturation also prevents winding up.
        axis.reset()
        _, terms = axis_step(axis, slew=.1)
        self.assertEqual(terms['integral'], 0.)

    def test_deadband_clamp_and_slew(self):
        axis = PIDAxis()
        out, _ = axis_step(axis, target=.01, deadband=.02)
        self.assertEqual(out, 0.)
        out, _ = axis_step(axis, slew=.2)
        self.assertAlmostEqual(out, .02)
        for _ in range(40):
            out, _ = axis_step(axis, slew=.2, high=.3)
        self.assertEqual(out, .3)


class PIDFollowTests(unittest.TestCase):
    def armed(self, config=None):
        c = PIDFollowController(config)
        self.assert_zero(c.select(1, [track()]))
        return c

    def assert_zero(self, action):
        self.assertEqual((action.linear_velocity_command, action.angular_velocity_command), (0., 0.))

    def test_sign_and_metadata(self):
        c = self.armed()
        a = c.predict(observation())
        self.assertLess(a.angular_velocity_command, 0.)
        self.assertGreater(a.linear_velocity_command, 0.)
        self.assertEqual(a.source_controller, 'pid')
        self.assertEqual(a.metadata['legacy']['state'], 'TRACKING')
        self.assertTrue({'p','i','d'} <= a.metadata['lateral'].keys())
        c.select(1, [track(-.25)])
        self.assertGreater(c.predict(observation([track(-.25)])).angular_velocity_command, 0.)

    def test_no_selection_stale_overlap_fault(self):
        c = PIDFollowController()
        self.assert_zero(c.predict(observation()))
        c.select(1, [track()])
        self.assert_zero(c.predict(observation(age=.6)))
        self.assert_zero(c.predict(observation()))
        c.select(1, [track()])
        self.assert_zero(c.predict(observation([track(), track(identity=2)])))
        c.select(1, [track()])
        self.assert_zero(c.predict(observation([track(), track()])))
        self.assertTrue(c.legacy.faulted)
        self.assert_zero(c.select(1, [track()]))
        self.assert_zero(c.predict(observation()))

    def test_loss_stops_immediately_and_requires_confirmation(self):
        c = self.armed()
        for i in range(20):
            c.predict(observation(timestamp=i*.1))
        self.assert_zero(c.predict(observation([], 2.)))
        self.assertEqual(c.lateral.integral, 0.)
        self.assertEqual(c.longitudinal.integral, 0.)
        self.assert_zero(c.predict(observation(timestamp=2.1)))
        c.select(1, [track()])
        self.assertIsNone(c.timestamp)
        self.assertEqual(c.predict(observation(timestamp=2.2)).status, 'TRACKING')
        self.assert_zero(c.cancel())
        self.assert_zero(c.predict(observation()))
        self.assert_zero(c.stop(fault=True))
        self.assert_zero(c.select(1, [track()]))

    def test_dt_fallback_zero_negative_nonfinite(self):
        c = self.armed()
        self.assertEqual(c.predict(observation(timestamp=None)).metadata['dt'], .1)
        c.predict(observation(timestamp=1.))
        self.assertEqual(c.predict(observation(timestamp=1.)).metadata['dt'], .1)
        self.assert_zero(c.predict(observation(timestamp=.9)))
        for stamp in (math.nan, math.inf, -1.):
            c.select(1, [track()])
            self.assert_zero(c.predict(observation(timestamp=stamp)))

    def test_rate_limits_use_timestamp_dt(self):
        c = self.armed(PIDConfig(speed_slew=.2, turn_slew=.3))
        a = c.predict(observation(timestamp=1.))
        b = c.predict(observation(timestamp=1.05))
        self.assertLessEqual(abs(b.linear_velocity_command-a.linear_velocity_command), .01+1e-12)
        self.assertLessEqual(abs(b.angular_velocity_command-a.angular_velocity_command), .015+1e-12)

    def test_height_axis_close_override_and_reset(self):
        c = self.armed(PIDConfig(size_axis='height', target_fraction=.5))
        self.assert_zero(c.predict(observation([track(offset=0.)])))
        self.assertEqual(c.longitudinal.integral, 0.)

    def test_supervisor_never_faults_or_reverses(self):
        c = self.armed()
        gate = SafetySupervisor()
        gate.rearm()
        for i in range(200):
            t = track(.6*math.sin(i*.1), .05+.003*(i % 100))
            a = c.predict(observation([t], i*.1))
            gate.apply(a)
            self.assertFalse(gate.faulted)
            self.assertTrue(0 <= a.linear_velocity_command <= .3)
            self.assertLessEqual(abs(a.angular_velocity_command), .5)
            if (t['box'][2]-t['box'][0])/640 >= c.config.target_fraction:
                self.assertEqual(a.linear_velocity_command, 0.)

    def test_json_validation_and_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'gains.json'
            path.write_text(json.dumps(PIDConfig().to_dict()))
            self.assertEqual(PIDConfig.from_json(path), PIDConfig())
            for data in ({'unknown': 1}, {'speed_limit': .31}, {'turn_limit': .51},
                         {'nominal_dt': 0}, {'lateral_kp': -1}, {'lateral_kp': True},
                         {'derivative_tau': math.nan}, {'size_axis': 'area'},
                         {'target_fraction': 2}, []):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    PIDConfig.from_json(path)
            path.write_text('{"lateral_kp": 1, "lateral_kp": 2}')
            with self.assertRaises(ValueError):
                PIDConfig.from_json(path)
        with self.assertRaises(AttributeError):
            PIDConfig().lateral_kp = 2.


class ClosedLoopTests(unittest.TestCase):
    def test_determinism_and_all_scenarios(self):
        for s in SCENARIOS:
            a = run_scenario(PIDFollowController(), s, seed=7)
            b = run_scenario(PIDFollowController(), s, seed=7)
            self.assertEqual(a, b)
            self.assertTrue(a['safety_pass'])
            self.assertEqual(a['supervisor_fault_steps'], 0)
        self.assertEqual(run_scenario(PIDFollowController(), 'straight_walk'),
                         run_scenario(PIDFollowController(), 'straight_walk'))

    def test_pid_better_on_straight_and_majority(self):
        result = compare()
        row = result['scenarios']['straight_walk']
        for key in ('centering_rms', 'distance_rms_m'):
            self.assertLess(row['pid'][key], row['rule'][key])
            self.assertGreaterEqual(result['summary']['pid_wins'][key], 4)
        self.assertTrue(result['summary']['all_safety_pass'])

    def test_occlusion_operator_reselect_only(self):
        stopped = run_scenario(PIDFollowController(), 'occlusion', 80)
        resumed = run_scenario(PIDFollowController(), 'occlusion', 80, operator_reselect_steps=(55,))
        self.assertEqual(stopped['tracking_steps'], 40)
        self.assertEqual(stopped['latched_steps'], 40)
        self.assertEqual(resumed['tracking_steps'], 65)

    def test_too_close_stays_stopped(self):
        result = run_scenario(PIDFollowController(), 'too_close')
        self.assertGreaterEqual(result['min_distance_m'], .65)
        self.assertEqual(result['mean_delta_command'], 0.)
        c = PIDFollowController()
        for i in range(100):
            tracks = render_person([0.,0.,0.], [max(.9,1.3-.008*i),0.], SimConfig())
            if i == 0:
                c.select(1, tracks)
            self.assertEqual(c.predict(observation(tracks, i*.1)).linear_velocity_command, 0.)

    def test_camera_geometry_and_validation(self):
        c = SimConfig()
        self.assertEqual(render_person([0.,0.,0.], [-1.,0.], c), [])
        self.assertEqual(render_person([0.,0.,0.], [1.,10.], c), [])
        tracks = render_person([0.,0.,0.], [1.,-.2], c)
        self.assertGreater(tracks[0]['box'][0]+tracks[0]['box'][2], c.image_width)
        for kwargs in ({'dt': 0}, {'hfov_degrees': 180}, {'image_width': 2.5}):
            with self.assertRaises(ValueError):
                SimConfig(**kwargs)
        with self.assertRaises(ValueError):
            run_scenario(PIDFollowController(), 'invalid')

    def test_cli_json_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'new'/'compare.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--output', str(path), '--steps', '20']), 0)
            content = path.read_bytes()
            self.assertEqual(json.loads(content)['kind'], 'synthetic_kinematic_simulation')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['--output', str(path)])
            self.assertEqual(path.read_bytes(), content)
            for controller in ('pid', 'rule'):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(['--controller', controller, '--scenarios', 'straight_walk',
                          '--steps', '2', '--output', str(Path(d)/f'{controller}.json')])


if __name__ == '__main__':
    unittest.main()
