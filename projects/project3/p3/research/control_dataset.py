"""Versioned offline observation/teacher-action data. No physical commands or media copies."""
import argparse
from collections import Counter
import hashlib
import math
from pathlib import Path
import random
import re

from . import dataset as v1
from . import dataset_v2 as v2
from .closed_loop import SCENARIOS, SimConfig, run_scenario
from .controllers import RuleBasedController
from .export import convert_events
from .pid_controller import PIDFollowController, PIDConfig

SCHEMA = 'p3_control_dataset/1.0'
VERSION = '1.0'
SPLITS = ('train', 'val', 'test')
# Numeric inputs only. Null stays null; consumers must choose an explicit missing-data policy.
FEATURES = ['frame_height', 'frame_width', 'target_visible', 'bbox_x1', 'bbox_y1',
            'bbox_x2', 'bbox_y2', 'centre_offset', 'width_fraction', 'height_fraction',
            'number_of_tracks', 'age_seconds']
FEATURE = FEATURES
ACTIONS = ['linear', 'angular']
OBS_FIELDS = set(FEATURES) | {'follow_state', 'follow_reason'}
require = v1.require


def hash_value(value):
    return hashlib.sha256(v2.canonical(value).encode('utf-8')).hexdigest()


def split_episode(episode_id, ratios=(.7, .15, .15)):
    require(len(ratios) == 3 and all(v1.number(x) and 0 <= x <= 1 for x in ratios)
            and math.isclose(sum(ratios), 1., abs_tol=1e-12), 'invalid split ratios')
    value = int(hashlib.sha256(episode_id.encode()).hexdigest(), 16) / 2**256
    return 'train' if value < ratios[0] else 'val' if value < sum(ratios[:2]) else 'test'


def features(observation):
    return [observation[name] for name in FEATURES]


def observation_features(height, width, tracks, target_id, state, reason, age):
    target = next((t for t in tracks or [] if t['id'] == target_id), None)
    visible = None if tracks is None else bool(target and target['state'] == 'tracked')
    box = target['box'] if visible and height and width else None
    normalized = [box[0]/width, box[1]/height, box[2]/width, box[3]/height] if box else [None]*4
    return dict(zip(FEATURES, [height, width, visible, *normalized,
        normalized[0]+normalized[2]-1 if box else None,
        normalized[2]-normalized[0] if box else None,
        normalized[3]-normalized[1] if box else None,
        len(tracks) if tracks is not None else None, age]), follow_state=state, follow_reason=reason)


def action_dict(action):
    return {'controller_type': 'pid' if action.source_controller == 'pid' else 'rule',
            'linear': action.linear_velocity_command, 'angular': action.angular_velocity_command,
            'status': action.status, 'valid': action.valid, 'units': action.units}


def make_sample(episode, step, timestamp, source, frame_ref, observation, teacher, safety, truth=None):
    row = {'schema': SCHEMA, 'sample_id': hash_value([episode, step]), 'episode_id': episode,
           'split': None, 'step': step, 'timestamp': timestamp, 'source': source,
           'frame_ref': frame_ref, 'observation': observation, 'feature_vector': features(observation),
           'teacher_action': teacher, 'safety': safety,
           'sim_ground_truth': None if truth is None else {'privileged': True, 'for_model_input': False, **truth},
           'missing_fields': []}
    row['missing_fields'] = sorted(['observation.'+k for k, v in observation.items() if v is None]
        + ['safety.'+k for k, v in safety.items() if v is None]
        + [k for k in ('timestamp', 'frame_ref', 'sim_ground_truth') if row[k] is None])
    return row


def _validate_sample(row):
    require(isinstance(row, dict) and set(row) == {'schema', 'sample_id', 'episode_id', 'split', 'step',
        'timestamp', 'source', 'frame_ref', 'observation', 'feature_vector', 'teacher_action', 'safety',
        'sim_ground_truth', 'missing_fields'}, 'sample fields')
    v1.finite_tree(row)
    require(row['schema'] == SCHEMA and isinstance(row['episode_id'], str) and bool(row['episode_id']), 'schema/episode')
    require(v1.integer(row['step']) and row['sample_id'] == hash_value([row['episode_id'], row['step']]), 'sample ID/step')
    require(row['split'] in SPLITS, 'invalid split')
    source = row['source']
    require(set(source) == {'kind', 'reference'} and source['kind'] in {'closed_loop_simulation', 'recorded_run'}
            and v2.is_hash(source['reference']), 'source')
    ref = row['frame_ref']
    require(ref is None or (isinstance(ref, str) and re.fullmatch(r'sha256:[0-9a-f]{64}#decoded_frame=\d+', ref)), 'frame_ref')
    stamp = row['timestamp']
    if stamp is not None:
        require(set(stamp) == {'seconds', 'clock', 'semantics'} and v1.number(stamp['seconds']) and stamp['seconds'] >= 0
                and (stamp['clock'], stamp['semantics']) in {('simulation_seconds', 'observation_before_action'),
                    ('session_elapsed_monotonic', 'journal_emission'),
                    ('session_elapsed_monotonic', 'processing_complete')}, 'timestamp')
    obs = row['observation']
    require(set(obs) == OBS_FIELDS, 'observation fields')
    for name in ('frame_height', 'frame_width'):
        require(obs[name] is None or v1.integer(obs[name], 1), 'frame dimensions')
    require(obs['target_visible'] is None or type(obs['target_visible']) is bool, 'visibility')
    for name in FEATURES[3:10]:
        value = obs[name]
        require(value is None or (v1.number(value) and (-1 if name == 'centre_offset' else 0) <= value <= 1), 'normalized feature')
    box = [obs[k] for k in ('bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2')]
    require(all(x is None for x in box) or (all(v1.number(x) for x in box)
            and box[0] < box[2] and box[1] < box[3] and obs['target_visible'] is True), 'bbox')
    if box[0] is not None:
        require(obs['centre_offset'] == box[0]+box[2]-1 and obs['width_fraction'] == box[2]-box[0]
                and obs['height_fraction'] == box[3]-box[1], 'bbox feature mismatch')
    else:
        require(all(obs[k] is None for k in ('centre_offset', 'width_fraction', 'height_fraction')), 'geometry without bbox')
    require(obs['number_of_tracks'] is None or v1.integer(obs['number_of_tracks']), 'track count')
    require(obs['age_seconds'] is None or (v1.number(obs['age_seconds']) and obs['age_seconds'] >= 0), 'age')
    require(all(obs[k] is None or isinstance(obs[k], str) and bool(obs[k]) for k in ('follow_state', 'follow_reason')), 'follow fields')
    vector = row['feature_vector']
    require(isinstance(vector, list) and len(vector) == len(FEATURES) and vector == features(obs), 'feature vector')
    action = row['teacher_action']
    require(set(action) == {'controller_type', 'linear', 'angular', 'status', 'valid', 'units'}
            and action['controller_type'] in {'rule', 'pid'} and type(action['valid']) is bool, 'teacher')
    _validate_command(action)
    require(action['status'] in {'IDLE', 'STOP', 'TARGET_SELECTED', 'TRACKING',
            'TARGET_TEMPORARILY_LOST', 'TARGET_LOST'} and obs['follow_state'] == action['status'], 'follow status')
    safety = row['safety']
    require(set(safety) == {'supervisor_latched', 'supervisor_faulted', 'final_gated_command'}, 'safety fields')
    require(all(safety[k] is None or type(safety[k]) is bool for k in ('supervisor_latched', 'supervisor_faulted')), 'supervisor')
    command = safety['final_gated_command']
    if command is not None:
        require(set(command) == {'linear', 'angular', 'status', 'valid', 'units'}, 'gated fields')
        _validate_command(command)
        require(not (safety['supervisor_latched'] or safety['supervisor_faulted'])
                or command['linear'] == command['angular'] == 0, 'latched motion')
    truth = row['sim_ground_truth']
    if source['kind'] == 'closed_loop_simulation':
        require(ref is None and stamp is not None and stamp['clock'] == 'simulation_seconds'
                and truth is not None and all(v is not None for v in safety.values()), 'simulation fields')
    elif stamp is not None:
        require(stamp['clock'] == 'session_elapsed_monotonic', 'recorded clock')
    if truth is not None:
        require(source['kind'] == 'closed_loop_simulation' and set(truth) == {'privileged', 'for_model_input', 'distance_m', 'bearing_rad'}
                and truth['privileged'] is True and truth['for_model_input'] is False
                and v1.number(truth['distance_m']) and truth['distance_m'] >= 0
                and v1.number(truth['bearing_rad']) and abs(truth['bearing_rad']) <= math.pi, 'privileged truth')
    expected = make_sample(row['episode_id'], row['step'], stamp, source, ref, obs, action, safety)['missing_fields']
    if truth is not None: expected.remove('sim_ground_truth')
    require(row['missing_fields'] == expected, 'missing fields declaration')
    return row


def _validate_command(action):
    require(action['units'] == 'normalized_simulation' and type(action['valid']) is bool
            and isinstance(action['status'], str) and bool(action['status'])
            and v1.number(action['linear']) and 0 <= action['linear'] <= .3
            and v1.number(action['angular']) and abs(action['angular']) <= .5, 'command')
    require((action['status'] == 'TRACKING' and action['valid'])
            or action['linear'] == action['angular'] == 0, 'invalid/nontracking motion')


def validate_sample(row):
    try:
        return _validate_sample(row)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('malformed control sample') from error


def validate_samples(rows):
    seen, episodes, previous, sources, times = set(), {}, {}, {}, {}
    for row in rows:
        validate_sample(row)
        episode = row['episode_id']
        require(row['sample_id'] not in seen, 'duplicate sample ID')
        seen.add(row['sample_id'])
        require(episodes.setdefault(episode, row['split']) == row['split'], 'episode split leakage')
        require(sources.setdefault(episode, row['source']) == row['source'], 'mixed episode sources')
        require(row['step'] > previous.get(episode, -1), 'nonmonotonic episode steps')
        previous[episode] = row['step']
        stamp = row['timestamp']
        if stamp is not None:
            clock = (episode, stamp['clock'], stamp['semantics'])
            require(stamp['seconds'] >= times.get(clock, 0), 'nonmonotonic episode timestamp')
            times[clock] = stamp['seconds']
    return rows


def compute_stats(rows, episodes):
    result = {}
    for split in SPLITS:
        subset = [r for r in rows if r['split'] == split]
        feature_stats = {}
        for key in FEATURES:
            values = [float(r['observation'][key]) for r in subset if r['observation'][key] is not None]
            feature_stats[key] = distribution(values, len(subset))
        result[split] = {'count': len(subset), 'episodes': len({r['episode_id'] for r in subset}),
            'features': feature_stats,
            'actions': {k: distribution([r['teacher_action'][k] for r in subset], len(subset)) for k in ACTIONS},
            'status_counts': dict(sorted(Counter(r['teacher_action']['status'] for r in subset).items())),
            'stop_fraction': sum(r['teacher_action']['linear'] == r['teacher_action']['angular'] == 0 for r in subset)/len(subset) if subset else None,
            'scenario_counts': dict(sorted(Counter(episodes[r['episode_id']]['scenario'] for r in subset).items())),
            'controller_counts': dict(sorted(Counter(r['teacher_action']['controller_type'] for r in subset).items()))}
    return result


def distribution(values, total):
    mean = sum(values)/len(values) if values else None
    return {'count': len(values), 'missing': total-len(values), 'mean': mean,
            'std': math.sqrt(sum((v-mean)**2 for v in values)/len(values)) if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None}


def write_dataset(output, rows, config, episodes, ratios, excluded=0):
    output = Path(output)
    for row in rows: row['split'] = split_episode(row['episode_id'], ratios)
    validate_samples(rows)
    stats = compute_stats(rows, episodes)
    output.mkdir(parents=True, exist_ok=False)
    for split in SPLITS:
        with (output/f'samples-{split}.jsonl').open('x', encoding='utf-8') as stream:
            for row in rows:
                if row['split'] == split: stream.write(v2.canonical(row)+'\n')
    v2.json_write(output/'stats.json', stats)
    manifest = {'schema': SCHEMA, 'version': VERSION, 'created_from': config,
        'feature_names': FEATURES, 'action_names': ACTIONS, 'split_ratios': list(ratios),
        'counts': {k: stats[k]['count'] for k in SPLITS}, 'excluded_without_teacher': excluded,
        'episodes': episodes, 'files': {name: v2.digest(output/name) for name in
            ['samples-train.jsonl', 'samples-val.jsonl', 'samples-test.jsonl', 'stats.json']}}
    v2.json_write(output/'manifest.json', manifest)
    return manifest


def build_sim(output, controllers=('pid', 'rule'), scenarios=SCENARIOS, episodes_per_scenario=1,
              seed=0, steps=200, ratios=(.7, .15, .15), perturb=False):
    require(not Path(output).exists(), 'output already exists')
    require(controllers and len(set(controllers)) == len(controllers) and set(controllers) <= {'pid', 'rule'}, 'controllers')
    require(scenarios and len(set(scenarios)) == len(scenarios) and set(scenarios) <= set(SCENARIOS), 'scenarios')
    require(v1.integer(episodes_per_scenario, 1) and v1.integer(steps, 1) and type(seed) is int, 'episode/step/seed')
    rng, rows, episodes = random.Random(seed), [], {}
    for scenario in scenarios:
        for index in range(episodes_per_scenario):
            # Optional deterministic plant speed variation, shared between both teachers.
            scale = rng.uniform(.8, 1.2) if perturb else 1.
            c = SimConfig(max_linear=scale)
            for kind in controllers:
                controller = PIDFollowController() if kind == 'pid' else RuleBasedController()
                identity = {'scenario': scenario, 'controller': kind, 'gains': PIDConfig().to_dict() if kind == 'pid' else {},
                    'config': c.to_dict(), 'seed': seed, 'episode_index': index, 'steps': steps,
                    'perturbations': {'robot_max_linear_scale': scale}}
                reference = hash_value(identity)
                episode = v2.session_id(identity)
                episodes[episode] = identity
                def capture(step, obs, teacher, safe, latched, faulted, truth):
                    target_id = controller.legacy.target
                    observation = observation_features(*obs.frame_dimensions, obs.tracks, target_id,
                        teacher.status, teacher.metadata['reason'], obs.age_seconds)
                    final = action_dict(safe); del final['controller_type']
                    rows.append(make_sample(episode, step,
                        {'seconds': obs.timestamp_monotonic_seconds, 'clock': 'simulation_seconds', 'semantics': 'observation_before_action'},
                        {'kind': 'closed_loop_simulation', 'reference': reference}, None, observation,
                        action_dict(teacher), {'supervisor_latched': latched, 'supervisor_faulted': faulted,
                                              'final_gated_command': final}, truth))
                run_scenario(controller, scenario, steps, c, seed, on_step=capture)
    return write_dataset(output, rows, {'kind': 'synthetic_closed_loop', 'controllers': list(controllers),
        'scenarios': list(scenarios), 'episodes_per_scenario': episodes_per_scenario,
        'seed': seed, 'steps': steps, 'perturb': perturb}, episodes, ratios)


def build_recorded(events, output, ratios=(.7, .15, .15), media_root=None):
    require(not Path(output).exists(), 'output already exists')
    rows, episodes, inputs, excluded = [], {}, [], 0
    for source in events:
        path = Path(source)
        if path.is_dir():
            _, records = v2.load_bundle(path, require_media=False, media_root=media_root)
            reference = v2.digest(path/'records.jsonl')
        else:
            records = convert_events(path)
            reference = v2.digest(path)
        inputs.append(reference)
        for record in records:
            teacher = record['rule_based_pseudo_labels']['value']
            if teacher is None:
                excluded += 1
                continue
            episode = record['session_id']
            episodes[episode] = {'scenario': 'recorded_unknown', 'controller': 'rule', 'source_reference': reference}
            obs = record['observations']['value']
            meta = obs['camera_metadata'] or {}
            target = record.get('selection', {}).get('controller_target_id', obs['selected_target'])
            observation = observation_features(meta.get('height'), meta.get('width'), obs['tracks'], target,
                teacher['status'], teacher['reason'], record.get('processing', {}).get('age_at_decision_seconds'))
            rows.append(make_sample(episode, record['frame_id'], record['timestamp']['value'],
                {'kind': 'recorded_run', 'reference': reference}, obs['camera_frame_reference'], observation,
                {'controller_type': 'rule', 'linear': teacher['linear'], 'angular': teacher['angular'],
                 'status': teacher['status'], 'valid': True, 'units': teacher['units']},
                {'supervisor_latched': None, 'supervisor_faulted': None, 'final_gated_command': None}))
    return write_dataset(output, rows, {'kind': 'recorded_run', 'source_sha256s': inputs}, episodes, ratios, excluded)


def validate(directory):
    directory = Path(directory)
    manifest = v1.loads((directory/'manifest.json').read_text())
    require(manifest['schema'] == SCHEMA and manifest['version'] == VERSION, 'manifest schema')
    require(manifest['feature_names'] == FEATURES and manifest['action_names'] == ACTIONS, 'manifest features/actions')
    names = {'samples-'+s+'.jsonl' for s in SPLITS} | {'stats.json'}
    require(set(manifest['files']) == names, 'manifest files')
    for name, digest in manifest['files'].items():
        require(v2.digest(directory/name) == digest, 'hash mismatch: '+name)
    rows = []
    for split in SPLITS:
        subset = [v1.loads(line) for line in (directory/f'samples-{split}.jsonl').read_text().splitlines()]
        require(all(r['split'] == split for r in subset), 'split file mismatch')
        require(len(subset) == manifest['counts'][split], 'count mismatch')
        rows.extend(subset)
    validate_samples(rows)
    for row in rows:
        episode = row['episode_id']
        require(episode in manifest['episodes'], 'missing episode metadata')
        require(row['split'] == split_episode(episode, manifest['split_ratios']), 'split hash mismatch')
        if row['source']['kind'] == 'closed_loop_simulation':
            identity = manifest['episodes'][episode]
            require(episode == v2.session_id(identity) and row['source']['reference'] == hash_value(identity), 'simulation provenance mismatch')
    stats = compute_stats(rows, manifest['episodes'])
    require(v1.loads((directory/'stats.json').read_text()) == stats, 'stats mismatch')
    return manifest, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('build-sim', 'build-recorded'):
        p = commands.add_parser(command)
        p.add_argument('--output', required=True)
        p.add_argument('--ratios', default='0.7,0.15,0.15')
        if command == 'build-sim':
            p.add_argument('--controllers', default='pid,rule')
            p.add_argument('--scenarios', default=','.join(SCENARIOS))
            p.add_argument('--episodes-per-scenario', type=int, default=1)
            p.add_argument('--seed', type=int, default=0)
            p.add_argument('--steps', type=int, default=200)
            p.add_argument('--perturb', action='store_true')
        else:
            p.add_argument('--events', nargs='+', required=True, help='events.jsonl files or v2 bundle directories')
            p.add_argument('--media-root')
    for command in ('validate', 'stats'):
        commands.add_parser(command).add_argument('directory')
    args = parser.parse_args(argv)
    try:
        if args.command.startswith('build'):
            ratios = tuple(float(x) for x in args.ratios.split(','))
            if args.command == 'build-sim':
                build_sim(args.output, args.controllers.split(','), args.scenarios.split(','),
                    args.episodes_per_scenario, args.seed, args.steps, ratios, args.perturb)
            else:
                build_recorded(args.events, args.output, ratios, args.media_root)
            _, stats = validate(args.output)
        else:
            _, stats = validate(args.directory)
        print(v2.canonical(stats))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
