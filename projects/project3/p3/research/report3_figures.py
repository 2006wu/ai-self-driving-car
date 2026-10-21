"""Gather a Report 3 draft from synthetic experiments and existing evidence.

The draft folder is never the implicit default. Pass ``--output`` for a new
directory, or ``--draft`` to write ``reports/project3-report3-draft``. Existing
outputs are refused. Real hardware stays ``NOT TESTED`` unless evidence says
otherwise. Missing measurements stay ``NOT AVAILABLE``; numbers are not invented.
"""
import argparse
import csv
import io
import json
import math
import os
import re
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMEXPR_NUM_THREADS', '1')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/matplotlib-p3')

import numpy as np

from . import bc_baseline as bc
from . import control_dataset as cd
from .closed_loop import SCENARIOS, SimConfig, person_position, run_scenario
from .controllers import RuleBasedController
from .pid_controller import PIDFollowController
from .pid_sim import compare
from .tracker_benchmark import METHODS, run_benchmark

try:
    Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)
except OSError:
    pass

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, PngImagePlugin

PROJECT3 = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT3.parents[1]
DEFAULT_EVIDENCE = PROJECT3/'evidence'
DRAFT_RELATIVE = Path('reports/project3-report3-draft')
SCHEMA = 'p3_report3_figures/1.0'
TEXT_SUFFIXES = {'.txt', '.md', '.json', '.py'}
MAX_EVIDENCE_BYTES = 2_000_000
PNG_METADATA = {'Software': 'p3.research.report3_figures',
                'Creation Time': 'Thu, 01 Jan 2026 00:00:00 GMT'}
CONTROLLER_COLORS = {'rule': '#4C78A8', 'pid': '#F58518', 'ridge': '#54A24B', 'mlp': '#E45756'}
BC_CHART_CONTROLLERS = ('pid', 'ridge', 'mlp')
PID_CONTROLLERS = ('rule', 'pid')
BC_CSV_CONTROLLERS = ('pid', 'rule', 'ridge', 'mlp')
TRACKER_COLUMNS = ('scenario', 'method', 'seed', 'ID_switches', 'IDF1', 'ID_precision', 'ID_recall',
                   'track_fragmentations', 'detection_matches', 'ground_truth_detections',
                   'predicted_detections', 'annotation_kind')
PID_COLUMNS = ('scenario', 'controller', 'centering_rms', 'distance_rms_m', 'distance_overshoot_m',
               'lateral_overshoot_m', 'settling_time_s', 'safety_stop_steps', 'safety_pass',
               'min_distance_m', 'steps', 'seed')
BC_COLUMNS = ('scenario', 'partition', 'episode_index', 'max_linear', 'controller', 'centering_rms',
              'distance_rms_m', 'distance_overshoot_m', 'lateral_overshoot_m', 'settling_time_s',
              'safety_stop_steps', 'safety_pass', 'steps', 'seed')
RAN_RE = re.compile(r'^Ran (\d+) tests? in (\d+(?:\.\d+)?)s\s*$')
STATUS_RE = re.compile(r'^(OK|FAILED|ERROR)(?:\s*\((.*)\))?\s*$')
STREAM_KEY_RE = re.compile(
    r'["\']?(stream_stop_latency_ms|stream_stop_latency_s|stop_latency_ms|stop_latency_s)["\']?\s*[:=]\s*'
    r'([-+]?(?:\d+(?:\.\d*)?|\.\d+))', re.I)
STREAM_PHRASE_RE = re.compile(
    r'stream stop[- ]latency(?:\s*\((ms|s)\))?\s*[:=]\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))', re.I)
HARDWARE_RE = re.compile(r'(hardware|physical|webcam|camera authorization|C2C|AVFoundation|real tracking)', re.I)
HARDWARE_STATUS_RE = re.compile(r'\b(NOT TESTED|BLOCKED|UNVERIFIED|unverif\w*)\b', re.I)
HARDWARE_PASS_RE = re.compile(
    r'\b(hardware acceptance|physical C2C|physical following|webcam live(?: detection)?)\b.{0,80}\bPASS\b',
    re.I)

matplotlib.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 11, 'axes.labelsize': 10,
    'figure.facecolor': 'white', 'savefig.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.unicode_minus': False,
})


@dataclass(frozen=True)
class Settings:
    tracker_seed: int = 2026
    pid_steps: int = 200
    pid_seed: int = 0
    pid_scenarios: tuple = SCENARIOS
    bc_episodes: int = 8
    bc_dataset_steps: int = 200
    bc_dataset_seed: int = 0
    bc_seed: int = 0
    bc_eval_steps: int = 200
    bc_scenarios: tuple = SCENARIOS
    evidence_dir: Path = DEFAULT_EVIDENCE


def output_directory(output, draft, repo_root):
    """Resolve the draft directory. The reports path is used only with draft=True."""
    if draft and output is not None:
        raise ValueError('pass only one of --output and --draft')
    if draft:
        return Path(repo_root)/DRAFT_RELATIVE
    if output is None:
        raise ValueError('pass --output DIR, or --draft to write reports/project3-report3-draft')
    return Path(output)


def display_path(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def parse_scenarios(text):
    names = tuple(part.strip() for part in str(text).split(',') if part.strip())
    if not names or len(set(names)) != len(names) or any(name not in SCENARIOS for name in names):
        raise ValueError('scenarios must be unique known names: '+', '.join(SCENARIOS))
    return names


def cell(value):
    if value is None:
        return 'null'
    if isinstance(value, (bool, np.bool_)):
        return 'true' if bool(value) else 'false'
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('nonfinite metric')
        return json.dumps(number)
    return str(value)


def csv_bytes(headers, rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(headers), lineterminator='\n', extrasaction='raise')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: cell(row[key]) for key in headers})
    return buffer.getvalue().encode('utf-8')


def markdown_table(headers, rows):
    def shown(value):
        return cell(value).replace('|', '\\|')
    lines = ['| '+' | '.join(headers)+' |', '| '+' | '.join('---' for _ in headers)+' |']
    for row in rows:
        lines.append('| '+' | '.join(shown(row[key]) for key in headers)+' |')
    return '\n'.join(lines)+'\n'


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')


def text_bytes(value):
    if not value.endswith('\n'):
        value += '\n'
    return value.encode('utf-8')


def png_bytes(fig):
    """Encode RGBA pixels with fixed metadata so repeated runs match byte for byte."""
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    pixels = np.asarray(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4).copy()
    plt.close(fig)
    image = Image.fromarray(pixels)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', compress_level=9, pnginfo=_png_info())
    return buffer.getvalue()


def _png_info():
    info = PngImagePlugin.PngInfo()
    for key, value in PNG_METADATA.items():
        info.add_text(key, value)
    return info


def _style_axis(ax, ylabel, title):
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.yaxis.grid(True, linestyle=':', linewidth=0.6, color='#cccccc')
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(frameon=False, loc='upper right')


def grouped_bars(categories, series, ylabel, title, figsize=(8.2, 4.6)):
    """series is a list of (name, values). None becomes a gap, not a zero."""
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    draw_grouped(ax, categories, series, ylabel, title)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.24)
    return png_bytes(fig)


def draw_grouped(ax, categories, series, ylabel, title):
    count = len(series)
    width = 0.8/count
    positions = np.arange(len(categories))
    for index, (name, values) in enumerate(series):
        offset = (index-(count-1)/2)*width
        heights = [float('nan') if value is None else float(value) for value in values]
        ax.bar(positions+offset, heights, width=width*0.92, label=name,
               color=CONTROLLER_COLORS.get(name, '#4C78A8'))
    ax.set_xticks(positions)
    ax.set_xticklabels(list(categories), rotation=20, ha='right')
    _style_axis(ax, ylabel, title)


def overshoot_png(categories, series_for_metric, provenance_title):
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.5), dpi=100)
    for ax, metric, ylabel in (
            (axes[0], 'distance_overshoot_m', 'Distance overshoot (m)'),
            (axes[1], 'lateral_overshoot_m', 'Lateral overshoot (m)')):
        draw_grouped(ax, categories, series_for_metric(metric), ylabel, ylabel)
    fig.suptitle(provenance_title)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.82, bottom=0.24, wspace=0.28)
    return png_bytes(fig)


def trajectory_png(scenario, series_by_controller):
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=100)
    person = series_by_controller['pid']
    ax.plot([row['person_x_m'] for row in person], [row['person_y_m'] for row in person],
            color='#333333', linestyle='--', linewidth=1.4, label='person')
    for name in PID_CONTROLLERS:
        rows = series_by_controller[name]
        color = CONTROLLER_COLORS[name]
        ax.plot([row['robot_x_m'] for row in rows], [row['robot_y_m'] for row in rows],
                color=color, linewidth=1.6, label=name+' robot')
        ax.scatter([rows[0]['robot_x_m']], [rows[0]['robot_y_m']], color=color, s=18, zorder=3)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel('world x (m, forward)')
    ax.set_ylabel('world y (m, left)')
    ax.set_title(scenario+': synthetic kinematic trajectory')
    ax.legend(frameon=False, loc='upper left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.subplots_adjust(left=0.16, right=0.97, top=0.90, bottom=0.12)
    return png_bytes(fig)


def simulate_series(controller, scenario, steps, seed):
    """Record commands, then integrate the same unicycle update as closed_loop."""
    commands = []

    def on_step(step, observation, proposed, safe, latched, faulted, truth):
        commands.append((safe.linear_velocity_command, safe.angular_velocity_command,
                         truth['distance_m'], proposed.status))

    metrics = run_scenario(controller, scenario, steps, seed=seed, on_step=on_step)
    config = SimConfig()
    robot = [0., 0., 0.]
    series = []
    for step, (linear, angular, distance, status) in enumerate(commands):
        t = step*config.dt
        person_x, person_y = person_position(scenario, t)
        integrated = math.hypot(person_x-robot[0], person_y-robot[1])
        if abs(integrated-distance) > 1e-9:
            raise RuntimeError(f'trajectory integration diverged at {scenario} step {step}')
        series.append({'t_s': t, 'robot_x_m': robot[0], 'robot_y_m': robot[1],
                       'person_x_m': person_x, 'person_y_m': person_y, 'distance_m': distance,
                       'linear': linear, 'angular': angular, 'status': status})
        v = linear/.3*config.max_linear
        omega = angular/.5*config.max_angular
        angle = robot[2]
        if abs(omega) > 1e-12:
            robot[0] += v/omega*(math.sin(angle+omega*config.dt)-math.sin(angle))
            robot[1] += v/omega*(math.cos(angle)-math.cos(angle+omega*config.dt))
        else:
            robot[0] += v*config.dt*math.cos(angle)
            robot[1] += v*config.dt*math.sin(angle)
        robot[2] += omega*config.dt
    return metrics, series


def tracker_rows(result):
    rows = []
    for scenario, payload in result['scenarios'].items():
        for method in METHODS:
            metrics = payload['methods'][method]
            rows.append({'scenario': scenario, 'method': method, 'seed': payload['seed'],
                         **{key: metrics[key] for key in TRACKER_COLUMNS if key not in ('scenario', 'method', 'seed')}})
    return rows


def pid_rows(result):
    rows = []
    for scenario, controllers in result['scenarios'].items():
        for name in PID_CONTROLLERS:
            metrics = controllers[name]
            rows.append({'scenario': scenario, 'controller': name,
                         **{key: metrics[key] for key in PID_COLUMNS if key not in ('scenario', 'controller')}})
    return rows


def _detail_counts(detail):
    counts = {'failures': 0, 'errors': 0, 'skipped': 0}
    for key, value in re.findall(r'(failures|errors|skipped)=(\d+)', detail or ''):
        counts[key] = int(value)
    return counts


def parse_unittest_text(text):
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        match = RAN_RE.fullmatch(line.strip())
        if not match:
            continue
        status, detail = 'NOT AVAILABLE', ''
        for later in lines[index+1:index+6]:
            stripped = later.strip()
            if not stripped or set(stripped) <= {'-'}:
                continue
            status_match = STATUS_RE.fullmatch(stripped)
            if status_match:
                status, detail = status_match.group(1), status_match.group(2) or ''
            break
        found.append({'line': index+1, 'tests': int(match.group(1)), 'elapsed_s': match.group(2),
                      'status': status, 'detail': detail, **_detail_counts(detail)})
    return found


def parse_stream_stop_latency(text):
    found = []
    seen = set()
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        for match in STREAM_KEY_RE.finditer(line):
            key, raw = match.group(1), match.group(2)
            unit = 'ms' if key.lower().endswith('_ms') else 's'
            token = (index, key.lower(), raw, unit)
            if token not in seen:
                seen.add(token)
                found.append({'line': index, 'key': key.lower(), 'raw': raw, 'unit': unit})
        for match in STREAM_PHRASE_RE.finditer(line):
            raw = match.group(2)
            unit = match.group(1).lower() if match.group(1) else 'NOT AVAILABLE'
            token = (index, 'stream stop-latency', raw, unit)
            if token not in seen:
                seen.add(token)
                found.append({'line': index, 'key': 'stream stop-latency', 'raw': raw, 'unit': unit})
    return found


def _evidence_files(root):
    if not Path(root).is_dir():
        return []
    files = []
    for path in Path(root).rglob('*'):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_EVIDENCE_BYTES:
            continue
        files.append(path)
    return sorted(files)


def summarize_evidence(root):
    root = Path(root)
    present = root.is_dir()
    test_rows, stream_rows, hardware_rows = [], [], []
    hardware_pass = False
    for path in _evidence_files(root):
        text = path.read_text(encoding='utf-8', errors='replace')
        source = display_path(path)
        for row in parse_unittest_text(text):
            test_rows.append({'source': source, **row})
        for row in parse_stream_stop_latency(text):
            stream_rows.append({'source': source, **row})
        for index, line in enumerate(text.splitlines(), start=1):
            if HARDWARE_PASS_RE.search(line):
                hardware_pass = True
            if HARDWARE_RE.search(line) and (HARDWARE_STATUS_RE.search(line) or HARDWARE_PASS_RE.search(line)):
                hardware_rows.append({'source': source, 'line': index, 'text': ' '.join(line.split())})
    test_rows.sort(key=lambda row: (row['source'], row['line']))
    stream_rows.sort(key=lambda row: (row['source'], row['line'], row['key'], row['raw']))
    hardware_rows.sort(key=lambda row: (row['source'], row['line']))
    if not present:
        test_status = stream_status = 'NOT AVAILABLE'
    else:
        test_status = 'present' if test_rows else 'NOT AVAILABLE'
        stream_status = 'present' if stream_rows else 'NOT AVAILABLE'
    return {'directory': display_path(root) if present else display_path(root),
            'directory_present': present,
            'test_counts': test_rows, 'test_count_status': test_status,
            'stream_stop_latency': stream_rows, 'stream_stop_latency_status': stream_status,
            'hardware_statements': hardware_rows,
            'real_hardware': 'cited evidence records a hardware acceptance pass' if hardware_pass else 'NOT TESTED'}


def _mean(values):
    if not values or any(value is None for value in values):
        return None
    return sum(float(value) for value in values)/len(values)


def _bc_value(rows, scenario, controller, partition, metric):
    chosen = [row[metric] for row in rows if row['scenario'] == scenario and row['controller'] == controller
              and row['partition'] == partition]
    return _mean(chosen)


def _series(rows, scenarios, controllers, partition, metric):
    return [(name, [_bc_value(rows, scenario, name, partition, metric) for scenario in scenarios])
            for name in controllers]


def build_bc(settings):
    with tempfile.TemporaryDirectory(prefix='p3-report3-bc-') as folder:
        dataset = Path(folder)/'dataset'
        cd.build_sim(dataset, controllers=('pid',), scenarios=settings.bc_scenarios,
                     episodes_per_scenario=settings.bc_episodes, seed=settings.bc_dataset_seed,
                     steps=settings.bc_dataset_steps, perturb=False)
        ridge = bc.train(dataset, 'ridge', settings.bc_seed, teacher='pid')
        mlp = bc.train(dataset, 'mlp', settings.bc_seed, teacher='pid')
        digest = ridge.data['training_manifest_sha256']
        if digest != mlp.data['training_manifest_sha256']:
            raise RuntimeError('ridge and MLP were not trained on the same dataset manifest')
        ridge_report = bc.evaluate_closed_loop(ridge, settings.bc_scenarios, settings.bc_eval_steps)
        mlp_report = bc.evaluate_closed_loop(mlp, settings.bc_scenarios, settings.bc_eval_steps)
    if [(row['scenario'], row['episode_index'], row['controllers']['pid'], row['controllers']['rule'])
            for row in ridge_report['episodes']] != [
                (row['scenario'], row['episode_index'], row['controllers']['pid'], row['controllers']['rule'])
                for row in mlp_report['episodes']]:
        raise RuntimeError('PID and rule baselines differ between ridge and MLP closed-loop runs')
    rows = []
    for episode in ridge_report['episodes']:
        mlp_episode = next(item for item in mlp_report['episodes']
                          if item['scenario'] == episode['scenario'] and item['episode_index'] == episode['episode_index'])
        controllers = {'pid': episode['controllers']['pid'], 'rule': episode['controllers']['rule'],
                       'ridge': episode['controllers']['bc'], 'mlp': mlp_episode['controllers']['bc']}
        for name in BC_CSV_CONTROLLERS:
            metrics = controllers[name]
            rows.append({'scenario': episode['scenario'], 'partition': episode['partition'],
                         'episode_index': episode['episode_index'], 'max_linear': episode['config']['max_linear'],
                         'controller': name, 'steps': metrics['steps'], 'seed': metrics['seed'],
                         **{key: metrics[key] for key in
                            ('centering_rms', 'distance_rms_m', 'distance_overshoot_m', 'lateral_overshoot_m',
                             'settling_time_s', 'safety_stop_steps', 'safety_pass')}})
    order = {name: index for index, name in enumerate(settings.bc_scenarios)}
    partition_order = {'nominal': 0, 'held_out_perturbation': 1}
    rows.sort(key=lambda row: (partition_order.get(row['partition'], 9), order[row['scenario']],
                              row['episode_index'], BC_CSV_CONTROLLERS.index(row['controller'])))
    return rows, ridge_report, mlp_report, digest


def _pid_metric(rows, scenario, controller, metric):
    return next(row[metric] for row in rows if row['scenario'] == scenario and row['controller'] == controller)


def build_draft(settings):
    """Return relative path -> bytes. Does not create the output directory."""
    if type(settings.tracker_seed) is not int or type(settings.pid_seed) is not int:
        raise ValueError('seeds must be integers')
    if type(settings.bc_dataset_seed) is not int or type(settings.bc_seed) is not int:
        raise ValueError('seeds must be integers')
    for name in ('pid_steps', 'bc_episodes', 'bc_dataset_steps', 'bc_eval_steps'):
        if type(getattr(settings, name)) is not int or getattr(settings, name) <= 0:
            raise ValueError(name+' must be a positive integer')
    settings = Settings(
        tracker_seed=settings.tracker_seed, pid_steps=settings.pid_steps, pid_seed=settings.pid_seed,
        pid_scenarios=tuple(settings.pid_scenarios), bc_episodes=settings.bc_episodes,
        bc_dataset_steps=settings.bc_dataset_steps, bc_dataset_seed=settings.bc_dataset_seed,
        bc_seed=settings.bc_seed, bc_eval_steps=settings.bc_eval_steps,
        bc_scenarios=tuple(settings.bc_scenarios), evidence_dir=Path(settings.evidence_dir))
    evidence = summarize_evidence(settings.evidence_dir)
    benchmark = run_benchmark(settings.tracker_seed)
    tracker = tracker_rows(benchmark)
    pid_result = compare('both', None, settings.pid_scenarios, settings.pid_steps, settings.pid_seed)
    pid = pid_rows(pid_result)
    trajectories = {}
    for scenario in settings.pid_scenarios:
        trajectories[scenario] = {}
        for name, factory in (('rule', RuleBasedController), ('pid', PIDFollowController)):
            metrics, series = simulate_series(factory(), scenario, settings.pid_steps, settings.pid_seed)
            if metrics != pid_result['scenarios'][scenario][name]:
                raise RuntimeError('trajectory metrics diverged from pid_sim.compare for '+scenario+' '+name)
            trajectories[scenario][name] = series
    bc_rows, ridge_report, mlp_report, digest = build_bc(settings)
    files = {}
    files['tracker/benchmark.json'] = json_bytes(benchmark)
    files['tracker/comparison.csv'] = csv_bytes(TRACKER_COLUMNS, tracker)
    files['tracker/comparison.md'] = text_bytes(
        '# Tracker comparison\n\n'
        'Provenance: **synthetic_ground_truth**. Not a real-hardware result.\n\n'
        'Source command: `'+tracker_command(settings)+'`\n\n'
        'In-process call: `p3.research.tracker_benchmark.run_benchmark(seed='
        +str(settings.tracker_seed)+')`.\n\n'
        'Null cells are JSON null. ID switches are the local evaluator count, not real identity.\n\n'
        +markdown_table(TRACKER_COLUMNS, tracker))
    files['tracker/id_switches.png'] = grouped_bars(
        list(benchmark['scenarios']),
        [(method, [row['ID_switches'] for row in tracker if row['method'] == method]) for method in METHODS],
        'ID switches', 'Synthetic boxes: ID switches by tracker')
    files['pid/compare.json'] = json_bytes(pid_result)
    files['pid/metrics.csv'] = csv_bytes(PID_COLUMNS, pid)
    files['pid/metrics.md'] = text_bytes(
        '# PID vs rule\n\n'
        'Provenance: **synthetic kinematic simulation**. Not a real-hardware result.\n\n'
        'Source command: `'+pid_command(settings)+'`\n\n'
        'Metrics come from `p3.research.pid_sim.compare`. Settling time is null when the run never settles. '
        'Safety stop steps count non-TRACKING predictions. Overshoot is distance closer than desired, '
        'and lateral metres past the initial bearing side.\n\n'+markdown_table(PID_COLUMNS, pid))
    files['pid/centering_rms.png'] = grouped_bars(
        settings.pid_scenarios, [(name, [_pid_metric(pid, scenario, name, 'centering_rms') for scenario in settings.pid_scenarios])
                                 for name in PID_CONTROLLERS],
        'Centering RMS', 'Synthetic simulation: centering RMS')
    files['pid/distance_rms.png'] = grouped_bars(
        settings.pid_scenarios, [(name, [_pid_metric(pid, scenario, name, 'distance_rms_m') for scenario in settings.pid_scenarios])
                                 for name in PID_CONTROLLERS],
        'Distance RMS (m)', 'Synthetic simulation: distance RMS')
    files['pid/overshoot.png'] = overshoot_png(
        settings.pid_scenarios,
        lambda metric: [(name, [_pid_metric(pid, scenario, name, metric) for scenario in settings.pid_scenarios])
                        for name in PID_CONTROLLERS],
        'Synthetic simulation: PID vs rule overshoot')
    files['pid/settling_time_s.png'] = grouped_bars(
        settings.pid_scenarios, [(name, [_pid_metric(pid, scenario, name, 'settling_time_s') for scenario in settings.pid_scenarios])
                                 for name in PID_CONTROLLERS],
        'Settling time (s)', 'Synthetic simulation: settling time (gap = null / never settled)')
    files['pid/safety_stops.png'] = grouped_bars(
        settings.pid_scenarios, [(name, [_pid_metric(pid, scenario, name, 'safety_stop_steps') for scenario in settings.pid_scenarios])
                                 for name in PID_CONTROLLERS],
        'Safety stop steps', 'Synthetic simulation: safety stop steps')
    for scenario, series in trajectories.items():
        files[f'pid/trajectories/{scenario}.png'] = trajectory_png(scenario, series)
    files['bc/ridge_closed_loop.json'] = json_bytes(ridge_report)
    files['bc/mlp_closed_loop.json'] = json_bytes(mlp_report)
    files['bc/closed_loop.csv'] = csv_bytes(BC_COLUMNS, bc_rows)
    files['bc/closed_loop.md'] = text_bytes(
        '# Behaviour cloning vs PID\n\n'
        'Provenance: **synthetic kinematic simulation**. Not a real-hardware result.\n\n'
        'Dataset command: `'+bc_dataset_command(settings)+'`\n\n'
        'Train commands:\n\n'+''.join('- `'+command+'`\n' for command in bc_train_commands(settings))+'\n'
        'Closed-loop commands:\n\n'+''.join('- `'+command+'`\n' for command in bc_eval_commands(settings))+'\n'
        'The dataset is built in a temporary directory and not copied here. '
        'Training manifest SHA-256: `'+digest+'`. '
        'Charts compare pid, ridge and mlp. The table also includes rule because '
        '`evaluate_closed_loop` always runs it. Held-out chart bars are means across held-out episodes; '
        'a bar is omitted when any episode value is null.\n\n'+markdown_table(BC_COLUMNS, bc_rows))
    for partition, prefix, title in (
            ('nominal', 'nominal', 'Nominal synthetic simulation'),
            ('held_out_perturbation', 'heldout', 'Held-out plant scales, mean')):
        files[f'bc/{prefix}_centering_rms.png'] = grouped_bars(
            settings.bc_scenarios, _series(bc_rows, settings.bc_scenarios, BC_CHART_CONTROLLERS, partition, 'centering_rms'),
            'Centering RMS', title+': centering RMS')
        files[f'bc/{prefix}_distance_rms.png'] = grouped_bars(
            settings.bc_scenarios, _series(bc_rows, settings.bc_scenarios, BC_CHART_CONTROLLERS, partition, 'distance_rms_m'),
            'Distance RMS (m)', title+': distance RMS')
        files[f'bc/{prefix}_overshoot.png'] = overshoot_png(
            settings.bc_scenarios,
            lambda metric, partition=partition: _series(bc_rows, settings.bc_scenarios, BC_CHART_CONTROLLERS, partition, metric),
            title+': overshoot')
        files[f'bc/{prefix}_settling_time_s.png'] = grouped_bars(
            settings.bc_scenarios, _series(bc_rows, settings.bc_scenarios, BC_CHART_CONTROLLERS, partition, 'settling_time_s'),
            'Settling time (s)', title+': settling time (gap = null)')
        files[f'bc/{prefix}_safety_stops.png'] = grouped_bars(
            settings.bc_scenarios, _series(bc_rows, settings.bc_scenarios, BC_CHART_CONTROLLERS, partition, 'safety_stop_steps'),
            'Safety stop steps', title+': safety stop steps')
    files.update(evidence_files(evidence))
    files['run.json'] = b''
    records = artifact_records(files, settings)
    records.append({'path': 'summary.md', 'kind': 'summary', 'provenance': 'draft_index',
                    'source_command': reproduction_command(settings)})
    records.sort(key=lambda row: row['path'])
    payload = {'schema': SCHEMA, 'real_hardware': evidence['real_hardware'],
               'stream_stop_latency': evidence['stream_stop_latency_status'],
               'test_counts': evidence['test_count_status'],
               'evidence_directory': evidence['directory'],
               'evidence_directory_present': evidence['directory_present'],
               'bc_training_manifest_sha256': digest,
               'parameters': settings_dict(settings),
               'reproduction': reproduction_command(settings),
               'artifacts': records}
    files['run.json'] = json_bytes(payload)
    files['summary.md'] = text_bytes(render_summary(settings, evidence, records, digest))
    return files


def evidence_files(evidence):
    files = {}
    if evidence['test_counts']:
        test_body = ('# Test counts from existing evidence\n\n'
                     'Provenance: **existing evidence files**. These runs were not repeated. '
                     'Source: read-only scan of `'+evidence['directory']+'`. '
                     'Status is NOT AVAILABLE when a log has a `Ran N tests` line and no following OK/FAILED/ERROR line.\n\n'
                     +markdown_table(('source', 'line', 'tests', 'elapsed_s', 'status', 'failures', 'errors', 'skipped'),
                                     evidence['test_counts']))
    elif evidence['directory_present']:
        test_body = ('# Test counts from existing evidence\n\n'
                     'Conclusion: **NOT AVAILABLE**\n\n'
                     'No unittest `Ran N tests` summary was found under `'+evidence['directory']+'`.\n')
    else:
        test_body = ('# Test counts from existing evidence\n\n'
                     'Conclusion: **NOT AVAILABLE**\n\n'
                     'Evidence directory is missing: `'+evidence['directory']+'`.\n')
    files['evidence/test_counts.md'] = text_bytes(test_body)
    files['evidence/test_counts.csv'] = csv_bytes(
        ('source', 'line', 'tests', 'elapsed_s', 'status', 'failures', 'errors', 'skipped', 'detail'),
        evidence['test_counts'])
    if evidence['stream_stop_latency']:
        stream_body = ('# Stream stop-latency\n\nConclusion: **present**\n\n'
                       'Values are copied from the cited files. Units are taken from the key or phrase; '
                       'a missing unit is NOT AVAILABLE and is not guessed.\n\n'
                       +markdown_table(('source', 'line', 'key', 'raw', 'unit'), evidence['stream_stop_latency']))
    else:
        stream_body = ('# Stream stop-latency\n\nConclusion: **NOT AVAILABLE**\n\n'
                       'No file under `'+evidence['directory']+'` contains a measured stream stop-latency. '
                       'Searched keys: `stream_stop_latency_ms`, `stream_stop_latency_s`, `stop_latency_ms`, '
                       '`stop_latency_s`, and the phrases `stream stop latency` / `stream stop-latency` with a number. '
                       'Inference latency and other timings are not substituted.\n')
    files['evidence/stream_stop_latency.md'] = text_bytes(stream_body)
    hardware_csv = evidence['hardware_statements'] or []
    files['evidence/hardware_statements.csv'] = csv_bytes(('source', 'line', 'text'), hardware_csv)
    grouped = []
    for row in evidence['hardware_statements']:
        if grouped and grouped[-1]['text'] == row['text']:
            grouped[-1]['sources'] += '; '+row['source']+':'+str(row['line'])
        elif any(item['text'] == row['text'] for item in grouped):
            item = next(item for item in grouped if item['text'] == row['text'])
            item['sources'] += '; '+row['source']+':'+str(row['line'])
        else:
            grouped.append({'text': row['text'], 'sources': row['source']+':'+str(row['line'])})
    hardware_md = ('# Real-hardware statements copied from evidence\n\n'
                   'Conclusion: **'+evidence['real_hardware']+'**\n\n'
                   'This draft does not add a hardware measurement. '
                   'A PASS on simulated or injected software is not hardware acceptance. '
                   'The conclusion stays NOT TESTED unless a cited line records hardware acceptance, '
                   'physical C2C, physical following, or webcam live detection as PASS.\n\n')
    if grouped:
        hardware_md += markdown_table(('text', 'sources'), grouped)
    elif evidence['directory_present']:
        hardware_md += 'No matching hardware statement lines were found. Real hardware: **NOT TESTED**.\n'
    else:
        hardware_md += 'Evidence directory is missing, so hardware statements are **NOT AVAILABLE**. Real hardware: **NOT TESTED**.\n'
    files['evidence/hardware_statements.md'] = text_bytes(hardware_md)
    return files


def settings_dict(settings):
    return {'tracker_seed': settings.tracker_seed, 'pid_steps': settings.pid_steps, 'pid_seed': settings.pid_seed,
            'pid_scenarios': list(settings.pid_scenarios), 'bc_episodes': settings.bc_episodes,
            'bc_dataset_steps': settings.bc_dataset_steps, 'bc_dataset_seed': settings.bc_dataset_seed,
            'bc_seed': settings.bc_seed, 'bc_eval_steps': settings.bc_eval_steps,
            'bc_scenarios': list(settings.bc_scenarios), 'bc_teacher': 'pid', 'bc_perturb': False,
            'evidence_dir': display_path(settings.evidence_dir)}


def tracker_command(settings):
    return f'python -m p3.research.tracker_benchmark --seed {settings.tracker_seed} --output <new-file>'


def pid_command(settings):
    return ('python -m p3.research.pid_sim --controller both --scenarios '
            +','.join(settings.pid_scenarios)
            +f' --steps {settings.pid_steps} --seed {settings.pid_seed} --output <new-file>')


def bc_dataset_command(settings):
    return ('python -m p3.research.control_dataset build-sim --output <temp-dir> --controllers pid --scenarios '
            +','.join(settings.bc_scenarios)
            +f' --episodes-per-scenario {settings.bc_episodes} --seed {settings.bc_dataset_seed} '
            +f'--steps {settings.bc_dataset_steps}')


def bc_train_commands(settings):
    return [f'python -m p3.research.bc_baseline train --dataset <temp-dir> --model {kind} '
            f'--output <temp-dir>/{kind}.json --seed {settings.bc_seed} --teacher pid'
            for kind in ('ridge', 'mlp')]


def bc_eval_commands(settings):
    scenarios = ','.join(settings.bc_scenarios)
    return [f'python -m p3.research.bc_baseline eval-closed-loop --model-file <temp-dir>/{kind}.json '
            f'--scenarios {scenarios} --steps {settings.bc_eval_steps} --output <new-file>'
            for kind in ('ridge', 'mlp')]


def reproduction_command(settings):
    parts = ['python -m p3.research.report3_figures --output <new-dir>',
             f'--tracker-seed {settings.tracker_seed}', f'--pid-steps {settings.pid_steps}',
             f'--pid-seed {settings.pid_seed}', '--pid-scenarios '+','.join(settings.pid_scenarios),
             f'--bc-episodes {settings.bc_episodes}', f'--bc-dataset-steps {settings.bc_dataset_steps}',
             f'--bc-dataset-seed {settings.bc_dataset_seed}', f'--bc-seed {settings.bc_seed}',
             f'--bc-eval-steps {settings.bc_eval_steps}', '--bc-scenarios '+','.join(settings.bc_scenarios)]
    if Path(settings.evidence_dir).resolve() != DEFAULT_EVIDENCE.resolve():
        parts.append('--evidence '+shlex.quote(display_path(settings.evidence_dir)))
    return ' '.join(parts)


def artifact_records(files, settings):
    records = []
    for path in sorted(files):
        if path.startswith('tracker/'):
            provenance, command = 'synthetic_ground_truth', tracker_command(settings)
        elif path.startswith('pid/'):
            provenance = 'synthetic_simulation'
            command = pid_command(settings)
            if '/trajectories/' in path:
                command += ' ; robot path integrated with the same unicycle update as p3.research.closed_loop.run_scenario; person path from person_position'
        elif path.startswith('bc/'):
            provenance, command = 'synthetic_simulation', bc_dataset_command(settings)+' ; '+'; '.join(bc_train_commands(settings)+bc_eval_commands(settings))
        elif path.startswith('evidence/'):
            provenance, command = 'existing_evidence', 'read-only scan of '+display_path(settings.evidence_dir)+'; no measurement command'
        else:
            provenance, command = 'draft_index', reproduction_command(settings)
        kind = 'figure' if path.endswith('.png') else 'table' if path.endswith(('.csv', '.md')) else 'json'
        records.append({'path': path, 'kind': kind, 'provenance': provenance, 'source_command': command})
    return records


def render_summary(settings, evidence, records, digest):
    lines = ['# Report 3 draft', '',
             'This folder mixes **synthetic / simulated** results with **citations of existing evidence**. '
             'It does not create real-hardware results.', '',
             '## How to read provenance', '',
             '- **Synthetic / simulated:** tracker boxes, PID/rule rollouts, and behaviour-cloning closed loop. These are not vehicle or camera acceptance.',
             '- **Existing evidence:** test counts and stream stop-latency are copied from files when present. Missing items are **NOT AVAILABLE**. Numbers are not invented.',
             '- **Real hardware:** **'+evidence['real_hardware']+'**.',
             '',
             '## Reproduction', '',
             'Docker, from the repository root, writes a **new** directory and refuses an existing one:', '',
             '```sh',
             './scripts/dev.sh p3-python -m p3.research.report3_figures --output artifacts/report3-draft-001',
             '```', '',
             'Parameters actually used for this folder:', '',
             '```sh',
             reproduction_command(settings),
             '```', '',
             '`reports/project3-report3-draft` is written only when `--draft` is passed. It is not the implicit output.',
             '',
             'Behaviour-cloning training manifest SHA-256: `'+digest+'`. The `build-sim` dataset lived in a temporary directory and was not saved.',
             '',
             '## Figures and tables', '',
             '| Artifact | Kind | Provenance | Source command |',
             '| --- | --- | --- | --- |']
    for record in records:
        command = record['source_command'].replace('|', '\\|')
        lines.append(f"| `{record['path']}` | {record['kind']} | {record['provenance']} | `{command}` |")
    lines += ['',
              '## Simulated and synthetic results', '',
              'Tracker rows are `synthetic_ground_truth` from `p3.research.tracker_benchmark` '
              f"(seed {settings.tracker_seed}). The bar chart is ID switches only.",
              '',
              'PID and rule rows are a synthetic kinematic simulation from `p3.research.pid_sim.compare` '
              f"(steps {settings.pid_steps}, seed {settings.pid_seed}). "
              'One trajectory plot per scenario shows the person path and both robot paths in world metres '
              '(x forward, y left). The seed is recorded; the current simulator does not use it for randomness.',
              '',
              'Behaviour cloning trains ridge and MLP on a fresh `control_dataset build-sim` PID dataset '
              f"(episodes per scenario {settings.bc_episodes}, dataset steps {settings.bc_dataset_steps}, "
              f"dataset seed {settings.bc_dataset_seed}, model seed {settings.bc_seed}, perturb false) "
              f"and evaluates closed loop for {settings.bc_eval_steps} steps. "
              'Nominal episodes can overlap training trajectories. Held-out episodes use plant scales outside the training range. '
              'This is not real comma-body data and not hardware acceptance.',
              '',
              '## Existing evidence (not re-measured)', '',
              f"Evidence directory: `{evidence['directory']}` (present: {str(evidence['directory_present']).lower()}).",
              '',
              f"Stream stop-latency conclusion: **{evidence['stream_stop_latency_status']}**.",
              f"Test-count conclusion: **{evidence['test_count_status']}** "
              f"({len(evidence['test_counts'])} unittest summaries).",
              '',
              'See `evidence/stream_stop_latency.md`, `evidence/test_counts.md` and `evidence/test_counts.csv`. '
              'Each test-count row cites its source path and line.',
              '',
              '## Real hardware', '',
              f"Conclusion: **{evidence['real_hardware']}**.",
              '',
              'Cited statements, when any exist, are copied into `evidence/hardware_statements.md` and '
              '`evidence/hardware_statements.csv` with source paths. This draft did not run a vehicle, camera acceptance, or C2C session.',
              '']
    return '\n'.join(lines)


def write_new_tree(destination, files):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f'output already exists: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f'output already exists: {destination}') from exc
    for name in sorted(files):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe artifact path: '+name)
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(files[name])
    return destination


def settings_from_namespace(args):
    return Settings(tracker_seed=args.tracker_seed, pid_steps=args.pid_steps, pid_seed=args.pid_seed,
                    pid_scenarios=parse_scenarios(args.pid_scenarios), bc_episodes=args.bc_episodes,
                    bc_dataset_steps=args.bc_dataset_steps, bc_dataset_seed=args.bc_dataset_seed,
                    bc_seed=args.bc_seed, bc_eval_steps=args.bc_eval_steps,
                    bc_scenarios=parse_scenarios(args.bc_scenarios),
                    evidence_dir=args.evidence if args.evidence is not None else DEFAULT_EVIDENCE)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new directory; refused if it already exists')
    parser.add_argument('--draft', action='store_true',
                        help='write reports/project3-report3-draft; only when this flag is set')
    parser.add_argument('--evidence', type=Path, help='evidence directory to read (default projects/project3/evidence)')
    parser.add_argument('--tracker-seed', type=int, default=2026)
    parser.add_argument('--pid-steps', type=int, default=200)
    parser.add_argument('--pid-seed', type=int, default=0)
    parser.add_argument('--pid-scenarios', default=','.join(SCENARIOS))
    parser.add_argument('--bc-episodes', type=int, default=8)
    parser.add_argument('--bc-dataset-steps', type=int, default=200)
    parser.add_argument('--bc-dataset-seed', type=int, default=0)
    parser.add_argument('--bc-seed', type=int, default=0)
    parser.add_argument('--bc-eval-steps', type=int, default=200)
    parser.add_argument('--bc-scenarios', default=','.join(SCENARIOS))
    args = parser.parse_args(argv)
    try:
        destination = output_directory(args.output, args.draft, REPO_ROOT)
        if destination.exists():
            raise FileExistsError(f'output already exists: {destination}')
        files = build_draft(settings_from_namespace(args))
        write_new_tree(destination, files)
    except (ValueError, OSError, RuntimeError, np.linalg.LinAlgError) as exc:
        parser.error(str(exc))
    print(destination)
    return 0


if __name__ == '__main__':
    main()
