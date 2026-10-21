"""Read-only Run2 log measurements. Software commands are not actuator feedback."""
import argparse
from dataclasses import asdict, dataclass
import math
from pathlib import Path

from . import dataset as v1
from . import dataset_v2 as v2
from .real_session import load_session


@dataclass(frozen=True)
class Thresholds:
    """Seconds, fraction, counts. One-frame too-close deadline is fixed by definition."""
    max_frame_age_p95: float = .5
    max_stop_latency: float = .2
    max_drop_fraction: float = .05
    max_id_switches: int = 0
    max_lost_segments: int = 0

    def __post_init__(self):
        for name, value in asdict(self).items():
            v1.require(v1.number(value) and value >= 0, 'invalid threshold: '+name)
        v1.require(self.max_drop_fraction <= 1, 'drop fraction must be <= 1')
        for value in (self.max_id_switches, self.max_lost_segments):
            v1.require(v1.integer(value), 'continuity thresholds must be integer counts')


def nonnegative(value, label):
    v1.require(v1.number(value) and value >= 0, 'invalid '+label)
    return value


def evaluate(directory, thresholds=Thresholds()):
    s = load_session(directory)
    frames = [e for e in s['events'] if e['event'] == 'frame']
    m = s['measurements']
    measured = m.get('frames', [])
    v1.require(isinstance(measured, list), 'measurement frames must be a list')
    by_frame = {}
    ids = {r['frame_id'] for r in s['records']}
    for row in measured:
        v1.require(v1.integer(row['frame']) and row['frame'] in ids and row['frame'] not in by_frame,
                   'unknown/duplicate measurement frame')
        by_frame[row['frame']] = row
        if 'age_seconds' in row: nonnegative(row['age_seconds'], 'frame age')
        if 'too_close' in row: v1.require(type(row['too_close']) is bool, 'invalid too_close')
        if 'target_identity' in row:
            v1.require(isinstance(row['target_identity'], str) and bool(row['target_identity']), 'invalid target identity')
    items = {}
    def item(name, value, threshold, passed=None, detail=''):
        items[name] = {'status': 'NOT_MEASURED' if passed is None else 'PASS' if passed else 'FAIL',
                       'value': value, 'threshold': threshold, 'detail': detail}

    ages = [by_frame[i]['age_seconds'] for i in ids if 'age_seconds' in by_frame.get(i, {})]
    age = sorted(ages)[math.ceil(.95*len(ages))-1] if ages else None
    item('stream_latency', age, thresholds.max_frame_age_p95,
         age <= thresholds.max_frame_age_p95 if len(ages) == len(ids) else None,
         'Acquisition-to-decision age, nearest-rank p95 seconds; full frame coverage required.')

    stops = m.get('operator_stops', [])
    v1.require(isinstance(stops, list), 'operator_stops must be a list')
    # KeyboardInterrupt is the existing journal's observable SIGINT receipt time.
    stops = stops + [{'time_seconds': e['time_seconds']} for e in s['events']
                     if e['event'] == 'error' and e.get('type') == 'KeyboardInterrupt']
    commands = [e for e in s['events'] if e['event'] == 'simulated_control']
    latencies, unanswered, overdue = [], 0, False
    for stop in stops:
        start = nonnegative(stop['time_seconds'], 'operator stop time')
        end = next((e['time_seconds'] for e in commands if e['time_seconds'] >= start
                    and e.get('speed') == e.get('turn') == 0), None)
        if end is None:
            unanswered += 1
            overdue = overdue or any(e['time_seconds'] > start + thresholds.max_stop_latency for e in commands)
        else: latencies.append(end-start)
    latency = max(latencies) if latencies else None
    item('stop_latency', {'max_seconds': latency, 'events': len(stops), 'unanswered': unanswered},
         thresholds.max_stop_latency,
         False if overdue or latency is not None and latency > thresholds.max_stop_latency
         else None if unanswered or not latencies else True,
         'Operator receipt to first journalled zero software command; no actuator measurement.')

    close = [i for i, r in enumerate(frames) if
             by_frame.get(r['frame'], {}).get('too_close') is True
             or 'too_close' in (r.get('decision') or {}).get('reason', '')]
    violations, unknown = 0, 0
    close_coverage = all('too_close' in by_frame.get(r['frame'], {}) for r in frames)
    for i in close:
        window = frames[i:i+2]
        if any((r.get('decision') or {}).get('speed') == 0 for r in window): continue
        if len(window) < 2 or any(r.get('decision') is None for r in window): unknown += 1
        else: violations += 1
    item('too_close_stops', {'events': len(close), 'violations': violations, 'unmeasured': unknown},
         'zero forward command by next processed frame',
         False if violations else None if unknown or not close or not close_coverage else True,
         'Requires per-frame too-close annotations; no exercised event is NOT_MEASURED.')

    drops = s['summary'].get('stream_dropped_frames')
    counters = [e['stream_dropped_frames'] for e in frames if 'stream_dropped_frames' in e]
    for count in counters + ([] if drops is None else [drops]):
        v1.require(v1.integer(count), 'invalid dropped frame counter')
    v1.require(counters == sorted(counters), 'nonmonotonic drop counter')
    if drops is not None and counters:
        v1.require(drops >= counters[-1], 'summary drop counter precedes journal')
    # A complete final counter is required; partial per-frame counters cannot certify a session.
    fraction = drops/(drops+len(ids)) if drops is not None else None
    item('frame_drops', fraction, thresholds.max_drop_fraction,
         fraction <= thresholds.max_drop_fraction if fraction is not None else None,
         'Latest-frame replacements / (processed + replaced); sensor/upstream drops unknown.')

    run_frames = s['run'].get('frames', [])
    switches = lost = 0
    last_ids, was_lost = {}, False
    continuity_complete = bool(run_frames)
    selected = 0
    for r in run_frames:
        target = r.get('target')
        if target is None:
            was_lost = False
            continue
        selected += 1
        identity = by_frame.get(r['frame'], {}).get('target_identity')
        tracks = r.get('tracks')
        if identity is None or not isinstance(tracks, list):
            continuity_complete = False; continue
        if identity in last_ids and last_ids[identity] != target: switches += 1
        last_ids[identity] = target
        missing = not any(t['id'] == target and t['state'] == 'tracked' for t in tracks)
        if missing and not was_lost: lost += 1
        was_lost = missing
    item('tracker_continuity', {'id_switches': switches, 'lost_segments': lost},
         {'id_switches': thresholds.max_id_switches, 'lost_segments': thresholds.max_lost_segments},
         switches <= thresholds.max_id_switches and lost <= thresholds.max_lost_segments
         if continuity_complete and selected else None,
         'Requires selected-target identity annotations; counts tracked-ID changes per identity and loss entries.')
    overall = 'PASS' if all(x['status'] == 'PASS' for x in items.values()) else 'FAIL'
    return {'overall': overall, 'provenance': s['provenance'], 'thresholds': asdict(thresholds), 'items': items}


def markdown(result):
    lines = ['# Run2 acceptance — '+result['provenance']['kind'],
             '', 'Synthetic/simulated fixture PASS is NOT a hardware acceptance.',
             'These checks measure logged software commands, not physical actuator response.',
             '', 'Source: '+v2.canonical(result['provenance']), '',
             '| Item | Status | Measured value | Threshold |', '| --- | --- | --- | --- |']
    for name, item in result['items'].items():
        lines.append(f"| {name} | {item['status']} | {v2.canonical(item['value'])} | {v2.canonical(item['threshold'])} |")
    lines += ['', 'Overall: '+result['overall'], '']
    lines += [name+': '+item['detail'] for name, item in result['items'].items() if item['detail']]
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session_dir')
    parser.add_argument('--report'); parser.add_argument('--json')
    for name, default in asdict(Thresholds()).items():
        parser.add_argument('--'+name.replace('_', '-'), type=int if type(default) is int else float, default=default)
    args = parser.parse_args(argv)
    try:
        thresholds = Thresholds(**{name: getattr(args, name) for name in asdict(Thresholds())})
        result = evaluate(args.session_dir, thresholds)
        report = markdown(result)
        if args.report:
            with Path(args.report).open('x', encoding='utf-8') as stream: stream.write(report)
        if args.json: v2.json_write(Path(args.json), result)
        print(report, end='')
        return 0 if result['overall'] == 'PASS' else 1
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
