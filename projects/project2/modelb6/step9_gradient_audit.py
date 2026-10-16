"""P2.9 supervised gradients with the actual professor loss; never update weights."""
import argparse
import csv
import json
from pathlib import Path
import time

import cv2
import h5py
import numpy as np
import tensorflow as tf

import step6
import step7_sensitivity as s7
import step8_encoder_audit as s8
from corrections import corrected_datagen
from step5_data import SOURCE_ROOT, DERIVED_ROOT, TEACHER, split_config, validate_all
from train_modelB6 import custom_loss

OUTPUT = Path('/output/p29-gradient-audit')
MONITOR = ('stem_activation', 'block1b_add', 'block3c_add', 'block4d_add',
           'block5d_add', 'block6e_add', 'block7b_add', 'top_activation', 'flatten',
           'concatenate', 'dense_2', 'activation_1', 'dense_3', 'dense_4', 'dense_5',
           'dense_6', 'dense_7', 'dense_8', 'dense_9', 'add', 'add_1', 'add_2', 'add_3')
STATE_LAYERS = ('dense_3', 'dense_4', 'dense_5', 'dense_6')
CONDITIONS = ('original', 'zero_state', 'mismatched_state', 'zero_image')


def target(name):
    p = (OUTPUT / name).resolve()
    p.relative_to(OUTPUT.resolve())
    return p


def write(name, value):
    p = target(name)
    if p.exists():
        raise FileExistsError(p)
    step6.write_json(p, value)


def inventory():
    result = s8.protected_inventory()
    for p in sorted(s8.OUTPUT.rglob('*')):
        if p.is_file():
            result[str(p)] = {'bytes': p.stat().st_size, 'sha256': step6.sha256(p)}
    return result


def integrity(snapshot=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    current = inventory()
    if snapshot:
        write('integrity_before.json', current)
        return {'status': 'snapshot', 'files': len(current)}
    previous = json.loads(target('integrity_before.json').read_text())
    changed = sorted(k for k in previous.keys() & current.keys() if previous[k] != current[k])
    added = sorted(current.keys() - previous.keys())
    missing = sorted(previous.keys() - current.keys())
    if changed or added or missing:
        raise RuntimeError(json.dumps({'changed': changed, 'added': added, 'missing': missing}))
    return {'status': 'PASS', 'files': len(current), 'changed': 0, 'added': 0, 'missing': 0}


def sample_indices(count):
    # Match corrected_datagen's actual batch-2 range, including its end trimming.
    rows = [i + b for i in range(0, count - 4, 2) for b in range(2)]
    if len(rows) < 10:
        raise ValueError('short sequence')
    old = s7.selected_indices(count)
    return [0, 1, old[1], old[2], old[3], rows[-1]]


def grad_stats(arrays):
    if not isinstance(arrays, (list, tuple)):
        arrays = [arrays]
    if not arrays or any(a is None for a in arrays):
        raise ValueError('disconnected gradient')
    n = 0
    total_abs = total_square = 0.0
    maximum = 0.0
    zeros = tiny = 0
    shapes = []
    for array in arrays:
        a = np.asarray(array, dtype=np.float64)
        if not a.size or not np.isfinite(a).all():
            raise ValueError('empty/nonfinite gradient')
        shapes.append(list(a.shape))
        n += a.size
        total_abs += float(np.abs(a).sum())
        total_square += float(np.square(a).sum())
        maximum = max(maximum, float(np.abs(a).max()))
        zeros += int(np.count_nonzero(a == 0))
        tiny += int(np.count_nonzero(np.abs(a) < 1e-12))
    return {'shapes': shapes, 'elements': n, 'mean_abs': total_abs / n,
            'rms': float(np.sqrt(total_square / n)), 'l2': float(np.sqrt(total_square)),
            'max_abs': maximum, 'zero_fraction': zeros / n, 'below_1e-12_fraction': tiny / n}


def ratio(a, b):
    return a / b if b != 0 else None


def components(y, p):
    return {name: float(tf.reduce_mean(tf.square(p[:, lo:hi] - y[:, lo:hi])).numpy())
            for name, lo, hi in (('path', 0, 384), ('left_lane', 385, 769),
                                ('right_lane', 771, 1155), ('all', 0, 2383))}


def dependency(previous, current):
    if previous is None:
        return {'sequence_start': True}
    a, b = previous[1871:].astype(np.float64), current[1871:].astype(np.float64)
    return {'sequence_start': False,
            'previous_state_to_current_state_mae': float(np.mean(np.abs(a - b))),
            'state_copy_mse': float(np.mean(np.square(a - b))),
            'state_zero_mse': float(np.mean(np.square(b))),
            'state_cosine': ratio(float(a @ b), float(np.linalg.norm(a) * np.linalg.norm(b))),
            'previous_target_custom_loss': float(custom_loss(current[None], previous[None]).numpy()[0]),
            'zero_target_custom_loss': float(custom_loss(current[None], np.zeros_like(current[None])).numpy()[0])}


def prepare():
    if target('samples.json').exists():
        raise FileExistsError('sample cache exists')
    if not target('integrity_before.json').exists():
        raise RuntimeError('snapshot required')
    started = time.monotonic()
    preflight = s7.preflight()
    markers = validate_all()
    images, states, labels, rows = [], [], [], []
    config = split_config()
    sequences = [('usa_train', next(n for n in config['train_sequences'] if n.endswith('--37'))),
                 ('usa_validation', config['validation_sequences'][0])]
    for stratum, name in sequences:
        source = SOURCE_ROOT / name / 'yuv.h5'
        label = DERIVED_ROOT / name / 'outSC.h5'
        with h5py.File(source, 'r') as f:
            count = len(f['X'])
        chosen = sample_indices(count)
        stream = corrected_datagen([str(source)], 1, SOURCE_ROOT, DERIVED_ROOT)
        row_index = 0
        with h5py.File(label, 'r') as f:
            for batch in stream:
                y = np.hstack(batch[4:])
                for b in range(2):
                    if row_index in chosen:
                        prev = f['X'][row_index - 1] if row_index else None
                        expected_state = prev[1871:] if prev is not None else np.zeros(512, np.float32)
                        np.testing.assert_array_equal(batch[3][b], expected_state)
                        np.testing.assert_array_equal(y[b], f['X'][row_index])
                        images.append(batch[0][b]); states.append(batch[3][b]); labels.append(y[b])
                        rows.append({'domain': 'usa', 'stratum': stratum, 'sequence': name,
                                     'pair': [row_index, row_index + 1], 'state_target_row': row_index - 1 if row_index else None,
                                     'frame_count': count, 'target_origin': 'existing_P2.5_teacher_labels',
                                     'dependency': dependency(prev, y[b])})
                    row_index += 1
                if row_index > max(chosen):
                    break
        stream.close()
    # Match teacher.predict to direct inference on already validated local labels.
    teacher = tf.keras.models.load_model(str(TEACHER), compile=False)
    teacher_hash = step6.sha256(TEACHER)
    probe = [images[0][None], np.zeros((1, 8), np.float32), np.array([[1., 0.]], np.float32), states[0][None]]
    prediction = np.hstack([x.numpy() for x in teacher(probe, training=False)])[0]
    np.testing.assert_allclose(prediction, labels[0], rtol=1e-4, atol=1e-4)
    predict_api = np.hstack(teacher.predict(probe, verbose=0))[0]
    np.testing.assert_allclose(prediction, predict_api, rtol=1e-4, atol=1e-4)
    teacher_api_difference = s7.metrics(prediction, predict_api)
    teacher_before = [s7.array_hash(w.numpy()) for w in teacher.weights]
    count = s7.COUNTS['taiwan']
    chosen = sample_indices(count)
    cap = cv2.VideoCapture(step6.SOURCES['taiwan'])
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError('Taiwan source decode failed')
    previous_image = step6.preprocess(frame)
    state = np.zeros((1, 512), np.float32)
    previous_target = None
    decoded = 1
    for index in range(count - 1):
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError('Taiwan frame count disagrees with P2.7')
        decoded += 1
        current_image = step6.preprocess(frame)
        image = np.vstack((previous_image, current_image))[None]
        teacher_inputs = [image, np.zeros((1, 8), np.float32), np.array([[1., 0.]], np.float32), state]
        y = np.hstack([x.numpy() for x in teacher(teacher_inputs, training=False)]).astype(np.float32)
        step6.split_output(y)
        if index in chosen:
            images.append(image[0]); states.append(state[0].copy()); labels.append(y[0].copy())
            rows.append({'domain': 'taiwan', 'stratum': 'taiwan_teacher_extension', 'sequence': step6.SOURCES['taiwan'],
                         'pair': [index, index + 1], 'state_target_row': index - 1 if index else None,
                         'frame_count': count, 'target_origin': 'P2.9_frozen_teacher_causal_rollout',
                         'dependency': dependency(previous_target, y[0])})
        state = y[:, 1871:].copy()
        previous_target = y[0].copy()
        previous_image = current_image
        if index % 300 == 0:
            print(json.dumps({'teacher_pair': index}), flush=True)
    if cap.read()[0]:
        raise RuntimeError('Taiwan decoded count unexpectedly greater')
    cap.release()
    if teacher_before != [s7.array_hash(w.numpy()) for w in teacher.weights]:
        raise RuntimeError('teacher changed')
    # Fixed within-sequence rotation by three selected samples preserves real state scale.
    for start in range(0, len(rows), 6):
        for offset in range(6):
            rows[start + offset]['mismatched_state_sample'] = start + ((offset + 3) % 6)
    arrays = {'images': np.asarray(images, np.float32), 'states': np.asarray(states, np.float32),
              'targets': np.asarray(labels, np.float32)}
    for key, value in arrays.items():
        if not np.isfinite(value).all():
            raise ValueError('nonfinite sample ' + key)
    np.savez_compressed(target('samples.npz'), **arrays)
    for index, row in enumerate(rows):
        row.update({'sample': index, 'image_sha256': s7.array_hash(arrays['images'][index]),
                    'state_sha256': s7.array_hash(arrays['states'][index]),
                    'target_sha256': s7.array_hash(arrays['targets'][index])})
    metadata = {'status': 'complete', 'samples': rows, 'preflight': preflight,
                'teacher_sha256': teacher_hash, 'teacher_predict_api_difference': teacher_api_difference,
                'source_marker_sha256': {m['sequence']: m['label_sha256'] for m in markers},
                'cache_sha256': step6.sha256(target('samples.npz')),
                'taiwan_decoded_frames': decoded, 'runtime_seconds': time.monotonic() - started}
    write('samples.json', metadata)
    return {'status': 'complete', 'samples': len(rows), 'runtime_seconds': metadata['runtime_seconds']}


def variant(image, state, condition, replacement):
    image, state = image.copy(), state.copy()
    if condition == 'zero_state': state.fill(0)
    elif condition == 'mismatched_state': state = replacement.copy()
    elif condition == 'zero_image': image.fill(0)
    elif condition != 'original': raise ValueError(condition)
    return image, state


def audit_one(model, probe, image, state, y):
    x = tf.convert_to_tensor(image[None]); st = tf.convert_to_tensor(state[None])
    y = tf.convert_to_tensor(y[None])
    with tf.GradientTape() as tape:
        tape.watch([x, st])
        outputs = probe([x, tf.zeros((1, 8)), tf.constant([[1., 0.]]), st], training=True)
        prediction, activations = outputs[0], outputs[1:]
        loss = tf.reduce_mean(custom_loss(y, prediction))
    sources = [x, st] + activations + model.trainable_weights
    gradients = tape.gradient(loss, sources)
    if any(g is None for g in gradients):
        raise RuntimeError('disconnected gradient collection')
    if not np.isfinite(float(loss.numpy())):
        raise ValueError('nonfinite loss')
    input_stats = {'image': grad_stats(gradients[0]), 'state': grad_stats(gradients[1])}
    for name, value in (('image', image), ('state', state)):
        input_stats[name]['input_rms'] = grad_stats(value)['rms']
        input_stats[name]['rms_times_input_rms'] = input_stats[name]['rms'] * input_stats[name]['input_rms']
    activation_stats = {name: grad_stats(g) for name, g in zip(MONITOR, gradients[2:2 + len(MONITOR)])}
    fusion = gradients[2 + MONITOR.index('concatenate')]
    for name, lo, hi in (('fusion_desire', 0, 8), ('fusion_traffic', 8, 10), ('fusion_image', 10, 1034)):
        activation_stats[name] = grad_stats(fusion[:, lo:hi])
    parameters = gradients[2 + len(MONITOR):]
    positions = {w.ref(): i for i, w in enumerate(model.trainable_weights)}
    image_layer_names = {l.name for l in model.layers if l.name.startswith(('stem_', 'block', 'top_')) or l.name in ('conv2d', 'activation', 'flatten')}
    groups = {'image_encoder': [], 'image_kernels': [], 'image_biases': [],
              'state_projection': [], 'recurrent_all': [], 'fusion_dense': [], 'heads': []}
    layer_stats = {}
    for layer in model.layers:
        if not layer.trainable_weights: continue
        ids = [positions[w.ref()] for w in layer.trainable_weights]
        g = [parameters[i] for i in ids]
        layer_stats[layer.name] = grad_stats(g)
        layer_stats[layer.name]['variables'] = {w.name: grad_stats(parameters[i]) for w, i in zip(layer.trainable_weights, ids)}
        layer_stats[layer.name]['weight_rms'] = grad_stats(layer.trainable_weights)['rms']
        layer_stats[layer.name]['gradient_rms_over_weight_rms'] = ratio(layer_stats[layer.name]['rms'], layer_stats[layer.name]['weight_rms'])
        if layer.name in image_layer_names:
            groups['image_encoder'].extend(ids)
            for w, i in zip(layer.trainable_weights, ids):
                groups['image_biases' if 'bias' in w.name else 'image_kernels'].append(i)
        elif layer.name == 'dense_2': groups['fusion_dense'].extend(ids)
        elif layer.name in tuple('dense_' + str(i) for i in range(3, 11)): groups['recurrent_all'].extend(ids)
        else: groups['heads'].extend(ids)
        if layer.name in STATE_LAYERS: groups['state_projection'].extend(ids)
    group_stats = {name: grad_stats([parameters[i] for i in ids]) for name, ids in groups.items()}
    comp = components(y, prediction)
    np.testing.assert_allclose(float(loss.numpy()), sum(comp[k] * w for k, w in zip(('path', 'left_lane', 'right_lane', 'all'), (.3, .3, .3, .1))), rtol=1e-5)
    return {'loss': float(loss.numpy()), 'loss_components': comp, 'input_gradients': input_stats,
            'activation_gradients': activation_stats, 'parameter_layers': layer_stats, 'parameter_groups': group_stats,
            'image_state_rms_ratio': ratio(input_stats['image']['rms'], input_stats['state']['rms']),
            'image_state_parameter_rms_ratio': ratio(group_stats['image_encoder']['rms'], group_stats['state_projection']['rms'])}


def distribution(values):
    a = np.asarray([x for x in values if x is not None], np.float64)
    if not len(a): return {'count': 0}
    return {'count': len(a), 'mean': float(a.mean()), 'median': float(np.median(a)),
            'min': float(a.min()), 'max': float(a.max())}


def flat_row(record):
    return {**{k: record[k] for k in ('role', 'domain', 'stratum', 'sample', 'condition', 'loss')},
        'pair_start': record['pair'][0], 'image_rms': record['input_gradients']['image']['rms'],
        'state_rms': record['input_gradients']['state']['rms'], 'image_state_ratio': record['image_state_rms_ratio'],
        'image_parameter_rms': record['parameter_groups']['image_encoder']['rms'],
        'state_parameter_rms': record['parameter_groups']['state_projection']['rms'],
        'stem_rms': record['activation_gradients']['stem_activation']['rms'],
        'middle_rms': record['activation_gradients']['block4d_add']['rms'],
        'late_rms': record['activation_gradients']['top_activation']['rms'],
        'embedding_rms': record['activation_gradients']['flatten']['rms']}


def csv_write(name, rows):
    with target(name).open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def run():
    if target('summary.json').exists() or target('records.json').exists():
        raise FileExistsError('audit already recorded')
    meta = json.loads(target('samples.json').read_text())
    if step6.sha256(target('samples.npz')) != meta['cache_sha256']:
        raise RuntimeError('sample cache changed')
    data = np.load(target('samples.npz'), allow_pickle=False)
    started = time.monotonic()
    records, identities, sanity = [], {}, {}
    for role in step6.MODELS:
        tf.keras.backend.clear_session()
        model, identities[role] = step6.load_model_for_role(role)
        if model.losses or any('dropout' in type(l).__name__.lower() or 'normalization' in type(l).__name__.lower() for l in model.layers):
            raise RuntimeError('unaccounted regularization/stochastic stateful layer')
        if not all(w.trainable for w in model.trainable_weights): raise RuntimeError('unexpected frozen weights')
        before = [s7.array_hash(w.numpy()) for w in model.weights]
        probe = tf.keras.Model(model.inputs, [model.output] + [model.get_layer(n).output for n in MONITOR])
        original_input = s7.inputs(data['images'][1][None], traffic=np.array([[1., 0.]], np.float32), state=data['states'][1][None])
        np.testing.assert_array_equal(model(list(original_input), training=True).numpy(), model(list(original_input), training=False).numpy())
        for index, sample in enumerate(meta['samples']):
            for condition in CONDITIONS:
                replacement = data['states'][sample['mismatched_state_sample']]
                image, state = variant(data['images'][index], data['states'][index], condition, replacement)
                rec = audit_one(model, probe, image, state, data['targets'][index])
                rec.update({k: sample[k] for k in ('domain', 'stratum', 'sample', 'pair')})
                rec.update({'role': role, 'condition': condition,
                            'image_sha256': s7.array_hash(image), 'state_sha256': s7.array_hash(state),
                            'target_sha256': s7.array_hash(data['targets'][index]),
                            'baseline_state_nonzero': bool(np.any(data['states'][index]))})
                records.append(rec)
            print(json.dumps({'role': role, 'sample_done': index}), flush=True)
        # Repeat after other trials verifies no gradient-buffer accumulation.
        repeated = audit_one(model, probe, data['images'][1], data['states'][1], data['targets'][1])
        first = next(r for r in records if r['role'] == role and r['sample'] == 1 and r['condition'] == 'original')
        if repeated['input_gradients'] != first['input_gradients'] or repeated['loss'] != first['loss']:
            raise RuntimeError('repeated audit differs')
        xb = tf.convert_to_tensor(data['images'][:2]); sb = tf.convert_to_tensor(data['states'][:2])
        with tf.GradientTape() as tape:
            tape.watch([xb, sb])
            yp = model([xb, tf.zeros((2,8)), tf.constant([[1.,0.],[1.,0.]]), sb], training=True)
            batch_loss = tf.reduce_mean(custom_loss(data['targets'][:2], yp))
        batch_gradients = tape.gradient(batch_loss, [xb, sb])
        singles = [next(r for r in records if r['role'] == role and r['sample'] == i and r['condition'] == 'original') for i in range(2)]
        np.testing.assert_allclose(float(batch_loss.numpy()), np.mean([r['loss'] for r in singles]), rtol=1e-4)
        for i, single in enumerate(singles):
            for name, gradient in zip(('image','state'), batch_gradients):
                np.testing.assert_allclose(grad_stats(gradient[i])['rms'], single['input_gradients'][name]['rms']/2, rtol=1e-3, atol=1e-30)
        if before != [s7.array_hash(w.numpy()) for w in model.weights]: raise RuntimeError('model weights changed')
        sanity[role] = {'all_weight_hashes_unchanged': True, 'repeat_gradients_exact': True,
                        'training_true_false_outputs_equal': True, 'batch2_per_sample_gradients_match': True,
                        'trainable_parameters': int(sum(np.prod(w.shape) for w in model.trainable_weights))}
    write('records.json', records)
    rows = [flat_row(r) for r in records]
    csv_write('per_sample_gradients.csv', rows)
    layer_rows = []
    for r in records:
        for name, g in r['activation_gradients'].items():
            layer_rows.append({'role': r['role'], 'domain': r['domain'], 'sample': r['sample'], 'condition': r['condition'],
                               'tensor': name, **{k: v for k, v in g.items() if k != 'shapes'}})
    csv_write('layer_gradient_profile.csv', layer_rows)
    contrasts = []
    for role in step6.MODELS:
        for index, sample in enumerate(meta['samples']):
            cell = {r['condition']: r for r in records if r['role'] == role and r['sample'] == index}
            a = cell['original']
            for condition in CONDITIONS[1:]:
                b = cell[condition]
                contrasts.append({'role': role, 'domain': sample['domain'], 'stratum': sample['stratum'], 'sample': index,
                                  'condition': condition, 'nonzero_history': a['baseline_state_nonzero'],
                                  'original_loss': a['loss'], 'counterfactual_loss': b['loss'],
                                  'loss_ratio': ratio(b['loss'], a['loss']),
                                  'original_image_rms': a['input_gradients']['image']['rms'],
                                  'counterfactual_image_rms': b['input_gradients']['image']['rms'],
                                  'image_gradient_amplification': ratio(b['input_gradients']['image']['rms'], a['input_gradients']['image']['rms'])})
    csv_write('counterfactual_gradients.csv', contrasts)
    aggregates = {}
    for role in step6.MODELS:
        aggregates[role] = {}
        for scope in ('overall', 'usa', 'taiwan', 'usa_train', 'usa_validation'):
            aggregates[role][scope] = {}
            for condition in CONDITIONS:
                selected = [r for r in rows if r['role'] == role and r['condition'] == condition and
                            (scope == 'overall' or r['domain'] == scope or r['stratum'] == scope)]
                aggregates[role][scope][condition] = {k: distribution([r[k] for r in selected])
                    for k in ('loss', 'image_rms', 'state_rms', 'image_state_ratio', 'image_parameter_rms',
                              'state_parameter_rms', 'stem_rms', 'middle_rms', 'late_rms', 'embedding_rms')}
    contrast_summary = {role: {condition: {k: distribution([r[k] for r in contrasts if r['role'] == role and
                       r['condition'] == condition and r['nonzero_history']])
                       for k in ('loss_ratio', 'image_gradient_amplification')}
                       for condition in CONDITIONS[1:]} for role in step6.MODELS}
    summary = {'status': 'complete', 'aggregates': aggregates, 'nonzero_history_counterfactuals': contrast_summary,
               'records': len(records), 'samples': len(meta['samples']), 'sanity': sanity,
               'runtime_seconds': time.monotonic() - started}
    write('summary.json', summary)
    csv_write('checkpoint_comparison.csv', [{'role': role, 'scope': scope, 'condition': condition,
        **{k: v['median'] for k, v in metrics.items()}}
        for role, scopes in aggregates.items() for scope, conditions in scopes.items() for condition, metrics in conditions.items()])
    write('run_metadata.json', {'status': 'complete', 'tensorflow': tf.__version__, 'models': identities,
          'loss_source': '/workspace/professor/train_modelB6.py:custom_loss',
          'loss_sha256': step6.sha256('/workspace/professor/train_modelB6.py'),
          'loss_weights': [.3, .3, .3, .1], 'loss_bounds': [[0,384],[385,769],[771,1155],[0,2383]],
          'traffic': [1,0], 'desire': 'zero', 'training': True, 'optimizer_created': False,
          'gradient_reduction': 'mean original custom_loss for one sample; no cross-sample layers; 2x its contribution to an original batch of two',
          'state_gradient': 'teacher state treated as an independent input, as in numpy training stream',
          'artifacts': {p.name: step6.sha256(p) for p in OUTPUT.iterdir() if p.is_file()}, 'sanity': sanity})
    return {'status': 'complete', 'records': len(records), 'runtime_seconds': summary['runtime_seconds']}


def component_probe():
    if target('component_gradients.json').exists(): raise FileExistsError('component probe exists')
    data = np.load(target('samples.npz'), allow_pickle=False)
    metadata = json.loads(target('samples.json').read_text())
    if step6.sha256(target('samples.npz')) != metadata['cache_sha256']: raise RuntimeError('cache changed')
    records = []
    started = time.monotonic()
    for role in step6.MODELS:
        tf.keras.backend.clear_session()
        model, identity = step6.load_model_for_role(role)
        probe = tf.keras.Model(model.inputs, [model.output, model.get_layer('flatten').output])
        before = [s7.array_hash(w.numpy()) for w in model.weights]
        for index in (2, 8, 14):
            for condition in ('original', 'zero_state'):
                x = tf.convert_to_tensor(data['images'][index:index+1])
                state = tf.convert_to_tensor(data['states'][index:index+1] if condition == 'original' else np.zeros((1,512),np.float32))
                truth = tf.convert_to_tensor(data['targets'][index:index+1])
                with tf.GradientTape(persistent=True) as tape:
                    tape.watch([x,state])
                    prediction, embedding = probe([x,tf.zeros((1,8)),tf.constant([[1.,0.]]),state],training=True)
                    terms = {name: weight*tf.reduce_mean(tf.square(prediction[:,lo:hi]-truth[:,lo:hi]))
                             for name,lo,hi,weight in (('path',0,384,.3),('left_lane',385,769,.3),('right_lane',771,1155,.3),('all',0,2383,.1))}
                    total = tf.reduce_mean(custom_loss(truth,prediction))
                total_gradients = tape.gradient(total,[x,state,embedding])
                term_results = {}
                accum = [np.zeros_like(g.numpy()) for g in total_gradients]
                for name,value in terms.items():
                    gradients = tape.gradient(value,[x,state,embedding])
                    term_results[name] = {'weighted_loss':float(value.numpy()),
                                         **{n:grad_stats(g) for n,g in zip(('image','state','embedding'),gradients)}}
                    for j,g in enumerate(gradients): accum[j] += g.numpy()
                residual = {}
                for name,actual,expected in zip(('image','state','embedding'),accum,total_gradients):
                    err=grad_stats(actual-expected.numpy())['rms']
                    scale=grad_stats(expected)['rms']
                    if err > max(1e-25,scale*1e-3): raise RuntimeError('component gradient sum disagrees')
                    residual[name]=ratio(err,scale)
                del tape
                records.append({'role':role,'model_sha256':identity['sha256'],'sample':index,
                                'stratum':metadata['samples'][index]['stratum'],'condition':condition,
                                'terms':term_results,'gradient_sum_relative_rms_error':residual})
        if before != [s7.array_hash(w.numpy()) for w in model.weights]: raise RuntimeError('weights changed')
    write('component_gradients.json',{'status':'complete','records':records,'runtime_seconds':time.monotonic()-started,
                                     'all_model_weight_hashes_unchanged':True})
    return {'status':'complete','records':len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('snapshot', 'prepare', 'run', 'components', 'verify'))
    args = parser.parse_args()
    action = {'snapshot': lambda: integrity(True), 'prepare': prepare, 'run': run,
              'components': component_probe, 'verify': integrity}[args.command]
    print(json.dumps(action(), indent=2))


if __name__ == '__main__': main()
