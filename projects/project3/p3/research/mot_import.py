"""Import local MOT ground truth, never detector predictions, into annotations/1.0."""
import csv
import hashlib
import math
from pathlib import Path

from .annotations import annotation_template, validate_annotations
from .dataset import integer, require
from .dataset_v2 import canonical, json_write, load_bundle


def import_mot(directory, source, output, *, frame_offset=0, frame_count=None,
               box_origin=1, clip_boxes=False, human_verified=False,
               annotator='', reviewer='', target_person_id=None, media_root=None):
    """MOT frame n -> dataset n-1+offset; x/y -> zero-based x/y minus origin.

    The selected contiguous span includes empty frames. Optional columns are
    mark (0/1), class (positive integer; 1=pedestrian), visibility ([0,1]).
    All rows are validated before mark=0/non-pedestrian rows are excluded.
    Clipping and exclusions are retained in provenance.reference as JSON and
    returned to the CLI. This is not full MOTChallenge ignore preprocessing.
    """
    output = Path(output)
    if output.exists():
        raise FileExistsError('output already exists; choose a new path')
    require(integer(frame_offset), 'frame offset must be a nonnegative dataset index')
    require(type(box_origin) is int and box_origin in (0, 1), 'box origin must be 0 or 1')
    require(type(human_verified) is bool, 'human_verified must be boolean')
    require(isinstance(annotator, str) and isinstance(reviewer, str), 'annotator/reviewer must be strings')
    if human_verified:
        require(annotator.strip() and reviewer.strip(), '--human-verified requires annotator and reviewer')
    require(target_person_id is None or integer(target_person_id, 1), 'target person ID must be positive')
    manifest, records = load_bundle(directory, media_root=media_root)
    count = len(records)-frame_offset if frame_count is None else frame_count
    require(integer(count, 1) and frame_offset+count <= len(records), 'invalid import frame span')
    document = annotation_template(directory, range(frame_offset, frame_offset+count), media_root=media_root)
    document['target_person_id'] = target_person_id
    frames = {f['frame_id']: f for f in document['frames']}
    raw = Path(source).read_bytes()
    summary = {'format': 'MOT ground truth', 'source': str(source),
               'source_sha256': hashlib.sha256(raw).hexdigest(),
               'frame_mapping': 'dataset_frame_id = mot_frame - 1 + frame_offset',
               'frame_offset': frame_offset, 'frame_count': count, 'box_origin': box_origin,
               'rows': 0, 'imported_person_rows': 0, 'ignored_mark_zero_rows': 0,
               'ignored_non_person_rows': 0, 'clipped_boxes': [],
               'empty_frame_policy': 'Rows absent within the imported span mean no annotated persons; review every frame.'}
    seen, columns = set(), None
    for line, row in enumerate(csv.reader(raw.decode('utf-8-sig').splitlines()), 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        try:
            require(6 <= len(row) <= 9, 'expected 6 to 9 columns: frame,id,x,y,w,h[,mark[,class[,visibility]]]')
            if columns is None:
                columns = len(row)
            require(len(row) == columns, 'inconsistent column count')
            values = [float(cell) for cell in row]
            require(all(math.isfinite(v) for v in values), 'all columns must be finite numbers')
            frame, pid, x, y, width, height = values[:6]
            require(frame.is_integer() and frame >= 1, 'MOT frame must be a positive integer')
            require(pid.is_integer() and pid >= 1, 'person ID must be a positive integer')
            index, pid = int(frame)-1+frame_offset, int(pid)
            require(index in frames, 'MOT frame outside imported dataset frame span')
            require((index, pid) not in seen, 'duplicate person ID within a frame')
            seen.add((index, pid))
            require(width > 0 and height > 0, 'box must have positive width and height')
            mark = values[6] if len(values) >= 7 else 1
            category = values[7] if len(values) >= 8 else 1.
            visibility = values[8] if len(values) >= 9 else 1
            require(mark in (0, 1), 'GT mark must be 0 or 1 (detector confidence is not ground truth)')
            require(category.is_integer(), 'class must be an integer')
            require(category >= 1, 'class must be positive; class 1 is pedestrian')
            require(0 <= visibility <= 1, 'visibility must be within [0,1]')
            box = [x-box_origin, y-box_origin, x-box_origin+width, y-box_origin+height]
            require(all(math.isfinite(v) for v in box), 'box coordinates overflow')
            target_frame = frames[index]
            clipped = [max(0., box[0]), max(0., box[1]),
                       min(target_frame['width'], box[2]), min(target_frame['height'], box[3])]
            if clipped != box:
                require(clip_boxes, 'box outside image bounds; use --clip-boxes to clip explicitly')
                require(clipped[0] < clipped[2] and clipped[1] < clipped[3], 'box has no positive area inside image')
                summary['clipped_boxes'].append({'line': line, 'frame_id': index, 'person_id': pid,
                                                  'original': box, 'clipped': clipped})
                box = clipped
            summary['rows'] += 1
            if mark == 0:
                summary['ignored_mark_zero_rows'] += 1
            elif category != 1:
                summary['ignored_non_person_rows'] += 1
            else:
                target_frame['persons'].append({'person_id': pid, 'box': box,
                    'occlusion': 'none' if visibility == 1 else 'full' if visibility == 0 else 'partial'})
                summary['imported_person_rows'] += 1
        except (ValueError, OverflowError) as error:
            raise ValueError(f'MOT line {line}: {error}') from error
    require(summary['rows'] > 0, 'MOT file contains no rows')
    people = {p['person_id'] for f in document['frames'] for p in f['persons']}
    require(target_person_id is None or target_person_id in people, 'unknown imported target identity')
    for frame in document['frames']:
        frame['persons'].sort(key=lambda p: p['person_id'])
        frame['reviewed'] = human_verified
    document['status'] = 'reviewed' if human_verified else 'draft'
    document['provenance'] = {'kind': 'human_annotation' if human_verified else 'pending_human_annotation',
                              'annotator': annotator, 'reviewer': reviewer, 'reference': canonical(summary)}
    validate_annotations(document, manifest, records, require_reviewed=human_verified)
    json_write(output, document)  # Exclusive creation also prevents overwrite races.
    return dict(summary, status=document['status'])
