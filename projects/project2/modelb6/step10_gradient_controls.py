"""P2.10: actual supervised-loss gradients on fresh ModelB6 controls."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import tensorflow as tf

import step6
import step8_encoder_audit as s8
import step9_gradient_audit as p29
import step7_sensitivity as s7
from modelB6 import get_model

OUTPUT = Path('/output/p210-gradient-controls')
SEEDS = (3101, 3102, 3103)


def path(name):
    p = (OUTPUT / name).resolve()
    p.relative_to(OUTPUT.resolve())
    return p


def write(name, value):
    target = path(name)
    if target.exists():
        raise FileExistsError(target)
    step6.write_json(target, value)


def protected_inventory():
    prefix = str(OUTPUT.resolve())
    return {k: v for k, v in s8.protected_inventory().items() if not k.startswith(prefix)}


def integrity(snapshot=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    current = protected_inventory()
    baseline_path = path('integrity_before.json')
    if snapshot:
        if baseline_path.exists():
            raise FileExistsError(baseline_path)
        write('integrity_before.json', current)
        return {'status': 'snapshot', 'files': len(current)}
    baseline = json.loads(baseline_path.read_text())
    changed = sorted(k for k in baseline.keys() & current.keys() if baseline[k] != current[k])
    added = sorted(current.keys() - baseline.keys())
    missing = sorted(baseline.keys() - current.keys())
    result = {'status': 'PASS' if not (changed or added or missing) else 'FAIL',
              'files': len(current), 'changed': changed, 'added': added, 'missing': missing}
    if result['status'] != 'PASS':
        raise RuntimeError(json.dumps(result))
    return result


def run():
    if path('results.json').exists():
        raise FileExistsError(path('results.json'))
    if not path('integrity_before.json').exists():
        raise RuntimeError('snapshot required')
    samples_meta = json.loads((p29.OUTPUT / 'samples.json').read_text())
    samples = np.load(p29.OUTPUT / 'samples.npz', allow_pickle=False)
    if step6.sha256(p29.OUTPUT / 'samples.npz') != samples_meta['cache_sha256']:
        raise RuntimeError('P2.9 sample cache changed')
    started = time.monotonic()
    records = []
    identities = []
    for seed in SEEDS:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(seed)
        model = get_model()
        if tuple(model.output_shape) != (None, 2383):
            raise RuntimeError('fresh model output changed')
        if len(model.trainable_weights) == 0 or not all(w.trainable for w in model.trainable_weights):
            raise RuntimeError('fresh model is not fully trainable')
        before = [s7.array_hash(w.numpy()) for w in model.weights]
        identity = {'seed': seed, 'training_steps': 0, 'output': [None, 2383],
                    'trainable_parameters': int(sum(np.prod(w.shape) for w in model.trainable_weights)),
                    'weight_hash': s7.array_hash(np.concatenate([w.numpy().reshape(-1) for w in model.weights]))}
        identities.append(identity)
        probe = tf.keras.Model(model.inputs, [model.output] +
                               [model.get_layer(n).output for n in p29.MONITOR])
        # Same original supervised-loss computation and cached conditions as P2.9.
        for index, sample in enumerate(samples_meta['samples']):
            image, state = samples['images'][index], samples['states'][index]
            audit = p29.audit_one(model, probe, image, state, samples['targets'][index])
            records.append({'seed': seed, 'sample': index, 'domain': sample['domain'],
                            'stratum': sample['stratum'], 'pair': sample['pair'],
                            'condition': 'original', 'loss': audit['loss'],
                            'image_rms': audit['input_gradients']['image']['rms'],
                            'state_rms': audit['input_gradients']['state']['rms'],
                            'image_state_ratio': audit['image_state_rms_ratio'],
                            'stem_rms': audit['activation_gradients']['stem_activation']['rms'],
                            'middle_rms': audit['activation_gradients']['block4d_add']['rms'],
                            'late_rms': audit['activation_gradients']['top_activation']['rms'],
                            'embedding_rms': audit['activation_gradients']['flatten']['rms'],
                            'image_parameter_rms': audit['parameter_groups']['image_encoder']['rms'],
                            'state_parameter_rms': audit['parameter_groups']['state_projection']['rms']})
        after = [s7.array_hash(w.numpy()) for w in model.weights]
        if before != after:
            raise RuntimeError('fresh model weights changed')
        identity['all_weight_hashes_unchanged'] = True
        print(json.dumps({'seed_complete': seed}), flush=True)
    def median(seed, key):
        return float(np.median([r[key] for r in records if r['seed'] == seed]))
    summary = {'status': 'complete', 'seeds': list(SEEDS), 'records': len(records),
               'sample_cache_sha256': samples_meta['cache_sha256'], 'identities': identities,
               'aggregates': {str(seed): {key: median(seed, key) for key in
                              ('loss', 'image_rms', 'state_rms', 'image_state_ratio',
                               'stem_rms', 'middle_rms', 'late_rms', 'embedding_rms',
                               'image_parameter_rms', 'state_parameter_rms')}
                              for seed in SEEDS},
               'runtime_seconds': time.monotonic() - started,
               'training_steps': 0, 'optimizer_created': False,
               'loss_source': '/workspace/professor/train_modelB6.py:custom_loss',
               'conditions': 'P2.9 original condition: real image, previous teacher state, desire zero, traffic [1,0]',
               'caveat': 'Fresh controls are default initialized and have zero training steps; they are not historical P2.5 initialization.'}
    write('records.json', records)
    write('summary.json', summary)
    write('run_metadata.json', {'status': 'complete', 'tensorflow': tf.__version__,
                               'seeds': list(SEEDS), 'records': len(records),
                               'sample_cache_sha256': samples_meta['cache_sha256'],
                               'optimizer_created': False, 'training_steps': 0,
                               'artifacts': {p.name: step6.sha256(p) for p in OUTPUT.iterdir() if p.is_file()}})
    return {'status': 'complete', 'records': len(records), 'runtime_seconds': summary['runtime_seconds']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('snapshot', 'run', 'verify'))
    args = parser.parse_args()
    action = {'snapshot': lambda: integrity(True), 'run': run, 'verify': integrity}[args.command]
    print(json.dumps(action(), indent=2))


if __name__ == '__main__':
    main()
