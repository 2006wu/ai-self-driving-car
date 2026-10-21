"""Synthetic distance gate regressions; no hardware acceptance evidence."""
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from p3.research import bc_baseline as bc, control_dataset as cd
from p3.research.closed_loop import SCENARIOS, SimConfig, run_scenario
from p3.research.controllers import Action, Observation, RuleBasedController
from p3.research.pid_controller import PIDFollowController
from p3.research.simulation import SafetySupervisor


def observation(distance, *, clipped=False, identity=1):
    focal = 640/(2*math.tan(math.radians(70)/2))
    width = .5*focal/distance
    box = [320-width/2, 100., 320+width/2, 400.]
    if clipped:
        box[0] = 0.
    return Observation(0., [{'id': identity, 'state': 'tracked', 'box': box}],
                       (480, 640), 0., target_id=identity)


class HostileController:
    """Ignores selection, loss and distance, and lies in its metadata."""
    def __init__(self):
        self.legacy = SimpleNamespace(latched=False)

    def select(self, *_):
        pass

    def predict(self, _):
        return Action(.3, 0., 'TRACKING', 'hostile', True,
                      metadata={'estimated_distance_m': 1000., 'target_id': 999})


class SupervisorDistanceTests(unittest.TestCase):
    def setUp(self):
        self.gate = SafetySupervisor()
        self.gate.rearm()
        self.action = Action(.3, -.4, 'TRACKING', 'test', True,
                             metadata={'estimated_distance_m': 1000.})

    def test_stop_release_no_latch_and_metadata_not_trusted(self):
        for distance in (.8, 2., .8, 1.01, 2.):
            with self.subTest(distance=distance):
                safe = self.gate.apply(self.action, observation=observation(distance))
                self.assertEqual(safe.linear_velocity_command, 0. if distance < 1. else .3)
                self.assertEqual(safe.angular_velocity_command, -.4)
                self.assertEqual(safe.status, 'TRACKING')
                self.assertFalse(self.gate.latched)
                self.assertFalse(self.gate.faulted)
                if distance < 1.:
                    self.assertEqual(safe.metadata['safety_stop'], 'too_close')
                    self.assertAlmostEqual(safe.metadata['estimated_distance_m'], distance)
        self.assertEqual(self.gate.too_close_stop_steps, 2)
        self.assertEqual(self.action.metadata, {'estimated_distance_m': 1000.})
        self.assertEqual(self.gate.apply(self.action), self.action)

    def test_release_exactly_at_threshold_and_missing_target_stops(self):
        obs = observation(1.)
        gate = SafetySupervisor(too_close_distance_m=self.gate._distance(obs))
        gate.rearm()
        self.assertEqual(gate.apply(self.action, observation=obs).linear_velocity_command, .3)
        missing = Observation(0., [], (480, 640), 0., target_id=1)
        self.assertEqual(gate.apply(self.action, observation=missing).linear_velocity_command, 0.)
        self.assertFalse(gate.latched)
        self.assertEqual(gate.apply(self.action, observation=observation(2.)).linear_velocity_command, .3)

    def test_only_horizontal_clipped_edges_are_conservative(self):
        for coordinate, value in ((0, 0.), (1, 0.), (2, 640.), (3, 480.)):
            with self.subTest(coordinate=coordinate):
                obs = observation(2.)
                box = obs.tracks[0]['box']
                if coordinate in (0, 2):
                    # Preserve the far width: a width-only estimate would pass.
                    shift = value-box[coordinate]
                    box[0] += shift
                    box[2] += shift
                else:
                    box[coordinate] = value
                safe = self.gate.apply(self.action, observation=obs)
                if coordinate in (0, 2):
                    self.assertEqual(safe.linear_velocity_command, 0.)
                    self.assertEqual(safe.metadata['estimated_distance_m'], 0.)
                else:
                    self.assertAlmostEqual(self.gate._distance(obs), 2.)
                    self.assertEqual(safe, self.action)

    def test_target_selection_and_geometry(self):
        gate = SafetySupervisor(hfov_degrees=90., person_width_m=1.)
        gate.rearm()
        obs = Observation(0., [
            {'id': 1, 'state': 'tracked', 'box': [10., 100., 630., 400.]},
            {'id': 2, 'state': 'tracked', 'box': [240., 100., 400., 400.]},
        ], (480, 640), 0., target_id=2)
        self.assertEqual(gate.apply(self.action, observation=obs).linear_velocity_command, .3)
        self.assertAlmostEqual(gate._distance(obs), 2.)

    def test_invalid_config(self):
        for key in ('too_close_distance_m', 'hfov_degrees', 'person_width_m'):
            for value in (None, True, 0., -1., math.inf, math.nan, '1'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    SafetySupervisor(**{key: value})
        for value in (1., 179., 180., 360.):
            with self.assertRaises(ValueError):
                SafetySupervisor(hfov_degrees=value)

    def test_emergency_latch_still_authoritative(self):
        stopped = self.gate.apply(self.action, observation=observation(.8), emergency_stop=True)
        self.assertEqual((stopped.linear_velocity_command, stopped.angular_velocity_command), (0., 0.))
        self.assertTrue(self.gate.latched)
        self.assertEqual(self.gate.apply(self.action, observation=observation(2.)).status, 'STOP')


class ClosedLoopDistanceTests(unittest.TestCase):
    def checked_run(self, controller, scenario):
        seen = []

        def capture(step, obs, proposed, safe, latched, faulted, truth):
            # True radial distance >= camera depth. Pinhole roundoff tolerance
            # is 1e-9m; clipping only makes the gate more conservative.
            if truth['distance_m'] < 1.-1e-9:
                self.assertEqual(safe.linear_velocity_command, 0.)
            seen.append(safe.metadata.get('safety_stop') == 'too_close')

        result = run_scenario(controller, scenario, on_step=capture)
        self.assertEqual(result['too_close_stop_steps'], sum(seen))
        self.assertEqual(result['supervisor_fault_steps'], 0)
        return result

    def checked_stationary_run(self, controller):
        config = SimConfig()
        threshold = SafetySupervisor().too_close_distance_m
        # A stationary person isolates robot travel after the last sample at
        # or above the threshold. One step covers at most dt*max_linear, so
        # the bound is 1.0 - .1*1.0 = .9m, with only pinhole roundoff allowed.
        lower_bound = threshold-config.dt*config.max_linear
        with patch('p3.research.closed_loop.person_position', return_value=(1.3, 0.)):
            result = self.checked_run(controller, 'too_close')
        self.assertGreaterEqual(result['min_distance_m'], lower_bound-1e-9)
        self.assertGreaterEqual(result['min_distance_m'], config.safety_distance)
        self.assertTrue(result['safety_pass'])
        return result

    def test_hostile_all_scenarios(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                result = self.checked_run(HostileController(), scenario)
                if scenario == 'too_close':
                    # The gate first stops at .976m (robot x=.3m), but the
                    # authored person continues to x=.9m: final gap .6m.
                    # Stopping forward motion cannot prevent that approach.
                    self.assertAlmostEqual(result['min_distance_m'], .6)
                    self.assertFalse(result['safety_pass'])
                    self.assertGreater(result['too_close_stop_steps'], 0)
        stationary = self.checked_stationary_run(HostileController())
        # Exercises forward travel and the actual 1m stop, despite vertical
        # clipping, rather than stopping immediately at the initial 1.3m gap.
        self.assertAlmostEqual(stationary['min_distance_m'], .9)
        self.assertGreater(stationary['too_close_stop_steps'], 0)

    def test_geometry_flows_to_supervisor(self):
        config = SimConfig(hfov_degrees=85., person_width=.6)
        with patch('p3.research.closed_loop.SafetySupervisor', wraps=SafetySupervisor) as factory:
            run_scenario(HostileController(), 'too_close', config=config)
        factory.assert_called_once_with(hfov_degrees=85., person_width_m=.6)

    def test_rule_pid_metrics_unchanged(self):
        for controller in (PIDFollowController, RuleBasedController):
            for scenario in SCENARIOS:
                with self.subTest(controller=controller.__name__, scenario=scenario):
                    after = run_scenario(controller(), scenario)
                    with patch('p3.research.closed_loop.SafetySupervisor',
                               side_effect=lambda **kw: SafetySupervisor(too_close_distance_m=1e-6, **kw)):
                        before = run_scenario(controller(), scenario)
                    for key in ('centering_rms', 'min_distance_m'):
                        self.assertEqual(after[key], before[key])
                    # Also compare the exact pre-distance-gate behavior, including
                    # absence of conservative clipping, without a public disable flag.
                    with patch.object(SafetySupervisor, '_distance', return_value=None):
                        original = run_scenario(controller(), scenario)
                    for key in ('centering_rms', 'min_distance_m'):
                        self.assertEqual(after[key], original[key])

    def test_trained_ridge_and_mlp_too_close(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory)/'dataset'
            cd.build_sim(dataset, controllers=('pid',), episodes_per_scenario=8,
                         steps=25, seed=5, perturb=True)
            factories = {'pid': PIDFollowController, 'rule': RuleBasedController}
            for kind in ('ridge', 'mlp'):
                model = bc.train(dataset, kind=kind)
                factories['bc_'+kind] = lambda model=model: bc.BCFollowController(model)
            for name, factory in factories.items():
                with self.subTest(controller=name):
                    after = self.checked_run(factory(), 'too_close')
                    # Empirical moving-person regression floor, not the .9m
                    # stationary-person bound: the person can keep approaching
                    # after the gate has removed all forward commands.
                    self.assertGreaterEqual(after['min_distance_m'], .9-.02)
                    self.assertGreaterEqual(after['min_distance_m'], SimConfig().safety_distance)
                    with patch.object(SafetySupervisor, '_distance', return_value=None):
                        before = run_scenario(factory(), 'too_close')
                    self.assertGreaterEqual(after['min_distance_m'], before['min_distance_m'])
                    self.checked_stationary_run(factory())


if __name__ == '__main__':
    unittest.main()
