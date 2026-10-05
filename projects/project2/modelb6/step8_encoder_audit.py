"""P2.8 frozen-weight encoder, input-scale and gradient investigation."""

import argparse
import json
import os
from pathlib import Path
import time

import h5py
import numpy as np
import tensorflow as tf

import step6
import step7_sensitivity as sensitivity

OUTPUT = Path('/output/p28-encoder-audit')
REFERENCE_SEED = 2801


def target(path):
    path = Path(path).resolve()
    if path != OUTPUT and OUTPUT not in path.parents:
        raise ValueError('P2.8 output must be under ' + str(OUTPUT))
    return path


def stats(array):
    value = np.asarray(array, dtype=np.float64)
    if not value.size or not np.isfinite(value).all():
        raise ValueError('empty or nonfinite array')
    return {'shape': list(value.shape), 'mean': float(value.mean()),
            'std': float(value.std()), 'rms': float(np.sqrt(np.mean(value * value))),
            'mean_abs': float(np.abs(value).mean()), 'max_abs': float(np.abs(value).max()),
            'min': float(value.min()), 'max': float(value.max()),
            'zero_fraction': float(np.mean(value == 0)),
            'negative_fraction': float(np.mean(value < 0)),
            'elu_negative_saturation_fraction': float(np.mean(value <= -0.999))}


def protected_inventory():
    records = sensitivity.inventory()
    if not sensitivity.OUTPUT.is_dir():
        raise FileNotFoundError(sensitivity.OUTPUT)
    for path in sorted(sensitivity.OUTPUT.rglob('*')):
        if path.is_file():
            records[str(path)] = {'bytes': path.stat().st_size, 'sha256': step6.sha256(path)}
    return records


def integrity(command):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = target(OUTPUT / 'integrity_before.json')
    current = protected_inventory()
    if command == 'snapshot':
        if path.exists():
            raise FileExistsError(path)
        step6.write_json(path, current)
        return {'status': 'snapshot', 'files': len(current)}
    baseline = json.loads(path.read_text())
    changed = sorted(k for k in baseline.keys() & current.keys() if baseline[k] != current[k])
    added = sorted(current.keys() - baseline.keys())
    missing = sorted(baseline.keys() - current.keys())
    result = {'status': 'PASS' if not (changed or added or missing) else 'FAIL',
              'files': len(current), 'changed': changed, 'added': added, 'missing': missing}
    if result['status'] != 'PASS':
        raise RuntimeError(json.dumps(result))
    return result


def encoder_layers(model):
    """Trace image-only graph before auxiliary inputs, retaining residual endpoints."""
    names = []
    for layer in model.layers:
        name = layer.name
        if (name in ('permute', 'stem_conv', 'stem_activation', 'top_conv',
                     'top_activation', 'conv2d', 'activation', 'flatten') or
                (name.startswith('block') and
                 (name.endswith('_activation') or name.endswith('_project_conv') or name.endswith('_add')))):
            names.append(name)
        if name == 'flatten':
            break
    if not names or names[-1] != 'flatten':
        raise ValueError('cannot locate image-only flatten endpoint')
    return names


def trace(model, images):
    records = []
    names = encoder_layers(model)
    # Chunk outputs so early high-resolution activations do not all remain in memory.
    for start in range(0, len(names), 8):
        chunk = names[start:start + 8]
        extractor = tf.keras.Model(model.inputs, [model.get_layer(n).output for n in chunk])
        values = {key: extractor(sensitivity.inputs(image), training=False)
                  for key, image in images.items()}
        for index, name in enumerate(chunk):
            baseline = values['usa_quarter'][index].numpy()
            records.append({'layer': name, 'class': model.get_layer(name).__class__.__name__,
                            'baseline': stats(baseline),
                            'comparisons': {key: sensitivity.metrics(baseline, output[index].numpy())
                                            for key, output in values.items() if key != 'usa_quarter'}})
    return records


def weight_stats(model):
    records = []
    for layer in model.layers:
        if not layer.weights:
            continue
        records.append({'layer': layer.name, 'class': layer.__class__.__name__,
                        'weights': [{'name': weight.name, 'stats': stats(weight.numpy()),
                                     'sha256': sensitivity.array_hash(weight.numpy())}
                                    for weight in layer.weights]})
    return records


def image_gradients(model, image):
    """Derivative of fixed scalar diagnostics; no optimizer, loss or weight update."""
    extractor = tf.keras.Model(model.inputs, [model.get_layer('flatten').output, model.output])
    x = tf.convert_to_tensor(image)
    auxiliary = [tf.convert_to_tensor(v) for v in sensitivity.inputs(image)[1:]]
    with tf.GradientTape(persistent=True, watch_accessed_variables=False) as tape:
        tape.watch(x)
        embedding, output = extractor([x] + auxiliary, training=False)
        scalar = {'embedding_mean_square': tf.reduce_mean(tf.square(embedding)),
                  'path_mean_square': tf.reduce_mean(tf.square(output[:, :385])),
                  'pose_mean_square': tf.reduce_mean(tf.square(output[:, 1859:1871])),
                  'state_mean_square': tf.reduce_mean(tf.square(output[:, 1871:]))}
    result = {}
    for name, objective in scalar.items():
        gradient = tape.gradient(objective, x)
        if gradient is None:
            raise RuntimeError('disconnected image gradient: ' + name)
        result[name] = {'objective': float(objective.numpy()), 'image_gradient': stats(gradient.numpy())}
    del tape
    return result


def input_scale_audit(frames):
    from step5 import stream_for_split
    from step5_data import SOURCE_ROOT
    records = []
    source = Path(step6.SOURCES['usa']).with_name('yuv.h5')
    with h5py.File(source, 'r') as stream:
        for index in (0, 299, 599):
            stored = np.vstack((stream['X'][index], stream['X'][index + 1]))[None].astype(np.float32)
            decoded = sensitivity.pair(frames, index)
            records.append({'pair': [index, index + 1],
                            'stored_vs_decoded': sensitivity.metrics(stored, decoded),
                            'stored': stats(stored), 'decoded': stats(decoded)})
    # Actual Step 5 stream, not a hand-written surrogate; reading generates no labels.
    names, generator = stream_for_split('train')
    batch = next(generator)
    with h5py.File(SOURCE_ROOT / names[0] / 'yuv.h5', 'r') as stream:
        expected = np.vstack((stream['X'][0], stream['X'][1])).astype(np.float32)
    if not np.array_equal(batch[0][0], expected):
        raise RuntimeError('actual training stream changes stored input scale or pairing')
    generator.close()
    return {'stored_video_pairs': records, 'training_sequences': names,
            'actual_training_image': stats(batch[0]),
            'training_first_pair_equals_stored': True,
            'training_traffic': batch[2].tolist(),
            'image_scaling': 'native float32 YUV pixel values; no division by 255 in training or inference'}


def run():
    result_path = target(OUTPUT / 'results.json')
    if result_path.exists():
        raise FileExistsError(result_path)
    if not (OUTPUT / 'integrity_before.json').is_file():
        raise RuntimeError('protected snapshot required')
    preflight = sensitivity.preflight()
    started = time.monotonic()
    usa, _ = sensitivity.sample_frames('usa')
    taiwan, _ = sensitivity.sample_frames('taiwan')
    images = {'usa_quarter': sensitivity.pair(usa, 299),
              'usa_middle': sensitivity.pair(usa, 599),
              'taiwan_quarter': sensitivity.pair(taiwan, 300)}
    images['zero_OOD'] = np.zeros_like(images['usa_quarter'])
    result = {'status': 'complete', 'tensorflow': tf.__version__, 'preflight': preflight,
              'input_scale': input_scale_audit(usa), 'models': {},
              'reference_caveat': 'Seeded fresh architecture reference is not the original P2.5 initialization; no reference weights are saved.',
              'scaled_input_caveat': 'Division by 255 is a diagnostic OOD scale intervention, not an approved correction.'}
    for role in ('final', 'best', 'fresh_reference'):
        tf.keras.backend.clear_session()
        if role == 'fresh_reference':
            tf.keras.utils.set_random_seed(REFERENCE_SEED)
            from modelB6 import get_model
            model = get_model()
            identity = {'role': role, 'seed': REFERENCE_SEED, 'training_steps': 0}
        else:
            model, identity = step6.load_model_for_role(role)
        before = [sensitivity.array_hash(w.numpy()) for w in model.weights]
        model_result = {'identity': identity, 'encoder_trace': trace(model, images),
                        'weight_stats': weight_stats(model),
                        'gradients': {domain: image_gradients(model, images[domain])
                                      for domain in ('usa_quarter', 'taiwan_quarter')}}
        native = sensitivity.predict(model, sensitivity.inputs(images['usa_quarter']))
        scaled = sensitivity.predict(model, sensitivity.inputs(images['usa_quarter'] / 255.0))
        native_cross = sensitivity.predict(model, sensitivity.inputs(images['taiwan_quarter']))
        scaled_cross = sensitivity.predict(model, sensitivity.inputs(images['taiwan_quarter'] / 255.0))
        model_result['scale_probe'] = {
            'native_vs_scaled_output': sensitivity.output_metrics(native, scaled),
            'native_cross_domain_output': sensitivity.output_metrics(native, native_cross),
            'scaled_cross_domain_output': sensitivity.output_metrics(scaled, scaled_cross)}
        after = [sensitivity.array_hash(w.numpy()) for w in model.weights]
        if before != after:
            raise RuntimeError('weights changed during read-only diagnostics')
        model_result['all_in_memory_weights_unchanged'] = True
        result['models'][role] = model_result
        print(json.dumps({'model_complete': role}), flush=True)
        del model
    result['runtime_seconds'] = time.monotonic() - started
    step6.write_json(result_path, result)
    return {'status': 'complete', 'path': str(result_path), 'runtime_seconds': result['runtime_seconds']}


def reference_controls():
    """Two independent fresh seeds address the single-reference limitation."""
    destination = target(OUTPUT / 'reference_controls.json')
    if destination.exists():
        raise FileExistsError(destination)
    if not (OUTPUT / 'results.json').is_file():
        raise RuntimeError('primary audit must complete first')
    started = time.monotonic()
    usa, _ = sensitivity.sample_frames('usa')
    taiwan, _ = sensitivity.sample_frames('taiwan')
    names = ('stem_activation', 'block3c_add', 'block4d_add', 'block5d_add',
             'block6e_add', 'block7b_add', 'top_activation', 'flatten')
    records = []
    for seed in (2802, 2803):
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(seed)
        from modelB6 import get_model
        model = get_model()
        extractor = tf.keras.Model(model.inputs, [model.get_layer(n).output for n in names])
        a = extractor(sensitivity.inputs(sensitivity.pair(usa, 299)), training=False)
        b = extractor(sensitivity.inputs(sensitivity.pair(taiwan, 300)), training=False)
        records.append({'seed': seed, 'training_steps': 0,
                        'layers': {n: {'baseline': stats(x.numpy()),
                                       'cross_domain': sensitivity.metrics(x.numpy(), y.numpy())}
                                   for n, x, y in zip(names, a, b)},
                        'depthwise': [{'layer': l.name, 'initializer': l.depthwise_initializer.get_config(),
                                       'kernel_shape': list(l.depthwise_kernel.shape),
                                       'kernel_rms': stats(l.depthwise_kernel.numpy())['rms']}
                                      for l in model.layers if isinstance(l, tf.keras.layers.DepthwiseConv2D)]})
    result = {'status': 'complete', 'tensorflow': tf.__version__, 'records': records,
              'runtime_seconds': time.monotonic() - started,
              'caveat': 'Fresh controls are not P2.5 historical initial weights; no weights saved or trained.'}
    step6.write_json(destination, result)
    return {'status': 'complete', 'path': str(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('snapshot', 'run', 'controls', 'verify'))
    command = parser.parse_args().command
    action = {'run': run, 'controls': reference_controls,
              'snapshot': lambda: integrity('snapshot'), 'verify': lambda: integrity('verify')}[command]
    print(json.dumps(action(), indent=2))


if __name__ == '__main__':
    main()
