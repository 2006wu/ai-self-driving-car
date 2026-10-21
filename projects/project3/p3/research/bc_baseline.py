"""Opt-in numpy behaviour cloning, synthetic/offline simulation only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import re

import numpy as np

from ..follow import FollowController
from . import control_dataset as cd
from .controllers import Action, RuleBasedController
from .closed_loop import SCENARIOS, SimConfig, run_scenario
from .pid_controller import PIDFollowController
from .dataset import loads, finite_tree

SCHEMA = 'p3_bc_model/1.0'
STOP_TOLERANCE = 1e-3


def numeric_array(value, shape):
    """Weights/statistics must be JSON lists of numbers, never strings/bools."""
    def numeric_tree(item):
        return (all(numeric_tree(v) for v in item) if isinstance(item, list)
                else type(item) in (int, float))
    if not isinstance(value, list) or not numeric_tree(value):
        raise ValueError('numeric lists required')
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError('array shape/finiteness')
    return result


def write_json(path, value):
    """Exclusive creation, including reports. Serialize before opening the file."""
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(payload)


def load_dataset(directory, teacher='pid'):
    manifest, _ = cd.validate(directory)  # Integrity/schema validation precedes use.
    if teacher not in ('pid', 'rule', 'all'):
        raise ValueError('unknown teacher')
    directory = Path(directory)
    splits = {}
    for split in cd.SPLITS:
        rows = [loads(line) for line in (directory/f'samples-{split}.jsonl').read_text().splitlines()]
        rows = [r for r in rows if teacher == 'all' or r['teacher_action']['controller_type'] == teacher]
        x = np.array([[np.nan if v is None else float(v) for v in r['feature_vector']] for r in rows], dtype=float).reshape(-1, len(cd.FEATURES))
        y = np.array([[r['teacher_action'][k] for k in cd.ACTIONS] for r in rows], dtype=float).reshape(-1, 2)
        tracking = np.array([r['teacher_action']['status'] == 'TRACKING' for r in rows], dtype=bool)
        splits[split] = (x, y, tracking)
    return manifest, hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(), splits


def normalization(x):
    counts = np.sum(np.isfinite(x), axis=0)
    mean = np.nansum(x, axis=0)/np.maximum(counts, 1)
    filled = np.where(np.isnan(x), mean, x)
    scale = filled.std(axis=0)
    scale[scale < 1e-8] = 1.
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'missing': 'train_mean'}


def standardized(x, norm):
    x = np.asarray(x, dtype=float)
    return (np.where(np.isnan(x), norm['mean'], x)-norm['mean'])/norm['scale']


def forward(x, kind, weights):
    w = {k: np.asarray(v) for k, v in weights.items()}
    if kind == 'ridge':
        return x @ w['w'] + w['b']
    return np.tanh(x @ w['w1'] + w['b1']) @ w['w2'] + w['b2']


def fit_ridge(x, y, alpha):
    """Standardized features; unpenalized intercept, closed-form ridge."""
    design = np.column_stack((x, np.ones(len(x))))
    penalty = np.eye(design.shape[1])*alpha
    penalty[-1, -1] = 0.
    weights = np.linalg.lstsq(design.T @ design + penalty, design.T @ y, rcond=None)[0]
    return {'w': weights[:-1].tolist(), 'b': weights[-1].tolist()}


def fit_mlp(x, y, vx, vy, *, seed=0, hidden=16, learning_rate=.01,
            epochs=500, patience=35):
    """Full-batch Adam. Validation selects the epoch; gradients use train only."""
    rng = np.random.default_rng(seed)
    w = {'w1': rng.normal(0, 1/np.sqrt(x.shape[1]), (x.shape[1], hidden)),
         'b1': np.zeros(hidden), 'w2': rng.normal(0, .1, (hidden, 2)), 'b2': y.mean(axis=0)}
    m, v = ({k: np.zeros_like(a) for k, a in w.items()} for _ in range(2))
    best, best_loss, best_epoch, history = None, float('inf'), 0, []
    for epoch in range(1, epochs+1):
        h = np.tanh(x @ w['w1'] + w['b1'])
        error = h @ w['w2'] + w['b2'] - y
        history.append(float(np.mean(error**2)))
        grad_out = error/len(x)  # mean over N*2 outputs
        dh = (grad_out @ w['w2'].T)*(1-h*h)
        gradients = {'w1': x.T @ dh, 'b1': dh.sum(axis=0),
                     'w2': h.T @ grad_out, 'b2': grad_out.sum(axis=0)}
        for k, g in gradients.items():
            m[k] = .9*m[k]+.1*g
            v[k] = .999*v[k]+.001*g*g
            w[k] -= learning_rate*(m[k]/(1-.9**epoch))/(np.sqrt(v[k]/(1-.999**epoch))+1e-8)
        loss = float(np.mean((forward(vx, 'mlp', w)-vy)**2))
        if loss < best_loss-1e-12:
            best, best_loss, best_epoch = copy.deepcopy(w), loss, epoch
        if epoch-best_epoch >= patience:
            break
    return {k: a.tolist() for k, a in best.items()}, {'best_epoch': best_epoch,
        'epochs_run': epoch, 'initial_train_mse': history[0], 'final_train_mse': float(np.mean((forward(x, 'mlp', best)-y)**2))}


class BCModel:
    def __init__(self, data):
        try:
            finite_tree(data)
            if data['schema'] != SCHEMA or data['feature_names'] != cd.FEATURES or data['action_names'] != cd.ACTIONS:
                raise ValueError('schema or feature/action names mismatch')
            if not re.fullmatch(r'[0-9a-f]{64}', data['training_manifest_sha256']):
                raise ValueError('manifest hash')
            if not isinstance(data['config'], dict) or not isinstance(data['metrics'], dict):
                raise ValueError('config/metrics')
            norm = data['normalization']
            if norm['missing'] != 'train_mean':
                raise ValueError('missing data policy')
            n = len(cd.FEATURES)
            for key in ('mean', 'scale'):
                numeric_array(norm[key], (n,))
            if np.any(np.asarray(norm['scale']) <= 0):
                raise ValueError('normalization scale')
            w = data['weights']
            if data['model_type'] == 'ridge':
                shapes = {'w': (n, 2), 'b': (2,)}
            elif data['model_type'] == 'mlp':
                hidden = len(w['b1'])
                if not 1 <= hidden <= 256:
                    raise ValueError('hidden width')
                shapes = {'w1': (n, hidden), 'b1': (hidden,), 'w2': (hidden, 2), 'b2': (2,)}
            else:
                raise ValueError('model type')
            if set(w) != set(shapes):
                raise ValueError('weight keys')
            for key, shape in shapes.items():
                numeric_array(w[key], shape)
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError('malformed BC model') from exc
        self.data = copy.deepcopy(data)

    @classmethod
    def load(cls, path):
        return cls(loads(Path(path).read_text()))

    def save(self, path):
        write_json(path, self.data)

    def predict(self, x):
        with np.errstate(over='ignore', invalid='ignore'):
            return forward(standardized(x, self.data['normalization']), self.data['model_type'], self.data['weights'])


def action_metrics(y, predicted):
    if not len(y):
        return {'count': 0, 'mae': None, 'rmse': None, 'r2': None, 'stop_agreement': None}
    error = predicted-y
    sse = np.sum(error**2, axis=0)
    sst = np.sum((y-y.mean(axis=0))**2, axis=0)
    # Constant targets: perfect => 1, otherwise 0 (finite convention).
    r2 = np.array([1-a/b if b > 1e-15 else float(a < 1e-15) for a, b in zip(sse, sst)])
    return {'count': len(y), 'mae': dict(zip(cd.ACTIONS, np.mean(abs(error), axis=0).tolist())),
            'rmse': dict(zip(cd.ACTIONS, np.sqrt(np.mean(error**2, axis=0)).tolist())),
            'r2': dict(zip(cd.ACTIONS, r2.tolist())), 'stop_agreement': float(np.mean(
                np.all(abs(y) <= STOP_TOLERANCE, axis=1) == np.all(abs(predicted) <= STOP_TOLERANCE, axis=1)))}


def offline_metrics(model, splits):
    result = {}
    for split, (x, y, tracking) in splits.items():
        predicted = np.clip(model.predict(x), [0., -.5], [.3, .5])
        predicted[~tracking] = 0.  # Same authoritative state gate as the controller.
        result[split] = action_metrics(y, predicted)
        result[split]['tracking_only'] = action_metrics(y[tracking], predicted[tracking])
    return result


def train(directory, kind='ridge', seed=0, teacher='pid', tracking_only=True):
    if kind not in ('ridge', 'mlp') or type(seed) is not int:
        raise ValueError('invalid model type/seed')
    manifest, digest, splits = load_dataset(directory, teacher)
    selected = {}
    for split, (x, y, tracking) in splits.items():
        mask = tracking if tracking_only else np.ones(len(x), dtype=bool)
        selected[split] = (x[mask], y[mask])
    if not len(selected['train'][0]) or not len(selected['val'][0]):
        raise ValueError('nonempty train and val required after filtering; build more episodes')
    norm = normalization(selected['train'][0])
    x, y = standardized(selected['train'][0], norm), selected['train'][1]
    vx, vy = standardized(selected['val'][0], norm), selected['val'][1]
    candidates = []
    for value in ((1e-4, .01, 1., 10.) if kind == 'ridge' else (.003, .01)):
        if kind == 'ridge':
            weights, detail = fit_ridge(x, y, value), {'alpha': value}
        else:
            weights, detail = fit_mlp(x, y, vx, vy, seed=seed, learning_rate=value)
            detail['learning_rate'] = value
            detail['hidden'] = 16
        score = float(np.mean((forward(vx, kind, weights)-vy)**2))
        candidates.append((score, weights, detail))
    score, weights, detail = min(candidates, key=lambda row: row[0])
    data = {'schema': SCHEMA, 'model_type': kind, 'feature_names': list(cd.FEATURES),
        'action_names': list(cd.ACTIONS), 'normalization': norm, 'weights': weights,
        'training_manifest_sha256': digest, 'config': {'seed': seed, 'teacher': teacher,
        'tracking_only': tracking_only, 'selected': detail, 'selection_val_mse': score,
        'candidates': [{'val_mse': s, **d} for s, _, d in candidates],
        'training_rows': len(x), 'dataset': manifest['created_from'],
        'training_episodes': sorted(k for k, e in manifest['episodes'].items()
            if cd.split_episode(k, manifest['split_ratios']) == 'train' and
            (teacher == 'all' or e.get('controller') == teacher)),
        'stop_tolerance': STOP_TOLERANCE}, 'metrics': {}}
    model = BCModel(data)
    model.data['metrics'] = offline_metrics(model, splits)
    return model


class BCFollowController:
    """Selection/loss/stale/overlap/latch/fault policy belongs to FollowController."""
    def __init__(self, model, **policy):
        self.model = BCModel.load(model) if isinstance(model, (str, Path)) else model
        if not isinstance(self.model, BCModel):
            raise ValueError('BCModel required')
        self.legacy = FollowController(**policy)

    @staticmethod
    def _action(output, speed=0., turn=0.):
        return Action(float(speed), float(turn), output['state'], 'bc', True,
                      metadata={'legacy': dict(output), 'reason': output['reason'], 'state': output['state']})

    def select(self, target_id, tracks):
        try:
            return self._action(self.legacy.select(target_id, tracks))
        except (KeyError, TypeError, ValueError, OverflowError):
            return self.stop('invalid_tracking_data', fault=True)

    def cancel(self):
        return self._action(self.legacy.cancel())

    def stop(self, reason='stop', fault=False):
        return self._action(self.legacy.stop(reason, fault))

    def predict(self, observation):
        output = self.legacy.update(observation.tracks, observation.frame_dimensions, observation.age_seconds)
        if output['state'] != 'TRACKING':
            return self._action(output)
        features = cd.observation_features(*observation.frame_dimensions[:2], observation.tracks,
            self.legacy.target, output['state'], output['reason'], observation.age_seconds)
        try:
            predicted = np.asarray(self.model.predict([cd.features(features)]), dtype=float)
            if predicted.shape != (1, 2) or not np.isfinite(predicted).all():
                raise ValueError('invalid output')
        except (ValueError, TypeError, ArithmeticError):
            return self.stop('invalid_bc_output', fault=True)
        speed, turn = np.clip(predicted[0], [0., -.5], [.3, .5])
        return self._action(output, speed, turn)


def evaluate_closed_loop(model, scenarios=SCENARIOS, steps=200):
    """Nominal plus held-out plant perturbations; seed labels alone change no dynamics."""
    if not scenarios or len(set(scenarios)) != len(scenarios) or set(scenarios)-set(SCENARIOS):
        raise ValueError('invalid scenarios')
    training_seed = model.data['config']['dataset'].get('seed', 0)
    seed = training_seed+100003
    rng = random.Random(seed)
    # Outside build_sim's training perturbation support [.8, 1.2].
    scales = [1., rng.uniform(.65, .75), rng.uniform(1.25, 1.35)]
    episodes = []
    for index, scale in enumerate(scales):
        config = SimConfig(max_linear=scale)
        for scenario in scenarios:
            results = {name: run_scenario(controller(), scenario, steps, config, seed)
                for name, controller in [('bc', lambda: BCFollowController(model)),
                    ('pid', PIDFollowController), ('rule', RuleBasedController)]}
            episodes.append({'scenario': scenario, 'episode_index': index,
                'partition': 'nominal' if index == 0 else 'held_out_perturbation',
                'seed': seed, 'config': config.to_dict(), 'controllers': results})
    return {'kind': 'synthetic_kinematic_simulation', 'model_schema': SCHEMA,
            'training_manifest_sha256': model.data['training_manifest_sha256'],
            'held_out_policy': 'new seed and plant scales outside training support; nominal may duplicate training trajectories',
            'episodes': episodes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('train')
    p.add_argument('--dataset', required=True)
    p.add_argument('--model', choices=('ridge', 'mlp'), required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--teacher', choices=('pid', 'rule', 'all'), default='pid')
    p.add_argument('--all-states', action='store_true', help='also fit safety-forced zero labels')
    p = commands.add_parser('eval-offline')
    p.add_argument('--dataset', required=True)
    p.add_argument('--model-file', required=True)
    p.add_argument('--output', help='optional new JSON file; always prints metrics')
    p = commands.add_parser('eval-closed-loop')
    p.add_argument('--model-file', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--scenarios', default=','.join(SCENARIOS))
    p.add_argument('--steps', type=int, default=200)
    args = parser.parse_args(argv)
    try:
        if getattr(args, 'output', None) and Path(args.output).exists():
            raise FileExistsError('output already exists')
        if args.command == 'train':
            model = train(args.dataset, args.model, args.seed, args.teacher, not args.all_states)
            model.save(args.output)
            result = model.data['metrics']
        else:
            model = BCModel.load(args.model_file)
            if args.command == 'eval-offline':
                _, digest, splits = load_dataset(args.dataset, model.data['config']['teacher'])
                result = {'dataset_manifest_sha256': digest, 'metrics': offline_metrics(model, splits)}
            else:
                result = evaluate_closed_loop(model, args.scenarios.split(','), args.steps)
            if args.output:
                write_json(args.output, result)
    except (ValueError, OSError, TypeError, KeyError, np.linalg.LinAlgError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    main()
