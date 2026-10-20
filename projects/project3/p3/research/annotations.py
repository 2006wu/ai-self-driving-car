"""Blank human annotation workflow; predictions are never copied into ground truth."""
import hashlib
from pathlib import Path

from .dataset import require, integer, box
from .dataset_v2 import frame_uri, load_bundle, json_write

ANNOTATION_VERSION = 'comma_body_annotations/1.0'


def annotation_template(directory, frame_ids=None):
    manifest, records = load_bundle(directory)
    ids = list(range(len(records))) if frame_ids is None else list(frame_ids)
    require(ids and all(integer(i) and i < len(records) for i in ids)
            and ids == sorted(set(ids)), 'annotation frame IDs must be ordered unique dataset indices')
    return {'annotation_version': ANNOTATION_VERSION, 'status': 'draft',
        'dataset_reference': {'session_id': manifest['session_id'],
                              'records_sha256': manifest['records']['sha256'],
                              'media_sha256': manifest['media']['sha256']},
        'provenance': {'kind': 'pending_human_annotation', 'annotator': '', 'reviewer': '', 'reference': ''},
        'target_person_id': None,
        'frames': [{'frame_id': i, 'frame_reference': records[i]['observations']['value']['camera_frame_reference'],
                    'width': records[i]['frame_reference']['width'], 'height': records[i]['frame_reference']['height'],
                    'reviewed': False, 'persons': []} for i in ids]}


def validate_annotations(document, manifest, records, *, require_reviewed=True):
    try:
        require(isinstance(document, dict) and set(document) == {'annotation_version', 'status', 'dataset_reference',
                'provenance', 'target_person_id', 'frames'}, 'annotation fields')
        require(document['annotation_version'] == ANNOTATION_VERSION, 'unsupported annotation version')
        require(document['dataset_reference'] == {'session_id': manifest['session_id'],
                    'records_sha256': manifest['records']['sha256'], 'media_sha256': manifest['media']['sha256']}, 'annotation dataset mismatch')
        require(document['status'] in {'draft', 'reviewed'}, 'invalid annotation status')
        provenance = document['provenance']
        require(set(provenance) == {'kind', 'annotator', 'reviewer', 'reference'} and
                all(isinstance(s, str) for s in provenance.values()), 'annotation provenance required')
        reviewed = document['status'] == 'reviewed'
        if require_reviewed: require(reviewed, 'human annotations are not reviewed')
        if reviewed:
            require(provenance['kind'] == 'human_annotation' and all(provenance[k].strip()
                    for k in ('annotator', 'reviewer', 'reference')), 'reviewed human provenance required')
        else: require(provenance['kind'] == 'pending_human_annotation', 'draft provenance must remain pending')
        target = document['target_person_id']
        require(target is None or integer(target, 1), 'target person identity must be a positive integer')
        require(isinstance(document['frames'], list) and bool(document['frames']), 'annotation frames required')
        previous, all_people = -1, set()
        for row in document['frames']:
            require(set(row) == {'frame_id', 'frame_reference', 'width', 'height', 'reviewed', 'persons'}, 'annotation frame fields')
            index = row['frame_id']
            require(integer(index) and previous < index < len(records), 'invalid/duplicate/out-of-order annotation frame')
            previous = index
            ref = records[index]['frame_reference']
            require(row['frame_reference'] == frame_uri(manifest['media']['sha256'], index)
                    and type(row['width']) is int and type(row['height']) is int
                    and (row['width'], row['height']) == (ref['width'], ref['height']), 'annotation frame mismatch')
            require(type(row['reviewed']) is bool and (not reviewed or row['reviewed']), 'unreviewed frame')
            require(isinstance(row['persons'], list), 'persons must be a list')
            seen = set()
            for person in row['persons']:
                require(set(person) == {'person_id', 'box', 'occlusion'}, 'person fields')
                pid = person['person_id']
                require(integer(pid, 1) and pid not in seen, 'duplicate/invalid person identity')
                seen.add(pid); all_people.add(pid)
                require(person['occlusion'] in {'none', 'partial', 'full'}, 'invalid occlusion label')
                if person['box'] is None:
                    require(person['occlusion'] == 'full', 'missing box requires full occlusion')
                else:
                    box(person['box'])
                    require(person['box'][2] <= ref['width'] and person['box'][3] <= ref['height'], 'annotation box outside frame')
        if reviewed: require(target is None or target in all_people, 'unknown target identity')
        return document
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('malformed annotations') from error


def extract_annotation_frames(directory, destination, frame_ids):
    """Save unannotated original decoded BGR pixels as lossless PNG, never overlays."""
    import cv2
    from ..pipeline import Frames
    manifest, records = load_bundle(directory)
    template = annotation_template(directory, frame_ids)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    wanted, index = set(frame_ids), []
    try:
        with Frames(manifest['media']['path'], camera=False) as frames:
            for i, image in enumerate(frames):
                if i in wanted:
                    require(hashlib.sha256(image.tobytes()).hexdigest() == records[i]['frame_reference']['decoded_bgr_sha256'], 'decoded annotation pixels mismatch')
                    name = f'frame-{i:06d}.png'
                    require(cv2.imwrite(str(destination/name), image), 'annotation image write failed')
                    index.append({'frame_id': i, 'file': name, 'frame_reference': frame_uri(manifest['media']['sha256'], i)})
                if i >= max(wanted): break
        require(len(index) == len(wanted), 'missing requested annotation frames')
        json_write(destination/'annotation-template.json', template)
        json_write(destination/'index.json', index)
        return index
    except BaseException as error:
        json_write(destination/'failure.json', {'status': 'FAIL', 'error': str(error)})
        raise
