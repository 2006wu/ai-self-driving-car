"""P2.10: actual supervised-loss gradients on fresh ModelB6 controls."""
import argparse
import json
import time
import math
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
    for name in ('records.json', 'summary.json', 'run_metadata.json'):
        if path(name).exists():
            raise FileExistsError(path(name))
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


METRICS = ('loss', 'image_rms', 'state_rms', 'image_state_ratio', 'stem_rms',
           'middle_rms', 'late_rms', 'embedding_rms', 'image_parameter_rms', 'state_parameter_rms')


def verify_results(root=OUTPUT, source=p29.OUTPUT):
    """Verify existing results and calculate depth attenuation, with no model run."""
    root, source = Path(root), Path(source)
    metadata = json.loads((root / 'run_metadata.json').read_text())
    for name, expected in metadata['artifacts'].items():
        if Path(name).name != name or step6.sha256(root / name) != expected:
            raise ValueError('P2.10 artifact identity mismatch: ' + name)
    records = json.loads((root / 'records.json').read_text())
    summary = json.loads((root / 'summary.json').read_text())
    samples = json.loads((source / 'samples.json').read_text())
    cache_hash = step6.sha256(source / 'samples.npz')
    if any(x != cache_hash for x in (samples['cache_sha256'], summary['sample_cache_sha256'],
                                     metadata['sample_cache_sha256'])):
        raise ValueError('sample cache identity mismatch')
    if len(records) != 54 or len(samples['samples']) != 18:
        raise ValueError('incomplete coverage')
    if summary['seeds'] != list(SEEDS) or metadata['seeds'] != list(SEEDS):
        raise ValueError('seed identity mismatch')
    if any(doc['status'] != 'complete' or doc['records'] != 54 or
           doc['optimizer_created'] is not False or doc['training_steps'] != 0
           for doc in (summary, metadata)):
        raise ValueError('incomplete/no-update contract failed')
    identities = summary['identities']
    if (len(identities) != 3 or {i['seed'] for i in identities} != set(SEEDS) or
            len({i['weight_hash'] for i in identities}) != 3 or
            any(i['training_steps'] != 0 or i['all_weight_hashes_unchanged'] is not True
                or i['trainable_parameters'] != 13039435 for i in identities)):
        raise ValueError('fresh control identity contract failed')
    seen = set()
    for rec in records:
        key = (rec['seed'], rec['sample'])
        if key in seen or rec['seed'] not in SEEDS or not 0 <= rec['sample'] < 18:
            raise ValueError('duplicate/invalid sample')
        seen.add(key)
        sample = samples['samples'][rec['sample']]
        if rec['condition'] != 'original' or any(rec[k] != sample[k] for k in ('domain','stratum','pair')):
            raise ValueError('sample provenance mismatch')
        if any(not math.isfinite(rec[k]) or rec[k] < 0 for k in METRICS):
            raise ValueError('nonfinite/invalid metrics')
    table = []
    for seed in SEEDS:
        selected = [r for r in records if r['seed'] == seed]
        values = summary['aggregates'][str(seed)]
        for key in METRICS:
            if not math.isclose(float(np.median([r[key] for r in selected])), values[key], rel_tol=1e-12):
                raise ValueError('aggregate mismatch: ' + key)
        table.append({'model': 'fresh_' + str(seed), **values})
    trained = json.loads((source / 'summary.json').read_text())
    for role in ('final', 'best'):
        values = trained['aggregates'][role]['overall']['original']
        table.append({'model': role, **{k: v['median'] for k,v in values.items()}})
    for row in table:
        row['top_to_stem_ratio'] = row['late_rms'] / row['stem_rms']
        row['top_to_input_ratio'] = row['late_rms'] / row['image_rms']
        row['top_to_stem_orders'] = math.log10(row['top_to_stem_ratio'])
        row['top_to_input_orders'] = math.log10(row['top_to_input_ratio'])
    return {'status': 'PASS', 'records': 54, 'samples': 18, 'table': table,
            'classification': 'P2.10-A', 'diagnostic_investigation': 'closed',
            'caveat': 'Ratios of medians describe attenuation; controls are not historical initial weights.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('snapshot', 'run', 'verify', 'verify-results'))
    args = parser.parse_args()
    action = {'snapshot': lambda: integrity(True), 'run': run, 'verify': integrity,
              'verify-results': verify_results}[args.command]
    print(json.dumps(action(), indent=2))


if __name__ == '__main__':
    main()
