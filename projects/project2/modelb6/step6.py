"""Student-owned, read-only ModelB6 Step 6 final/best × USA/Taiwan experiment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import cv2
import numpy as np

from corrections import TARGET_BOUNDS
from step5_preflight import EXPECTED_SHA256 as STEP5_HASHES


OUTPUT = Path('/output/step6')
BASELINE = Path('/output/step5/runs/p25-baseline-20261005')
PROFESSOR = Path('/workspace/professor')
MODELS = {
    'final': {'file': 'B6.keras', 'sha256': '7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03', 'bytes': 157259010},
    'best': {'file': 'B6BW.hdf5', 'sha256': '97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a', 'bytes': 157495320},
}
SOURCES = {
    'usa': '/data/dataB6/UHD--2018-08-02--08-34-47--37/video.hevc',
    'taiwan': '/opt/openpilot/tools/replay/dataC/8bfda98c9c9e4291|2020-05-11--03-00-57/61/fcamera.hevc',
}
# Professor Step 6 slide is authoritative over active parserB6.py constants.
# Offsets are ADDITIONAL to ±1.8 m lane anchors for left/right lanes.
CONFIGS = {
    'usa': {'start_point': 4, 'path_distance': 192, 'vanishing_x': 592.0,
            'vanishing_y': 379.0, 'camera_height_m': 1.4,
            'path_offset_m': 0.1, 'left_offset_m': 0.1, 'right_offset_m': -0.5,
            'traffic': [0.0, 0.0], 'source_role': 'step5_train',
            'warp': 'professor cameraB3.eon_intrinsics to OpenPilot medmodel_intrinsics'},
    'taiwan': {'start_point': 3, 'path_distance': 192, 'vanishing_x': 611.0,
               'vanishing_y': 397.0, 'camera_height_m': 1.2,
               'path_offset_m': 0.0, 'left_offset_m': -0.2, 'right_offset_m': -0.7,
               'traffic': [0.0, 0.0], 'source_role': 'out_of_training_domain',
               'warp': 'professor cameraB3.eon_intrinsics to OpenPilot medmodel_intrinsics'},
}
NAMES = ('path', 'left_lane', 'right_lane', 'lead', 'long_x', 'long_v', 'long_a',
         'desire_state', 'meta', 'desire_pred', 'pose', 'state')
BOUNDS = (0, 385, 771, 1157, 1215, 1415, 1615, 1815, 1823, 1827, 1859, 1871, 2383)
STEP6_HASHES = {
    'simulatorB6.py': 'c80ee5e6211faf59172bfb2dcab215b2adadb63cd585fe2b833725ece7b59e38',
    'parserB6.py': 'd24c15960c9df091fcf3ad1c1b44623d791747bb222c4b5e6fdbf2ee6724f839',
    'cameraB3.py': '6ecb51528096e6e4b0266350522bd94822709e25e92bf2354d21b6b8f9f87114',
    'lanes_image_space.py': '626e8fba1f224454c2a616214546ae7457f98176e471fc03bd00c8af0d19559a',
}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def within(path, root):
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path


def output_dir(domain, role, smoke=False):
    if domain not in CONFIGS or role not in MODELS:
        raise ValueError('unknown domain or model')
    return OUTPUT / ('smoke/' if smoke else '') / domain / role


def validated_output_dir(path):
    path = within(path, OUTPUT)
    if path == OUTPUT:
        raise ValueError('run needs a distinct output directory')
    return path


def model_identity(role):
    if role not in MODELS:
        raise ValueError(role)
    record = dict(MODELS[role])
    path = BASELINE / record['file']
    if not path.is_file() or path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
        raise RuntimeError('Step 5 model identity mismatch: ' + str(path))
    record.update({'role': role, 'path': str(path)})
    return record


def load_model_for_role(role):
    import tensorflow as tf
    from tensorflow.keras.models import load_model
    from modelB6 import get_model
    identity = model_identity(role)
    if tf.__version__ != '2.13.1':
        raise RuntimeError('TensorFlow runtime changed: ' + tf.__version__)
    model = load_model(identity['path'], compile=False) if role == 'final' else get_model()
    if role == 'best':
        model.load_weights(identity['path'])
    shapes = [tuple(int(d) for d in x.shape[1:]) for x in model.inputs]
    if shapes != [(12, 128, 256), (8,), (2,), (512,)]:
        raise RuntimeError('ModelB6 input contract changed: ' + repr(shapes))
    if tuple(model.output_shape) != (None, 2383):
        raise RuntimeError('ModelB6 output contract changed: ' + repr(model.output_shape))
    identity.update({'tensorflow': tf.__version__, 'inputs': [list(s) for s in shapes],
                     'output': [None, 2383]})
    return model, identity


def split_output(raw):
    raw = np.asarray(raw)
    if raw.shape != (1, 2383) or not np.isfinite(raw).all():
        raise ValueError('non-finite or malformed 2383 output: ' + repr(raw.shape))
    if BOUNDS != tuple(TARGET_BOUNDS) or len(BOUNDS) != len(NAMES) + 1:
        raise RuntimeError('student output boundaries disagree with training')
    return {name: raw[:, a:b] for name, a, b in zip(NAMES, BOUNDS[:-1], BOUNDS[1:])}


def parse_parts(parts, domain):
    """Keep raw slices intact; adapt only interpreted path/lane offsets."""
    import parserB6
    # Its log1p(exp(x)) overflows for finite x > ~88. Preserve the mathematical
    # softplus while evaluating it stably; never edit professor source on disk.
    original_softplus = parserB6.softplus
    parserB6.softplus = lambda x: np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0) + 1e-6
    try:
        parsed = parserB6.parser([parts[name] for name in NAMES])
    finally:
        parserB6.softplus = original_softplus
    for key, value in parsed.items():
        if not np.isfinite(value).all():
            raise ValueError('parser returned non-finite ' + key)
    for key in ('path', 'lll', 'rll', 'lead_xyva', 'lead_prob', 'long_x', 'long_v',
                'long_a', 'desire', 'meta', 'trans'):
        if key not in parsed:
            raise ValueError('parser omitted ' + key)
    if any(parsed[key].shape != (1, 192) for key in ('path', 'lll', 'rll')):
        raise ValueError('parser path/lane geometry changed')
    config = CONFIGS[domain]
    # Active parser uses path +0.1, left +1.8+0.1, right -1.8-0.1.
    parsed['path'] = parsed['path'] + (config['path_offset_m'] - 0.1)
    parsed['lll'] = parsed['lll'] + (config['left_offset_m'] - 0.1)
    parsed['rll'] = parsed['rll'] + (config['right_offset_m'] + 0.1)
    return parsed


def zero_state():
    return np.zeros((1, 512), dtype=np.float32)


def next_state(parts):
    state = np.asarray(parts['state'], dtype=np.float32)
    if state.shape != (1, 512) or not np.isfinite(state).all():
        raise ValueError('invalid recurrent state')
    return state.copy()


def project(lateral, domain):
    """Professor road-to-view transform at zero roll/pitch/yaw, with slide camera."""
    y = np.asarray(lateral)
    if y.shape != (192,) or not np.isfinite(y).all():
        raise ValueError('invalid path/lane projection input')
    c = CONFIGS[domain]
    distance = np.arange(1, 193, dtype=np.float64)
    pixel_x = c['vanishing_x'] - 910.0 * y / distance
    pixel_y = c['vanishing_y'] + 910.0 * c['camera_height_m'] / distance
    return pixel_x[c['start_point']:], pixel_y[c['start_point']:]


def preprocess(frame):
    from cameraB3 import eon_intrinsics, transform_img
    from common.transformations.model import medmodel_intrinsics
    if frame.shape != (874, 1164, 3) or frame.dtype != np.uint8:
        raise ValueError('unexpected source camera geometry: ' + repr(frame.shape))
    yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
    small = transform_img(yuv, from_intr=eon_intrinsics, to_intr=medmodel_intrinsics,
                          yuv=True, output_size=(512, 256))
    if small.shape != (384, 512) or small.dtype != np.uint8:
        raise ValueError('invalid warped YUV geometry')
    result = np.empty((6, 128, 256), dtype=np.float32)
    result[0] = small[:256:2, ::2]
    result[1] = small[1:256:2, ::2]
    result[2] = small[:256:2, 1::2]
    result[3] = small[1:256:2, 1::2]
    result[4] = small[256:320].reshape(128, 256)
    result[5] = small[320:384].reshape(128, 256)
    if not np.isfinite(result).all() or result.std() < 1.0:
        raise ValueError('blank or invalid preprocessed image')
    return result


def video_identity(domain, count=False):
    path = Path(SOURCES[domain])
    if not path.is_file():
        raise FileNotFoundError(path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError('cannot decode ' + str(path))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    reported_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if (width, height) != (1164, 874) or fps <= 0:
        raise ValueError('unexpected source geometry or frame rate')
    decoded_count = None
    if count:
        decoded_count = 0
        while cap.grab():
            decoded_count += 1
    cap.release()
    return {'path': str(path), 'sha256': sha256(path), 'bytes': path.stat().st_size,
            'width': width, 'height': height, 'fps': fps,
            'opencv_reported_frame_count': reported_count,
            'sequentially_decoded_frame_count': decoded_count}


def preflight(load_both=True, count=False):
    import tensorflow as tf
    import modelB6, parserB6, cameraB3, lanes_image_space
    from common.transformations import model as op_model, orientation
    from tools.lib import framereader
    del modelB6, parserB6, cameraB3, lanes_image_space, op_model, orientation, framereader
    if tf.__version__ != '2.13.1' or BOUNDS != tuple(TARGET_BOUNDS):
        raise RuntimeError('runtime or output contract changed')
    for path in (PROFESSOR, Path('/data'), Path('/opt/openpilot'), Path('/')):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError('source/root mount became writable: ' + str(path))
    for path in (Path('/output'), Path('/derived')):
        if os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError('dedicated writable volume became read-only: ' + str(path))
    for relative, expected in {**STEP5_HASHES, **STEP6_HASHES}.items():
        if sha256(PROFESSOR / relative) != expected:
            raise RuntimeError('professor file changed: ' + relative)
    identities = {role: model_identity(role) for role in MODELS}
    if load_both:
        for role in MODELS:
            model, identities[role] = load_model_for_role(role)
            del model
    sources = {domain: video_identity(domain, count=count) for domain in CONFIGS}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    within(OUTPUT, Path('/output'))
    with tempfile.NamedTemporaryFile(mode='w', prefix='.preflight-probe-', dir=OUTPUT) as probe:
        probe.write('ok')
    stat = os.statvfs(OUTPUT)
    free = stat.f_bavail * stat.f_frsize
    if free < 512 * 1024 * 1024:
        raise RuntimeError('less than 512 MiB Step 6 output space')
    return {'status': 'PASS', 'tensorflow': tf.__version__, 'model': identities,
            'source': sources, 'professor_sha256': 'PASS', 'output_free_bytes': free,
            'source_mounts_read_only': True, 'dedicated_output_writable': True}


def summarize(rows):
    if not rows:
        raise ValueError('no parsed rows')
    result = {'category': 'DESCRIPTIVE', 'frames': len(rows), 'nonfinite_count': 0,
              'ground_truth_accuracy': None}
    for name in ('path', 'left_lane', 'right_lane'):
        values = np.asarray([r[name] for r in rows], dtype=np.float64)[:, 4:40]
        result[name + '_near_mean_m'] = float(values.mean())
        result[name + '_near_abs_max_m'] = float(np.abs(values).max())
        result[name + '_near_temporal_change_m'] = float(np.abs(np.diff(values, axis=0)).mean()) if len(rows) > 1 else None
        result[name + '_near_extreme_frames_gt10m'] = int(np.any(np.abs(values) > 10, axis=1).sum())
    widths = np.asarray([r['left_lane'] for r in rows])[:, 4:40] - np.asarray([r['right_lane'] for r in rows])[:, 4:40]
    result['lane_width_near_mean_m'] = float(widths.mean())
    result['lane_width_near_nonpositive_frames'] = int(np.any(widths <= 0, axis=1).sum())
    lead_x = np.asarray([r['lead_xyva'][0] for r in rows])
    result['lead_x_mean_m'] = float(lead_x.mean())
    result['lead_x_temporal_change_m'] = float(np.abs(np.diff(lead_x)).mean()) if len(rows) > 1 else None
    result['lead_prob_mean'] = float(np.mean([r['lead_prob'] for r in rows]))
    result['state_l2_max'] = float(max(r['state_l2'] for r in rows))
    return result


def render(frame, parsed, domain, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    axes[0, 0].imshow(rgb)
    axes[0, 0].set_title('Overlay Scene')
    axes[0, 1].set_title('Camera View')
    axes[1, 0].imshow(rgb)
    axes[1, 0].set_title('Original Scene')
    axes[1, 1].set_title('Top-Down View')
    for name, color in (('lll', 'r'), ('path', 'g'), ('rll', 'b')):
        x, y = project(parsed[name][0], domain)
        axes[0, 0].plot(x, y, color, linewidth=1)
        axes[0, 1].plot(x, y, color, linewidth=1, label=name)
        axes[1, 1].plot(parsed[name][0], np.arange(1, 193), color, linewidth=1, label=name)
    for ax in (axes[0, 0], axes[0, 1], axes[1, 0]):
        ax.set_xlim(0, 1164)
        ax.set_ylim(874, 0)
    axes[1, 1].set_ylim(80, 0)
    axes[1, 1].invert_xaxis()
    axes[1, 1].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def write_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    temp.replace(path)


def run_cell(domain, role, start, frames, smoke=False):
    if domain not in CONFIGS or role not in MODELS or start < 0 or frames < 2:
        raise ValueError('invalid run arguments')
    preflight(load_both=False)
    # OpenCV's HEVC CAP_PROP_FRAME_COUNT is invalid here; sequential decoding is
    # the frame-count authority and is recorded separately in each manifest.
    source = video_identity(domain, count=True)
    if start + frames >= source['sequentially_decoded_frame_count']:
        raise ValueError('requested frame range exceeds decoded clip')
    model, identity = load_model_for_role(role)
    destination = validated_output_dir(output_dir(domain, role, smoke))
    if destination.exists():
        raise FileExistsError('completed or partial Step 6 result already exists: ' + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.step6-stage-', dir=OUTPUT))
    cap = cv2.VideoCapture(SOURCES[domain])
    try:
        for _ in range(start):
            if not cap.grab():
                raise ValueError('start frame exceeds clip')
        ok, first = cap.read()
        if not ok:
            raise ValueError('first frame cannot decode')
        previous = preprocess(first)
        state = zero_state()
        desire = np.zeros((1, 8), dtype=np.float32)
        traffic = np.asarray(CONFIGS[domain]['traffic'], dtype=np.float32)[None]
        rows, raw_rows = [], []
        started = time.monotonic()
        selected = {0, frames // 2, frames - 1}
        for index in range(frames):
            ok, frame = cap.read()
            if not ok:
                raise ValueError('video ended before requested prediction count')
            current = preprocess(frame)
            images = np.vstack((previous, current))[None]
            if images.shape != (1, 12, 128, 256):
                raise RuntimeError('image input contract changed')
            raw = model([images, desire, traffic, state], training=False).numpy()
            parts = split_output(raw)
            parsed = parse_parts(parts, domain)
            state = next_state(parts)
            row = {'frame': start + index + 1,
                   'path': parsed['path'][0].astype(float).tolist(),
                   'left_lane': parsed['lll'][0].astype(float).tolist(),
                   'right_lane': parsed['rll'][0].astype(float).tolist(),
                   'lead_xyva': parsed['lead_xyva'][0].astype(float).tolist(),
                   'lead_xyva_2s': parsed['lead_xyva_2s'][0].astype(float).tolist(),
                   'lead_prob': float(parsed['lead_prob'][0]),
                   'lead_prob_2s': float(parsed['lead_prob_2s'][0]),
                   'path_valid_len': float(parsed['path_valid_len'][0]),
                   'left_prob': float(parsed['lll_prob'][0]),
                   'right_prob': float(parsed['rll_prob'][0]),
                   'state_l2': float(np.linalg.norm(state))}
            if not all(np.isfinite(v).all() for v in (np.asarray(row['path']),
                                                     np.asarray(row['left_lane']),
                                                     np.asarray(row['right_lane']),
                                                     np.asarray(row['lead_xyva']))):
                raise ValueError('non-finite parsed row')
            rows.append(row)
            raw_rows.append(raw[0].astype(np.float32))
            if index in selected:
                render(frame, parsed, domain, stage / ('frame_%05d.png' % row['frame']))
            previous = current
        elapsed = time.monotonic() - started
        np.save(stage / 'raw_outputs.npy', np.asarray(raw_rows, dtype=np.float32), allow_pickle=False)
        write_json(stage / 'parsed.json', rows)
        metrics = summarize(rows)
        artifacts = {p.name: sha256(p) for p in sorted(stage.iterdir()) if p.is_file()}
        manifest = {'status': 'complete', 'run_type': 'smoke' if smoke else 'production',
                    'domain': domain, 'model': identity, 'source': source,
                    'dataset_role': CONFIGS[domain]['source_role'],
                    'frame_range': {'start_frame': start, 'end_frame_inclusive': start + frames,
                                    'prediction_frames': frames, 'first_pair': [start, start + 1]},
                    'camera_config': CONFIGS[domain], 'parser': 'professor parserB6 plus stable-softplus and slide-offset adapters',
                    'output_slices': {name: [a, b] for name, a, b in zip(NAMES, BOUNDS[:-1], BOUNDS[1:])},
                    'tensorflow': identity['tensorflow'], 'runtime_seconds': elapsed,
                    'metrics': metrics, 'artifact_sha256': artifacts,
                    'traffic_input_differs_from_step5': True,
                    'visual_frames': sorted(start + index + 1 for index in selected)}
        write_json(stage / 'manifest.json', manifest)
        stage.rename(destination)
        return manifest
    except Exception as error:
        write_json(stage / 'failure.json', {'status': 'failed', 'error': repr(error),
                                           'domain': domain, 'model': role})
        raise
    finally:
        cap.release()


def verify_cell(domain, role, smoke=False):
    directory = validated_output_dir(output_dir(domain, role, smoke))
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['domain'] != domain or manifest['model']['role'] != role:
        raise ValueError('mixed or incomplete Step 6 result')
    if manifest['model']['sha256'] != model_identity(role)['sha256']:
        raise ValueError('model artifact identity mismatch')
    if manifest['source']['sha256'] != sha256(SOURCES[domain]):
        raise ValueError('video identity mismatch')
    for name, expected in manifest['artifact_sha256'].items():
        if sha256(directory / name) != expected:
            raise ValueError('result artifact changed: ' + name)
    raw = np.load(directory / 'raw_outputs.npy', mmap_mode='r', allow_pickle=False)
    if raw.shape != (manifest['frame_range']['prediction_frames'], 2383) or not np.isfinite(raw).all():
        raise ValueError('raw result contract failed')
    return manifest


def compare(domain, smoke=False):
    records = {role: verify_cell(domain, role, smoke) for role in MODELS}
    final, best = records['final'], records['best']
    for key in ('source', 'frame_range', 'camera_config', 'domain'):
        if final[key] != best[key]:
            raise ValueError('uncontrolled comparison in ' + key)
    result = {'category': 'DESCRIPTIVE', 'domain': domain,
              'frame_range': final['frame_range'],
              'models': {role: rec['model']['sha256'] for role, rec in records.items()},
              'metrics': {role: rec['metrics'] for role, rec in records.items()},
              'behavioral_winner': 'inconclusive_without_ground_truth'}
    result['final_minus_best'] = {
        key: final['metrics'][key] - best['metrics'][key]
        for key in final['metrics'] if isinstance(final['metrics'][key], (float, int))
        and isinstance(best['metrics'].get(key), (float, int))}
    root = OUTPUT / ('smoke/' if smoke else '') / domain
    # Pair the same deterministic first/middle/last frames; avoid cherry-picking.
    visual_hashes = {}
    for frame in final['visual_frames']:
        name = 'frame_%05d.png' % frame
        left = cv2.imread(str(output_dir(domain, 'final', smoke) / name))
        right = cv2.imread(str(output_dir(domain, 'best', smoke) / name))
        if left is None or right is None or left.shape != right.shape:
            raise ValueError('paired visual missing: ' + name)
        visual = root / ('paired_' + name)
        if not cv2.imwrite(str(visual), np.hstack((left, right))):
            raise RuntimeError('could not write paired visual: ' + str(visual))
        visual_hashes[visual.name] = sha256(visual)
    result['paired_visual_sha256'] = visual_hashes
    write_json(root / 'comparison.json', result)
    return result


def report():
    """Check the complete four-cell matrix and summarize raw cross-domain response."""
    records = {(domain, role): verify_cell(domain, role)
               for domain in CONFIGS for role in MODELS}
    comparisons = {}
    for domain in CONFIGS:
        path = OUTPUT / domain / 'comparison.json'
        if not path.is_file():
            raise FileNotFoundError('run compare before report: ' + str(path))
        comparisons[domain] = json.loads(path.read_text())
    raw_response = {}
    for role in MODELS:
        usa = np.load(output_dir('usa', role) / 'raw_outputs.npy', mmap_mode='r', allow_pickle=False)
        taiwan = np.load(output_dir('taiwan', role) / 'raw_outputs.npy', mmap_mode='r', allow_pickle=False)
        shared = min(len(usa), len(taiwan))
        # Matching frame indices are descriptive, not matching road situations.
        difference = np.asarray(usa[:shared], dtype=np.float64) - np.asarray(taiwan[:shared], dtype=np.float64)
        amplitude = float(np.mean(np.abs(usa[:shared])))
        raw_response[role] = {
            'shared_frame_indices': shared,
            'mean_absolute_raw_output_difference': float(np.mean(np.abs(difference))),
            'max_absolute_raw_output_difference': float(np.max(np.abs(difference))),
            'mean_absolute_usa_raw_output': amplitude,
            'difference_to_amplitude_ratio': float(np.mean(np.abs(difference))) / amplitude if amplitude else None,
        }
    result = {
        'category': 'DESCRIPTIVE', 'ground_truth_accuracy': None,
        'matrix_complete': True,
        'cells': {domain: {role: {'model_sha256': records[domain, role]['model']['sha256'],
                                   'video_sha256': records[domain, role]['source']['sha256'],
                                   'prediction_frames': records[domain, role]['frame_range']['prediction_frames'],
                                   'runtime_seconds': records[domain, role]['runtime_seconds']}
                            for role in MODELS} for domain in CONFIGS},
        'comparisons': comparisons, 'cross_domain_raw_response': raw_response,
        'behavioral_quality': 'inconclusive_without_ground_truth',
        'limitations': ['USA is Step 5 train-seen', 'Taiwan uses distinct slide camera projection',
                        'Step 6 traffic [0,0] differs from Step 5 [1,0]']}
    write_json(OUTPUT / 'report.json', result)
    return result


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    p = commands.add_parser('preflight')
    p.add_argument('--count-frames', action='store_true')
    for command in ('smoke', 'run'):
        p = commands.add_parser(command)
        p.add_argument('--domain', choices=CONFIGS, required=True)
        p.add_argument('--model', choices=MODELS, required=True)
        p.add_argument('--start', type=int, default=0)
        p.add_argument('--frames', type=int, default=5 if command == 'smoke' else 120)
    p = commands.add_parser('verify')
    p.add_argument('--domain', choices=CONFIGS, required=True)
    p.add_argument('--model', choices=MODELS, required=True)
    p.add_argument('--smoke', action='store_true')
    p = commands.add_parser('compare')
    p.add_argument('--domain', choices=CONFIGS, required=True)
    p.add_argument('--smoke', action='store_true')
    commands.add_parser('report')
    args = cli.parse_args(argv)
    if args.command == 'preflight':
        result = preflight(count=args.count_frames)
    elif args.command in ('smoke', 'run'):
        result = run_cell(args.domain, args.model, args.start, args.frames, args.command == 'smoke')
    elif args.command == 'verify':
        result = verify_cell(args.domain, args.model, args.smoke)
    elif args.command == 'report':
        result = report()
    else:
        result = compare(args.domain, args.smoke)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('STEP6 FAIL: %s: %s' % (type(error).__name__, error), file=sys.stderr)
        raise
