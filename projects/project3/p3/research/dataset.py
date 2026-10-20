"""Version 1 research record contract. Null means unavailable, never fabricated.

Every category is a {value, provenance} envelope. This executable contract is the
schema; unknown keys are rejected. Physical labels/measurements are SI only.
"""
import json
import math

VERSION = 'comma_body_research/1.0'
CATEGORIES = ('observations', 'rule_based_pseudo_labels', 'human_demonstrations',
              'robot_measurements', 'ground_truth')
FIELDS = {
    'observations': {'camera_frame_reference', 'camera_metadata', 'detections', 'tracks',
                     'selected_target', 'target_box'},
    'rule_based_pseudo_labels': {'linear', 'angular', 'units', 'controller_type', 'source_controller', 'status', 'reason'},
    'human_demonstrations': {'linear', 'angular', 'units', 'operator_id'},
    'robot_measurements': {'linear_velocity', 'angular_velocity', 'units', 'odometry'},
    'ground_truth': {'annotations', 'annotation_kind'},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def box(value):
    require(isinstance(value, list) and len(value) == 4 and all(number(x) for x in value)
            and 0 <= value[0] < value[2] and 0 <= value[1] < value[3], 'invalid pixel bounding box')


def finite_tree(value):
    if isinstance(value, float):
        require(math.isfinite(value), 'NaN/Inf prohibited')
    elif isinstance(value, dict):
        for v in value.values(): finite_tree(v)
    elif isinstance(value, list):
        for v in value: finite_tree(v)


def envelope(value, provenance):
    return {'value': value, 'provenance': provenance}


def missing(reason):
    return envelope(None, {'kind': 'missing', 'reason': reason})


def _validate_record(record):
    require(isinstance(record, dict), 'record must be an object')
    require(set(record) == {'schema_version', 'session_id', 'frame_id', 'timestamp',
                           'data_source', 'operator_command', 'emergency_stop', *CATEGORIES}, 'missing/unknown fields')
    finite_tree(record)
    require(record['schema_version'] == VERSION, 'unsupported schema version')
    require(isinstance(record['session_id'], str) and bool(record['session_id'].strip()), 'session ID required')
    require(integer(record['frame_id']), 'invalid frame ID')
    require(isinstance(record['data_source'], dict) and bool(record['data_source'].get('kind'))
            and bool(record['data_source'].get('reference')), 'source reference required')
    for name in ('timestamp', 'operator_command', 'emergency_stop', *CATEGORIES):
        entry = record[name]
        require(isinstance(entry, dict) and set(entry) == {'value', 'provenance'}, 'invalid envelope: '+name)
        p, value = entry['provenance'], entry['value']
        require(isinstance(p, dict) and isinstance(p.get('kind'), str) and bool(p['kind']), 'missing provenance')
        if value is None:
            require(p['kind'] == 'missing' and bool(p.get('reason')), 'missing value needs reason')
            continue
        require(p['kind'] != 'missing' and bool(p.get('reference')), 'present value needs source reference')
        if name == 'timestamp':
            require(isinstance(value, dict) and set(value) == {'seconds', 'clock', 'semantics'}, 'invalid timestamp')
            require(number(value['seconds']) and value['seconds'] >= 0, 'invalid timestamp seconds')
            require(value['clock'] in {'session_elapsed_monotonic', 'monotonic'}, 'invalid clock')
            require(value['semantics'] in {'journal_emission', 'camera_capture'}, 'unknown timestamp semantics')
            require(value['semantics'] != 'camera_capture' or value['clock'] == 'monotonic', 'capture clock required')
        elif name == 'emergency_stop':
            require(type(value) is bool, 'invalid emergency stop')
        elif name == 'operator_command':
            require(isinstance(value, str) and bool(value), 'invalid operator command')
        else:
            require(isinstance(value, dict) and set(value) == FIELDS[name], 'invalid category fields: '+name)
            allowed = {'observations': {'observation', 'synthetic_observation'},
                       'rule_based_pseudo_labels': {'rule_based'},
                       'human_demonstrations': {'human_demonstration'},
                       'robot_measurements': {'robot_measurement'},
                       'ground_truth': {'human_annotation', 'synthetic_ground_truth'}}
            require(p['kind'] in allowed[name], 'category/provenance mismatch')
            if name == 'observations':
                validate_observations(value)
            elif name == 'ground_truth':
                require(value['annotation_kind'] == p['kind'], 'annotation provenance mismatch')
                require(isinstance(value['annotations'], list), 'annotations required')
                for annotation in value['annotations']: box(annotation['box'])
            else:
                a, b = ('linear_velocity', 'angular_velocity') if name == 'robot_measurements' else ('linear', 'angular')
                require(number(value[a]) and number(value[b]), 'invalid control values')
                if name == 'rule_based_pseudo_labels':
                    require(value['units'] == 'normalized_simulation' and value['controller_type'] == 'rule_based'
                            and value['source_controller'] == 'FollowController'
                            and isinstance(value['status'], str) and bool(value['status'])
                            and isinstance(value['reason'], str) and bool(value['reason']), 'inconsistent controller/units')
                    require(0 <= value[a] <= .3 and abs(value[b]) <= .5, 'command outside legacy limits')
                    require(value['status'] in {'IDLE', 'STOP', 'TARGET_SELECTED', 'TRACKING',
                                               'TARGET_TEMPORARILY_LOST', 'TARGET_LOST'}, 'invalid controller status')
                    require(value['status'] == 'TRACKING' or value[a] == value[b] == 0, 'nontracking motion')
                else:
                    require(value['units'] == 'm/s,rad/s', 'invalid physical units')
                    if name == 'human_demonstrations': require(bool(value['operator_id']), 'operator required')
                    else:
                        odo = value['odometry']
                        if odo is not None:
                            require(isinstance(odo, dict) and set(odo) == {'x_m', 'y_m', 'yaw_rad', 'coordinate_frame'}
                                    and all(number(odo[k]) for k in ('x_m', 'y_m', 'yaw_rad'))
                                    and bool(odo['coordinate_frame']), 'invalid odometry')
    return record


def validate_record(record):
    try:
        return _validate_record(record)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError('malformed schema record') from error


def validate_observations(value):
    require(value['camera_frame_reference'] is None or isinstance(value['camera_frame_reference'], str), 'frame reference')
    meta = value['camera_metadata']
    if meta is not None:
        require(isinstance(meta, dict) and set(meta) == {'width', 'height', 'color_space'}
                and integer(meta['width'], 1) and integer(meta['height'], 1)
                and meta['color_space'] in {'BGR', 'RGB', 'GRAY'}, 'camera metadata')
    for name in ('detections', 'tracks'):
        rows = value[name]
        require(rows is None or isinstance(rows, list), 'invalid '+name)
        ids = set()
        for row in rows or []:
            require(isinstance(row, dict), 'invalid box record')
            box(row.get('box'))
            if meta:
                require(row['box'][2] <= meta['width'] and row['box'][3] <= meta['height'], 'box outside image')
            if name == 'tracks':
                require(integer(row.get('id'), 1) and row['id'] not in ids
                        and row.get('state') in {'tracked', 'missing'}, 'invalid track')
                ids.add(row['id'])
            else:
                require(integer(row.get('class_id')) and number(row.get('objectness'))
                        and 0 <= row['objectness'] <= 1, 'invalid detection')
    require(value['selected_target'] is None or integer(value['selected_target'], 1), 'invalid target ID')
    if value['target_box'] is not None:
        box(value['target_box'])
        require(value['selected_target'] is not None, 'target box without target')
        if meta: require(value['target_box'][2] <= meta['width'] and value['target_box'][3] <= meta['height'], 'target outside image')


def validate_records(records):
    seen, times = set(), {}
    for record in records:
        validate_record(record)
        key = (record['session_id'], record['frame_id'])
        require(key not in seen, 'duplicate frame ID')
        seen.add(key)
        stamp = record['timestamp']['value']
        if stamp:
            clock = (record['session_id'], stamp['clock'], stamp['semantics'])
            require(stamp['seconds'] >= times.get(clock, 0), 'timestamps out of order')
            times[clock] = stamp['seconds']
    return records


def loads(text):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    try:
        result = json.loads(text, object_pairs_hook=pairs)
        finite_tree(result)
        return result
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError('corrupt JSON') from error
