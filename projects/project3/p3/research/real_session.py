"""Read local Project 3 journals/bundles; never capture media or send commands."""
import argparse
from pathlib import Path

from . import control_dataset as cd
from . import dataset as v1
from . import dataset_v2 as v2
from .export import convert_events


def read_json(path):
    return v1.loads(Path(path).read_text(encoding='utf-8'))


def read_lines(path):
    return [v1.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def load_session(directory):
    """Pipeline events (+ optional run.json/status), or complete recorder v2 bundle."""
    root = Path(directory)
    cd.require(root.is_dir(), 'session directory required')
    files = []
    if (root/'records.jsonl').exists():
        manifest, records = v2.load_bundle(root, require_media=False, media_root='')
        files = ['records.jsonl', 'manifest.json']
        events, summary, run = [], {}, {}
        detector_kind = manifest['identity']['configuration']['detector']['kind']
        kind = 'simulated' if 'synthetic' in detector_kind.lower() else 'real'
    else:
        cd.require((root/'events.jsonl').is_file(), 'missing events.jsonl or v2 recording bundle')
        records = convert_events(root/'events.jsonl')
        events = read_lines(root/'events.jsonl')
        files = ['events.jsonl']
        summary, run = {}, {}
        for name, dest in [('run-status.json', summary), ('run.json', run)]:
            if (root/name).exists():
                dest.update(read_json(root/name)); files.append(name)
        # Recorded observations can be real even when processed from a local file.
        # Synthetic fixtures must explicitly declare their simulated origin.
        kind = 'real'
        if run:
            frames = run.get('frames')
            cd.require(isinstance(frames, list) and len(frames) == len(records), 'run.json frame count mismatch')
            journal_frames = [e for e in events if e['event'] == 'frame']
            for record, frame, event in zip(records, frames, journal_frames):
                cd.require(frame['frame'] == record['frame_id'], 'run.json frame index mismatch')
                cd.require(frame['decision'] == event['decision'], 'decision mismatch')
                record['observations']['value']['tracks'] = frame.get('tracks')
    if (root/'session-provenance.json').exists():
        cd.require(read_json(root/'session-provenance.json') == {'kind': 'simulated'},
                   'only explicit simulated provenance override is supported')
        kind = 'simulated'; files.append('session-provenance.json')
    measurements = {}
    if (root/'run2-measurements.json').exists():
        measurements = read_json(root/'run2-measurements.json')
        cd.require(measurements.get('clock') == 'session_elapsed_monotonic', 'measurement clock must match journal')
        files.append('run2-measurements.json')
    reference = cd.hash_value({name: v2.digest(root/name) for name in sorted(files)})
    return {'records': records, 'events': events, 'summary': summary, 'run': run,
            'measurements': measurements, 'provenance': {'kind': kind,
            'source_session': records[0]['session_id'], 'source_sha256': reference}}


def to_control_dataset(directory, output):
    session = load_session(directory)
    provenance = session['provenance']
    episode = provenance['source_session']
    rows = []
    for record in session['records']:
        teacher = record['rule_based_pseudo_labels']['value']
        cd.require(teacher is not None, f"frame {record['frame_id']}: missing recorded teacher command")
        obs = record['observations']['value']
        meta = obs['camera_metadata'] or {}
        target = record.get('selection', {}).get('controller_target_id', obs['selected_target'])
        observation = cd.observation_features(meta.get('height'), meta.get('width'), obs['tracks'], target,
            teacher['status'], teacher['reason'], record.get('processing', {}).get('age_at_decision_seconds'))
        row = cd.make_sample(episode, record['frame_id'], record['timestamp']['value'],
            {'kind': 'recorded_run', 'reference': provenance['source_sha256']}, obs['camera_frame_reference'],
            observation, {'controller_type': 'rule', 'linear': teacher['linear'], 'angular': teacher['angular'],
                'status': teacher['status'], 'valid': True, 'units': teacher['units']},
            {'supervisor_latched': None, 'supervisor_faulted': None, 'final_gated_command': None})
        row['provenance'] = dict(provenance)
        rows.append(row)
    return cd.write_dataset(output, rows, {'kind': 'session_export', 'provenance': provenance,
        'teacher_labels': 'recorded software rule output; not physical actuator feedback'},
        {episode: {'scenario': 'recorded_unknown', 'controller': 'rule', 'provenance': provenance}}, (.7, .15, .15))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('to-control-dataset')
    p.add_argument('session_dir'); p.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = to_control_dataset(args.session_dir, args.output)
        print(v2.canonical(result['counts']))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
