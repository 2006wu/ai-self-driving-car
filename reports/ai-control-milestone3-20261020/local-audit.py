"""Reproduce local evidence inspection only; never create ground truth or run metrics.

From repo root:
PYTHONPATH=projects/project3 projects/project3/.venv/bin/python reports/ai-control-milestone3-20261020/local-audit.py --output reports/my-new-milestone3-audit
Output directory must not already exist. Original media and prior evidence read-only.
"""
import argparse
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from p3.pipeline import Frames, VIDEO_SUFFIXES
from p3.research.dataset import loads
from p3.research.dataset_v2 import digest, json_write, load_bundle
from p3.research.annotations import validate_annotations


def audit(out):
    candidates = subprocess.check_output(['rg', '--files', '--hidden', '--no-ignore',
        '-g', '!**/.git/**', '-g', '!**/.venv/**', '-g', '!**/node_modules/**',
        '-g', '!**/__pycache__/**']).decode().splitlines()
    videos = []
    for name in sorted(candidates):
        path = Path(name)
        if path.suffix.lower() not in VIDEO_SUFFIXES: continue
        role = ('original local USA input' if name == 'projects/project3/artifacts/inputs/usa.hevc' else
                'rendered overlay; excluded' if path.name == 'overlay.avi' else 'unverified provenance; excluded pending review')
        videos.append({'path': name, 'bytes': path.stat().st_size, 'sha256': digest(path), 'role': role})
    source = Path('projects/project3/artifacts/inputs/usa.hevc')
    history = Path('projects/project3/artifacts/validation-20261016/stability-video-final/run.json')
    saved = loads(history.read_text())
    assert saved['input_sha256'] == digest(source), 'historical predictions do not match original source bytes'
    rows = saved['frames']
    person_frames = [r['frame'] for r in rows if any(d['class_id'] == 0 for d in r['detections'])]
    multi = [r['frame'] for r in rows if sum(d['class_id'] == 0 for d in r['detections']) >= 2]
    wanted = sorted(set(range(0, len(rows), 100)) | set(person_frames) | {len(rows)-1})
    tiles, indices, count = [], [], 0
    with Frames(str(source), camera=False) as frames:
        decoder_fps = frames.fps
        for index, image in enumerate(frames):
            count += 1
            if index not in wanted: continue
            tile = cv2.resize(image, (384, 256))
            caption = np.zeros((34,384,3), np.uint8)
            text = f'frame {index}; historical person det={int(index in person_frames)}'
            cv2.putText(caption, text, (6,22), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
            tiles.append(np.concatenate([caption,tile]))
            indices.append({'decoded_index': index, 'original_width': image.shape[1], 'original_height': image.shape[0],
                            'historical_person_detection': index in person_frames})
    assert count == len(rows), 'actual decode length differs from historical log'
    while len(tiles) % 4: tiles.append(np.zeros_like(tiles[0]))
    sheet = np.concatenate([np.concatenate(tiles[i:i+4], axis=1) for i in range(0,len(tiles),4)])
    if not cv2.imwrite(str(out/'audit-contact-sheet.jpg'),sheet):raise RuntimeError('contact sheet write failed')
    json_write(out/'audit-frame-index.json', {'scope':'AI visual survey only, NOT human annotation or benchmark media',
               'source':str(source),'source_sha256':digest(source),'frames':indices})
    json_write(out/'media-inventory.json', {'scope':'repository local files, excluding environments; no Docker/network access',
        'videos':videos,'original_usa':{'decoded_frames':count,'decoder_reported_fps':decoder_fps,
            'historical_log':str(history),'historical_log_sha256':digest(history),
            'historical_person_detection_frames':person_frames,'historical_multi_person_detection_frames':multi,
            'limits':'Detector observations are not GT or proof of absence. Visual survey is AI inspection, not independent human review.'},
        'image_fixture':{'path':'projects/project3/artifacts/bus.jpg','sha256':digest('projects/project3/artifacts/bus.jpg'),
            'role':'single real image; unsuitable for crossing/occlusion trajectories'},
        'annotation_candidates':[p for p in candidates if Path(p).suffix.lower()=='.json' and Path(p).name.startswith('annotation')
                                  and not p.startswith(str(out)+'/')]})
    checks = []
    for bundle, template in [
        ('reports/ai-control-milestone2-20261020/usa-verified', 'reports/ai-control-milestone2-20261020/annotation-template.json'),
        ('reports/ai-control-milestone2-20261020/image-sample', None)]:
        manifest, records = load_bundle(bundle, verify_pixels=True)
        entry = {'bundle':bundle,'status':'PASS','frames':len(records),'pixels_verified':True,
                 'session_id':manifest['session_id'],'records_sha256':manifest['records']['sha256']}
        if template:
            document = loads(Path(template).read_text())
            validate_annotations(document,manifest,records,require_reviewed=False)
            try:validate_annotations(document,manifest,records)
            except ValueError as error:entry['reviewed_annotation_gate']={'status':'BLOCKED','reason':str(error)}
            else:raise AssertionError('blank draft unexpectedly accepted as reviewed human GT')
            entry['draft_frames']=len(document['frames'])
            entry['reviewed_frames']=sum(f['reviewed'] for f in document['frames'])
            entry['annotated_person_rows']=sum(len(f['persons']) for f in document['frames'])
        checks.append(entry)
    json_write(out/'existing-tool-validation.json', {'checks':checks,
        'identity_metrics_executed':False,'reason':'No valid reviewed human annotations and no accepted real scenario suite'})


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    target=Path(args.output);target.mkdir(parents=True,exist_ok=False)
    audit(target)
