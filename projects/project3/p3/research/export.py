"""Read-only events.jsonl conversion; elapsed emission time is NOT capture time."""
import argparse
import hashlib
import json
from pathlib import Path
from .dataset import VERSION, CATEGORIES, envelope, missing, loads, require, number, validate_records


def convert_events(source):
    raw = Path(source).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    records = []
    previous_time = 0.
    for line_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
        event = loads(line)
        require(isinstance(event, dict) and isinstance(event.get('event'), str), 'invalid event')
        stamp = event.get('time_seconds')
        require(number(stamp) and stamp >= previous_time, 'invalid journal timestamp')
        previous_time = stamp
        if event['event'] != 'frame': continue
        reference = f'sha256:{digest}:line:{line_number}'
        r = {'schema_version': VERSION, 'session_id': 'events-'+digest,
             'frame_id': event.get('frame'),
             'timestamp': envelope({'seconds': stamp, 'clock': 'session_elapsed_monotonic',
                                    'semantics': 'journal_emission'},
                                   {'kind': 'observation', 'reference': reference}),
             'data_source': {'kind': 'project3_event_journal', 'reference': 'sha256:'+digest},
             'operator_command': missing('No explicit operator command field in frame event'),
             'emergency_stop': missing('Software STOP is not a measured emergency stop state')}
        for name in CATEGORIES: r[name] = missing('Not recorded in Project 3 frame event')
        r['observations'] = envelope({'camera_frame_reference': None, 'camera_metadata': None,
                                     'detections': None, 'tracks': None,
                                     'selected_target': event.get('target'), 'target_box': None},
                                    {'kind': 'observation', 'reference': reference,
                                     'missing_fields': 'Image, camera metadata, detections, tracks and target box absent; capture timestamp absent'})
        decision = event.get('decision')
        if decision is not None:
            require(isinstance(decision, dict) and decision.get('simulation_only') is True
                    and decision.get('action') in {'STOP', 'FOLLOW'}
                    and number(decision.get('speed')) and number(decision.get('turn'))
                    and isinstance(decision.get('state'), str) and bool(decision['state'])
                    and isinstance(decision.get('reason'), str) and bool(decision['reason']), 'invalid legacy decision')
            require((decision['speed'] == decision['turn'] == 0) == (decision['action'] == 'STOP'), 'inconsistent action')
            r['rule_based_pseudo_labels'] = envelope({
                'linear': decision['speed'], 'angular': decision['turn'], 'units': 'normalized_simulation',
                'controller_type': 'rule_based', 'source_controller': 'FollowController',
                'status': decision['state'], 'reason': decision['reason']},
                {'kind': 'rule_based', 'reference': reference,
                 'basis': 'Known p3.pipeline frame decision contract; not human or physical commands'})
        records.append(r)
    require(bool(records), 'journal has no frame events')
    return validate_records(records)


def export_events(source, destination):
    records = convert_events(source)  # validate entire source before opening destination
    payload = ''.join(json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n' for r in records)
    with Path(destination).open('x', encoding='utf-8') as stream: stream.write(payload)
    return len(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source'); parser.add_argument('destination')
    args = parser.parse_args()
    print(export_events(args.source, args.destination))
