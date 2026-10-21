"""Fast numpy cloning and synthetic safety contracts; no physical acceptance."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from p3.research import bc_baseline as bc, control_dataset as cd
from p3.research.closed_loop import run_scenario
from p3.research.controllers import Observation, AIController
from p3.research.simulation import SafetySupervisor


def track(identity=1):
    return {'id': identity, 'state': 'tracked', 'box': [352., 100., 416., 400.]}


def observation(tracks=None, age=0.):
    return Observation(0., [track()] if tracks is None else tracks, (480, 640), age)


class BCMathTests(unittest.TestCase):
    def test_ridge_known_map(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=(100, len(cd.FEATURES)))
        y = x @ rng.normal(size=(len(cd.FEATURES), 2))+[.2, -.1]
        norm = bc.normalization(x)
        z = bc.standardized(x, norm)
        w = bc.fit_ridge(z, y, 0.)
        np.testing.assert_allclose(bc.forward(z, 'ridge', w), y, atol=1e-10)

    def test_mlp_determinism_and_learning(self):
        rng = np.random.default_rng(8)
        x = rng.normal(size=(80, len(cd.FEATURES)))
        y = np.column_stack((.1*np.tanh(x[:, 0]), .2*np.tanh(x[:, 1])))
        a, detail = bc.fit_mlp(x[:60], y[:60], x[60:], y[60:], epochs=160, seed=7)
        b, second = bc.fit_mlp(x[:60], y[:60], x[60:], y[60:], epochs=160, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(detail, second)
        self.assertLess(detail['final_train_mse'], detail['initial_train_mse']*.1)

    def test_metrics_constant_empty_stop(self):
        self.assertIsNone(bc.action_metrics(np.empty((0, 2)), np.empty((0, 2)))['r2'])
        m = bc.action_metrics(np.zeros((3, 2)), np.zeros((3, 2)))
        self.assertEqual(m['r2'], {'linear': 1., 'angular': 1.})
        self.assertEqual(m['stop_agreement'], 1.)


class BCDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.dataset = cls.root/'data'
        cd.build_sim(cls.dataset, controllers=('pid',), episodes_per_scenario=8,
                     steps=25, seed=5, perturb=True)
        cls.model = bc.train(cls.dataset)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_roundtrip_and_bad_models(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'model.json'
            self.model.save(path)
            loaded = bc.BCModel.load(path)
            self.assertEqual(loaded.data, self.model.data)
            x = np.ones((3, len(cd.FEATURES)))
            np.testing.assert_array_equal(loaded.predict(x), self.model.predict(x))
            before = path.read_bytes()
            with self.assertRaises(FileExistsError): loaded.save(path)
            self.assertEqual(path.read_bytes(), before)
            for key, value in [('schema', 'bad'), ('feature_names', list(reversed(cd.FEATURES))),
                               ('model_type', 'bad'), ('training_manifest_sha256', 'x')]:
                bad = copy.deepcopy(loaded.data); bad[key] = value
                with self.subTest(key=key), self.assertRaises(ValueError): bc.BCModel(bad)
            for value in ([[1., 2.]], [[float('nan'), 0.]]*len(cd.FEATURES),
                          [[float('inf'), 0.]]*len(cd.FEATURES)):
                bad = copy.deepcopy(loaded.data); bad['weights']['w'] = value
                with self.assertRaises(ValueError): bc.BCModel(bad)
            for value in ([1.], [0.]*len(cd.FEATURES), [float('inf')]*len(cd.FEATURES)):
                bad = copy.deepcopy(loaded.data); bad['normalization']['scale'] = value
                with self.assertRaises(ValueError): bc.BCModel(bad)
            path.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(ValueError): bc.BCModel.load(path)

    def test_mlp_roundtrip_shapes_and_train_determinism(self):
        data = copy.deepcopy(self.model.data)
        data['model_type'] = 'mlp'
        data['weights'] = {'w1': np.zeros((len(cd.FEATURES), 3)).tolist(),
                           'b1': [0.]*3, 'w2': np.zeros((3, 2)).tolist(), 'b2': [.1, -.2]}
        model = bc.BCModel(data)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'mlp.json'
            model.save(path)
            self.assertEqual(bc.BCModel.load(path).data, data)
        data['weights']['w2'] = [[0., 0.]]
        with self.assertRaises(ValueError): bc.BCModel(data)
        self.assertEqual(self.model.data, bc.train(self.dataset).data)

    def test_train_rows_only_no_validation_or_test_gradients(self):
        manifest, digest, splits = bc.load_dataset(self.dataset)
        train_x, train_y, tracking = splits['train']
        expected = bc.normalization(train_x[tracking])
        self.assertEqual(self.model.data['normalization'], expected)
        calls = []
        original = bc.fit_ridge
        def capture(x, y, alpha):
            calls.append((x.copy(), y.copy()))
            return original(x, y, alpha)
        changed = copy.deepcopy(splits)
        changed['test'] = (splits['test'][0]+100., splits['test'][1]+100., splits['test'][2])
        with patch.object(bc, 'load_dataset', return_value=(manifest, digest, changed)), patch.object(bc, 'fit_ridge', side_effect=capture):
            other = bc.train(self.dataset)
        self.assertEqual(self.model.data['weights'], other.data['weights'])
        for x, y in calls:
            np.testing.assert_array_equal(y, train_y[tracking])
            np.testing.assert_array_equal(x, bc.standardized(train_x[tracking], expected))
        changed['val'] = (splits['val'][0]+50., splits['val'][1], splits['val'][2])
        calls.clear()
        with patch.object(bc, 'load_dataset', return_value=(manifest, digest, changed)), patch.object(bc, 'fit_ridge', side_effect=capture):
            bc.train(self.dataset)
        for x, y in calls:
            np.testing.assert_array_equal(y, train_y[tracking])
            np.testing.assert_array_equal(x, bc.standardized(train_x[tracking], expected))

    def test_validation_first_and_empty_splits(self):
        with patch.object(cd, 'validate', side_effect=ValueError('bad integrity')):
            with self.assertRaisesRegex(ValueError, 'bad integrity'): bc.load_dataset(self.dataset)
        manifest, digest, splits = bc.load_dataset(self.dataset)
        splits['val'] = (np.empty((0, len(cd.FEATURES))), np.empty((0, 2)), np.array([], dtype=bool))
        with patch.object(bc, 'load_dataset', return_value=(manifest, digest, splits)):
            with self.assertRaisesRegex(ValueError, 'nonempty'): bc.train(self.dataset)

    def test_closed_loop_straight_and_report(self):
        result = run_scenario(bc.BCFollowController(self.model), 'straight_walk', steps=100)
        self.assertTrue(result['safety_pass'])
        self.assertLess(result['centering_rms'], .12)
        self.assertEqual(result['supervisor_fault_steps'], 0)
        report = bc.evaluate_closed_loop(self.model, ('straight_walk',), steps=20)
        self.assertEqual(len(report['episodes']), 3)
        for row in report['episodes']:
            self.assertEqual(set(row['controllers']), {'bc', 'pid', 'rule'})
            if row['partition'] == 'held_out_perturbation':
                self.assertFalse(.8 <= row['config']['max_linear'] <= 1.2)

    def test_cli_and_reports_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            model_path = Path(d)/'model.json'
            report = Path(d)/'offline.json'
            closed = Path(d)/'closed.json'
            with contextlib.redirect_stdout(io.StringIO()):
                bc.main(['train', '--dataset', str(self.dataset), '--model', 'ridge', '--output', str(model_path)])
                bc.main(['eval-offline', '--dataset', str(self.dataset), '--model-file', str(model_path), '--output', str(report)])
                bc.main(['eval-closed-loop', '--model-file', str(model_path), '--output', str(closed), '--scenarios', 'straight_walk', '--steps', '10'])
            self.assertIn('test', json.loads(report.read_text())['metrics'])
            for command, path, extra in [('train', model_path, ['--dataset', str(self.dataset), '--model', 'ridge']),
                    ('eval-offline', report, ['--dataset', str(self.dataset), '--model-file', str(model_path)]),
                    ('eval-closed-loop', closed, ['--model-file', str(model_path)])]:
                before = path.read_bytes()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    bc.main([command, '--output', str(path), *extra])
                self.assertEqual(before, path.read_bytes())

    def controller(self):
        return bc.BCFollowController(copy.deepcopy(self.model))

    def zero(self, action):
        self.assertEqual((action.linear_velocity_command, action.angular_velocity_command), (0., 0.))
        self.assertEqual(action.source_controller, 'bc')

    def test_controller_selection_loss_stale_latch_overlap_fault(self):
        c = self.controller()
        self.zero(c.predict(observation()))
        self.zero(c.select(1, [track()]))
        self.zero(c.predict(observation([])))
        self.zero(c.predict(observation()))
        c.select(1, [track()])
        self.zero(c.predict(observation(age=.6)))
        self.zero(c.predict(observation()))
        c.select(1, [track()])
        self.zero(c.predict(observation([track(), track(2)])))
        self.zero(c.predict(observation()))
        c.select(1, [track()])
        self.zero(c.predict(observation([track(), track()])))
        self.assertTrue(c.legacy.faulted)
        self.zero(c.select(1, [track()]))
        self.zero(c.cancel())
        self.assertFalse(AIController().predict(None).valid)
        self.assertEqual(AIController().predict(None).status, 'UNAVAILABLE')

    def test_limits_no_reverse_and_supervisor(self):
        c, gate = self.controller(), SafetySupervisor()
        c.select(1, [track()]); gate.rearm()
        for speed, turn in [(-1e3, -1e3), (1e3, 1e3), (.1, -.2)]:
            with patch.object(c.model, 'predict', return_value=np.array([[speed, turn]])):
                a = c.predict(observation())
            self.assertTrue(0 <= a.linear_velocity_command <= .3)
            self.assertLessEqual(abs(a.angular_velocity_command), .5)
            gate.apply(a)
            self.assertFalse(gate.faulted)

    def test_nonfinite_output_stops_with_fault(self):
        for value in (float('nan'), float('inf')):
            c = self.controller(); c.select(1, [track()])
            with patch.object(c.model, 'predict', return_value=[[value, 0.]]):
                a = c.predict(observation())
            self.zero(a)
            self.assertEqual(a.status, 'STOP')
            self.assertTrue(c.legacy.faulted)
            self.zero(c.select(1, [track()]))

    def test_reuses_dataset_feature_builder(self):
        c = self.controller(); c.select(1, [track()])
        with patch.object(cd, 'observation_features', wraps=cd.observation_features) as builder:
            c.predict(observation())
            builder.assert_called_once_with(480, 640, [track()], 1, 'TRACKING', 'visible_unambiguous_target', 0.)


if __name__ == '__main__':
    unittest.main()
