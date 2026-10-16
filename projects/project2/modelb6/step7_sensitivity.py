"""P2.7 controlled, read-only sensitivity diagnostics for immutable ModelB6 weights."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import cv2
import numpy as np

import step6


OUTPUT = Path('/output/p27-sensitivity')
COUNTS = {'usa': 1200, 'taiwan': 1202}  # P2.6 sequential decode, never HEVC metadata
INPUT_NAMES = ('image', 'desire', 'traffic', 'state')
DESIRES = {'turn_left': 1, 'lane_change_left': 3}  # cereal/log.capnp ModelData.Desire
INTEGRITY_ROOTS = (Path('/workspace/professor'), Path('/data/dataB6'),
                   Path('/opt/openpilot/tools/replay/dataC'), Path('/derived/step5'),
                   Path('/output/step5'), Path('/output/step6'))


def selected_indices(count):
    if count < 18:
        raise ValueError('clip too short for deterministic sample and state windows')
    last = count - 2  # pair i,i+1; next-pair control requires i+2 except last
    return [0, last // 4, last // 2, (3 * last) // 4, last]


def output_target(path):
    target = Path(path).resolve()
    if target != OUTPUT and OUTPUT not in target.parents:
        raise ValueError('P2.7 may write only under ' + str(OUTPUT))
    return target


def array_hash(value):
    array = np.asarray(value)
    return hashlib.sha256(array.tobytes(order='C')).hexdigest()


def inputs(image, desire=None, traffic=None, state=None):
    values = (np.array(image, dtype=np.float32, copy=True),
              np.zeros((1, 8), np.float32) if desire is None else np.array(desire, dtype=np.float32, copy=True),
              np.zeros((1, 2), np.float32) if traffic is None else np.array(traffic, dtype=np.float32, copy=True),
              step6.zero_state() if state is None else np.array(state, dtype=np.float32, copy=True))
    if tuple(x.shape for x in values) != ((1, 12, 128, 256), (1, 8), (1, 2), (1, 512)):
        raise ValueError('invalid input shapes')
    if any(not np.isfinite(x).all() for x in values):
        raise ValueError('non-finite model input')
    return values


def intervention(base, factor, value):
    if factor not in INPUT_NAMES:
        raise ValueError('unknown input factor')
    index = INPUT_NAMES.index(factor)
    variant = list(inputs(*base))
    replacement = np.asarray(value, dtype=np.float32)
    if replacement.shape != variant[index].shape:
        raise ValueError('intervention shape changed')
    variant[index] = replacement.copy()
    changed = [name for name, old, new in zip(INPUT_NAMES, base, variant)
               if not np.array_equal(old, new)]
    if changed != [factor]:
        raise ValueError('intervention must change exactly ' + factor + ': ' + repr(changed))
    return tuple(variant)


def hashes(values):
    return dict(zip(INPUT_NAMES, (array_hash(x) for x in values)))


def metrics(base, changed):
    a, b = np.asarray(base, dtype=np.float64), np.asarray(changed, dtype=np.float64)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('non-finite or mismatched metric input')
    difference = b - a
    mae = float(np.mean(np.abs(difference)))
    denominator = max(float(np.mean(np.abs(a))), 1.0)
    return {'mae': mae, 'rms': float(np.sqrt(np.mean(difference * difference))),
            'max_abs': float(np.max(np.abs(difference))),
            'relative_to_max_baseline_mean_abs_or_1': mae / denominator,
            'baseline_mean_abs': float(np.mean(np.abs(a))),
            'different_values': int(np.count_nonzero(difference))}


def output_metrics(base, changed):
    step6.split_output(base)
    step6.split_output(changed)
    return {'full': metrics(base, changed),
            'sections': {name: metrics(base[:, lo:hi], changed[:, lo:hi])
                         for name, lo, hi in zip(step6.NAMES, step6.BOUNDS[:-1], step6.BOUNDS[1:])}}


def sample_frames(domain):
    count = COUNTS[domain]
    selected = selected_indices(count)
    need = set()
    for i in selected:
        need.update((i, i + 1))
        if i + 2 < count:
            need.add(i + 2)
        if i >= 8:
            need.update(range(i - 8, i + 2))
    quarter = selected[1]
    need.update(range(quarter, quarter + 13))  # 12 adjacent pairs
    frames = {}
    cap = cv2.VideoCapture(step6.SOURCES[domain])
    if not cap.isOpened():
        raise RuntimeError('video cannot open: ' + domain)
    try:
        for index in range(max(need) + 1):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('sequential decode ended at frame ' + str(index))
            if index in need:
                frames[index] = step6.preprocess(frame)
    finally:
        cap.release()
    return frames, selected


def pair(frames, index):
    result = np.vstack((frames[index], frames[index + 1]))[None]
    if result.shape != (1, 12, 128, 256):
        raise RuntimeError('pair geometry changed')
    return result


def predict(model, values):
    output = model(list(values), training=False).numpy()
    step6.split_output(output)
    return output


def one_hot(index):
    if index not in DESIRES.values():
        raise ValueError('unsupported Desire enum index')
    result = np.zeros((1, 8), np.float32)
    result[0, index] = 1.0
    return result


def inventory():
    records = {}
    for root in INTEGRITY_ROOTS:
        if not root.is_dir():
            raise FileNotFoundError(root)
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                records[str(path)] = {'link_target': str(path.readlink())}
            elif path.is_file():
                records[str(path)] = {'bytes': path.stat().st_size, 'sha256': step6.sha256(path)}
    return records


def integrity(command):
    output_target(OUTPUT).mkdir(parents=True, exist_ok=True)
    target = output_target(OUTPUT / 'integrity_before.json')
    current = inventory()
    if command == 'snapshot':
        if target.exists():
            raise FileExistsError(target)
        step6.write_json(target, current)
        return {'status': 'snapshot', 'files': len(current)}
    expected = json.loads(target.read_text())
    missing = sorted(set(expected) - set(current))
    added = sorted(set(current) - set(expected))
    changed = sorted(k for k in expected.keys() & current.keys() if expected[k] != current[k])
    result = {'status': 'PASS' if not (missing or added or changed) else 'FAIL',
              'files': len(current), 'missing': missing, 'added': added, 'changed': changed}
    if result['status'] != 'PASS':
        raise RuntimeError(json.dumps(result))
    return result


def preflight():
    import tensorflow as tf
    if tf.__version__ != '2.13.1':
        raise RuntimeError('TensorFlow changed: ' + tf.__version__)
    if step6.BOUNDS[-1] != 2383 or step6.BOUNDS != tuple(step6.TARGET_BOUNDS):
        raise RuntimeError('output sections changed')
    for root in (Path('/workspace/professor'), Path('/data'), Path('/opt/openpilot'), Path('/')):
        if not os.statvfs(root).f_flag & os.ST_RDONLY:
            raise RuntimeError('source/root writable: ' + str(root))
    for role in step6.MODELS:
        step6.model_identity(role)
    source = {domain: step6.video_identity(domain, count=False) for domain in COUNTS}
    return {'tensorflow': tf.__version__, 'models': {r: step6.model_identity(r) for r in step6.MODELS},
            'sources': source, 'sample_indices': {d: selected_indices(n) for d, n in COUNTS.items()},
            'source_mounts_read_only': True}


def record(model, base, modified, factor, label, context):
    before, after = hashes(base), hashes(modified)
    if [n for n in INPUT_NAMES if before[n] != after[n]] != [factor]:
        raise RuntimeError('input hash single-factor contract failed')
    started = time.monotonic()
    y0, y1 = predict(model, base), predict(model, modified)
    result = {'context': context, 'intervention': label, 'changed_input': factor,
              'baseline_input_sha256': before, 'intervention_input_sha256': after,
              'unchanged_inputs': [n for n in INPUT_NAMES if n != factor],
              'baseline_output_sha256': array_hash(y0), 'intervention_output_sha256': array_hash(y1),
              'metrics': output_metrics(y0, y1), 'runtime_seconds': time.monotonic() - started}
    return result


def sequential(model, frames, start, length=12):
    recurrent, reset = [], []
    state = step6.zero_state()
    state_norms = []
    for i in range(start, start + length):
        image = pair(frames, i)
        y_recurrent = predict(model, inputs(image, state=state))
        y_reset = predict(model, inputs(image))
        recurrent.append(y_recurrent)
        reset.append(y_reset)
        state = step6.next_state(step6.split_output(y_recurrent))
        state_norms.append(float(np.linalg.norm(state)))
    return {'frame_pairs': [[i, i + 1] for i in range(start, start + length)],
            'recurrent_vs_reset': [output_metrics(a, b) for a, b in zip(recurrent, reset)],
            'state_l2': state_norms,
            'state_frame_change_mae': [metrics(recurrent[i - 1][:, 1871:], recurrent[i][:, 1871:])['mae']
                                       for i in range(1, len(recurrent))]}


def run():
    if (OUTPUT / 'results.json').exists():
        raise FileExistsError('P2.7 results already exist')
    if not (OUTPUT / 'integrity_before.json').is_file():
        raise RuntimeError('take protected-input integrity snapshot first')
    started = time.monotonic()
    info = preflight()
    frames = {}
    selected = {}
    for domain in COUNTS:
        frames[domain], selected[domain] = sample_frames(domain)
    tensor_differences = []
    for ordinal in range(5):
        usa = pair(frames['usa'], selected['usa'][ordinal])
        taiwan = pair(frames['taiwan'], selected['taiwan'][ordinal])
        comparison = metrics(usa, taiwan)
        if comparison['mae'] < 1.0:
            raise RuntimeError('preprocessed cross-domain tensor near identity; inspect preprocessing')
        tensor_differences.append({'ordinal': ordinal,
                                   'usa_pair': [selected['usa'][ordinal], selected['usa'][ordinal] + 1],
                                   'taiwan_pair': [selected['taiwan'][ordinal], selected['taiwan'][ordinal] + 1],
                                   'usa_sha256': array_hash(usa), 'taiwan_sha256': array_hash(taiwan),
                                   'metrics': comparison})
    results = {'status': 'complete', 'category': 'controlled_inference_diagnostic',
               'ground_truth_accuracy': None, 'preflight': info,
               'tensor_cross_domain': tensor_differences, 'roles': {},
               'metric_definition': 'Raw MAE/RMS/max are primary; relative denominator=max(mean(abs(baseline)),1.0), independently per section.',
               'static_baseline': {'desire': 'zeros', 'traffic': [0, 0], 'state': 'zeros'},
               'desire_enum_source': '/opt/openpilot/cereal/log.capnp ModelData.Desire: turnLeft=1,laneChangeLeft=3'}
    for role in step6.MODELS:
        model, identity = step6.load_model_for_role(role)
        role_result = {'model': identity, 'domains': {}}
        for domain in COUNTS:
            indices = selected[domain]
            domain_result = {'selected_pairs': [[i, i + 1] for i in indices], 'records': [],
                             'static_baseline_output_sha256': []}
            for ordinal, index in enumerate(indices):
                image = pair(frames[domain], index)
                base = inputs(image)
                baseline_output = predict(model, base)
                domain_result['static_baseline_output_sha256'].append(array_hash(baseline_output))
                context = {'role': role, 'domain': domain, 'ordinal': ordinal,
                           'baseline_pair': [index, index + 1]}
                def add(factor, label, value, source_pair=None):
                    modified = intervention(base, factor, value)
                    local_context = dict(context)
                    if source_pair is not None:
                        local_context['replacement_pair'] = source_pair
                    domain_result['records'].append(record(model, base, modified, factor, label, local_context))
                other = indices[(ordinal + 1) % len(indices)]
                add('image', 'real_within_domain_swap', pair(frames[domain], other), [other, other + 1])
                other_domain = 'taiwan' if domain == 'usa' else 'usa'
                other_index = selected[other_domain][ordinal]
                add('image', 'real_cross_domain_swap', pair(frames[other_domain], other_index),
                    [other_index, other_index + 1])
                add('image', 'zero_image_OOD', np.zeros_like(image))
                add('image', 'constant_mean_image_OOD', np.full_like(image, float(image.mean())))
                add('image', 'duplicate_current_temporal_pair', np.vstack((image[0, 6:], image[0, 6:]))[None])
                add('image', 'reverse_temporal_pair', np.vstack((image[0, 6:], image[0, :6]))[None])
                add('traffic', 'step5_traffic_1_0', np.array([[1., 0.]], np.float32))
                for label, desire_index in DESIRES.items():
                    add('desire', label + '_one_hot', one_hot(desire_index))
                if index + 2 < COUNTS[domain]:
                    add('image', 'natural_next_pair', pair(frames[domain], index + 1), [index + 1, index + 2])
                if index >= 8:
                    state = step6.zero_state()
                    for prev in range(index - 8, index):
                        y = predict(model, inputs(pair(frames[domain], prev), state=state))
                        state = step6.next_state(step6.split_output(y))
                    add('state', 'real_preceding_8_pair_state', state)
            domain_result['closed_loop'] = sequential(model, frames[domain], indices[1])
            role_result['domains'][domain] = domain_result
        results['roles'][role] = role_result
        del model
    results['runtime_seconds'] = time.monotonic() - started
    output_target(OUTPUT).mkdir(parents=True, exist_ok=True)
    step6.write_json(output_target(OUTPUT / 'results.json'), results)
    return {'status': 'complete', 'path': str(OUTPUT / 'results.json'),
            'records': sum(len(d['records']) for r in results['roles'].values() for d in r['domains'].values()),
            'runtime_seconds': results['runtime_seconds']}


def verify():
    path = output_target(OUTPUT / 'results.json')
    result = json.loads(path.read_text())
    if result['status'] != 'complete' or set(result['roles']) != set(step6.MODELS):
        raise ValueError('incomplete P2.7 results')
    for role, data in result['roles'].items():
        if data['model']['sha256'] != step6.model_identity(role)['sha256']:
            raise ValueError('model identity changed')
        if set(data['domains']) != set(COUNTS):
            raise ValueError('domain coverage incomplete')
        for domain, cell in data['domains'].items():
            if cell['selected_pairs'] != [[i, i + 1] for i in selected_indices(COUNTS[domain])]:
                raise ValueError('sample indices changed')
            for row in cell['records']:
                changed = [n for n in INPUT_NAMES if row['baseline_input_sha256'][n] != row['intervention_input_sha256'][n]]
                if changed != [row['changed_input']]:
                    raise ValueError('multi-factor result')
                if not np.isfinite(row['metrics']['full']['mae']):
                    raise ValueError('non-finite result')
    return {'status': 'PASS', 'records': sum(len(d['records']) for r in result['roles'].values() for d in r['domains'].values())}


def probe_representation():
    """Locate where distinct images become indistinguishable; keep weights frozen."""
    import tensorflow as tf
    target = output_target(OUTPUT / 'representation_probe.json')
    if target.exists():
        raise FileExistsError(target)
    if not (OUTPUT / 'results.json').is_file():
        raise RuntimeError('controlled result required before representation probe')
    frames_usa, _ = sample_frames('usa')
    frames_taiwan, _ = sample_frames('taiwan')
    images = {'usa_quarter': pair(frames_usa, 299),
              'usa_middle': pair(frames_usa, 599),
              'taiwan_quarter': pair(frames_taiwan, 300)}
    images['zero_OOD'] = np.zeros_like(images['usa_quarter'])
    layers = ('stem_activation', 'block3b_activation', 'top_activation', 'flatten')
    result = {'status': 'complete', 'purpose': 'read-only localization of image response',
              'layers': layers, 'comparisons': {}, 'models': {},
              'image_input_metrics': {name: metrics(images['usa_quarter'], image)
                                      for name, image in images.items() if name != 'usa_quarter'}}
    for role in step6.MODELS:
        model, identity = step6.load_model_for_role(role)
        extractor = tf.keras.Model(inputs=model.inputs,
                                   outputs=[model.get_layer(name).output for name in layers])
        baseline = inputs(images['usa_quarter'])
        repeats = (predict(model, baseline), predict(model, baseline))
        activations = {name: extractor(inputs(image), training=False)
                       for name, image in images.items()}
        model_result = {'identity': identity, 'repeat_full_output': metrics(*repeats),
                        'layers': {}}
        for index, layer in enumerate(layers):
            reference = activations['usa_quarter'][index].numpy()
            model_result['layers'][layer] = {
                'baseline_mean_abs': float(np.mean(np.abs(reference))),
                'baseline_std': float(np.std(reference)),
                'comparison': {name: metrics(reference, values[index].numpy())
                               for name, values in activations.items() if name != 'usa_quarter'}}
        result['models'][role] = model_result
    output_target(OUTPUT).mkdir(parents=True, exist_ok=True)
    step6.write_json(target, result)
    return {'status': 'complete', 'path': str(target)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight', 'snapshot', 'run', 'probe', 'verify', 'integrity-verify'))
    command = parser.parse_args().command
    action = {'preflight': preflight, 'snapshot': lambda: integrity('snapshot'),
              'run': run, 'probe': probe_representation, 'verify': verify,
              'integrity-verify': lambda: integrity('verify')}[command]
    print(json.dumps(action(), indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
