"""Standalone local-file CLI. Opt-in: p3.cli defaults are unchanged.

Original media may be an absolute path, or relative to --media-root / P3_MEDIA_ROOT.
validate exits 0 with WARN when recorded data is intact but original media is absent.
--require-media and --verify-pixels exit 2 when that file is absent.
A present file whose size or SHA256 differs is still a failure.
"""
import argparse
from pathlib import Path

from .dataset import loads
from .dataset_v2 import canonical, json_write, quality_report, load_bundle
from .recorder import record_media
from .annotations import annotation_template, validate_annotations, extract_annotation_frames
from .evaluate_dataset import compare_dataset
from .mot_import import import_mot


def add_media_root(parser):
    parser.add_argument('--media-root',
                        help='Directory original media is stored under. Overrides P3_MEDIA_ROOT. '
                             'record stores a relative path; validate resolves it, and can match a '
                             'byte-identical copy of a legacy absolute path under this directory.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    record = sub.add_parser('record')
    record.add_argument('source'); record.add_argument('--output', required=True)
    record.add_argument('--max-frames', type=int, default=120)
    record.add_argument('--tracker', choices=('greedy_iou', 'hungarian'), default='greedy_iou')
    record.add_argument('--selection-schedule', help='JSON object: zero-based frame index -> track ID, or null to cancel')
    add_media_root(record)
    quality = sub.add_parser('validate')
    quality.add_argument('dataset'); quality.add_argument('--output', required=True)
    quality.add_argument('--verify-pixels', action='store_true',
                         help='Re-decode original frames and fail if the media file is absent or pixels differ.')
    quality.add_argument('--require-media', action='store_true',
                         help='Fail when the original media file is absent. Implied by --verify-pixels.')
    add_media_root(quality)
    annotate = sub.add_parser('template')
    annotate.add_argument('dataset'); annotate.add_argument('--output', required=True)
    annotate.add_argument('--frames', help='comma-separated decoded indices; default all recorded frames')
    add_media_root(annotate)
    extract = sub.add_parser('extract')
    extract.add_argument('dataset'); extract.add_argument('--output', required=True)
    extract.add_argument('--frames', required=True)
    add_media_root(extract)
    check = sub.add_parser('validate-annotations')
    check.add_argument('dataset'); check.add_argument('annotations')
    add_media_root(check)
    mot = sub.add_parser('import-mot', help='Import local MOT/CVAT MOT 1.1 ground truth as draft annotations')
    mot.add_argument('dataset'); mot.add_argument('source', help='Exported gt/gt.txt (not detector results)')
    mot.add_argument('--output', required=True)
    mot.add_argument('--frame-offset', type=int, default=0, help='MOT frame n maps to dataset n-1+offset')
    mot.add_argument('--frame-count', type=int, help='Contiguous labeled span length; default all remaining dataset frames')
    mot.add_argument('--box-origin', type=int, choices=(0, 1), default=1, help='MOT x/y origin; default 1, converted to zero-based pixels')
    mot.add_argument('--clip-boxes', action='store_true', help='Clip to frame bounds and report every changed box')
    mot.add_argument('--human-verified', action='store_true', help='Attest every imported frame and identity has been human reviewed')
    mot.add_argument('--annotator', default=''); mot.add_argument('--reviewer', default='')
    mot.add_argument('--target-person-id', type=int)
    add_media_root(mot)
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('dataset'); evaluate.add_argument('--output', required=True)
    evaluate.add_argument('--annotations')
    evaluate.add_argument('--trackers', help='Opt-in comparison: all or comma-separated greedy_iou,hungarian,kalman_iou')
    add_media_root(evaluate)
    args = parser.parse_args()
    try:
        if args.command == 'record':
            schedule = None
            if args.selection_schedule:
                raw = loads(Path(args.selection_schedule).read_text())
                if not isinstance(raw, dict) or any(not k.isdecimal() or str(int(k)) != k for k in raw):
                    raise ValueError('schedule requires canonical nonnegative decimal frame keys')
                schedule = {int(k): v for k, v in raw.items()}
            result = record_media(args.source, args.output, max_frames=args.max_frames,
                                  method=args.tracker, selection_schedule=schedule, media_root=args.media_root)
            print(result['session_id'])
        elif args.command == 'validate':
            report = quality_report(args.dataset, verify_pixels=args.verify_pixels, media_root=args.media_root,
                                    require_media=args.require_media)
            json_write(args.output, report)
            if report['status'] == 'FAIL':
                parser.exit(2, 'Dataset validation failed; see quality report.\n')
            if report['status'] == 'WARN':
                print('WARN')
                for warning in report['warnings']:
                    print(warning)
            else:
                print('PASS')
        elif args.command in {'template', 'extract'}:
            ids = [int(i) for i in args.frames.split(',')] if args.frames else None
            if args.command == 'template':
                json_write(args.output, annotation_template(args.dataset, ids, media_root=args.media_root))
            else:
                extract_annotation_frames(args.dataset, args.output, ids, media_root=args.media_root)
        elif args.command == 'validate-annotations':
            manifest, records = load_bundle(args.dataset, media_root=args.media_root)
            validate_annotations(loads(Path(args.annotations).read_text()), manifest, records)
            print('PASS: structural reviewed-human annotation contract; source truth requires human review')
        elif args.command == 'import-mot':
            summary = import_mot(args.dataset, args.source, args.output,
                frame_offset=args.frame_offset, frame_count=args.frame_count, box_origin=args.box_origin,
                clip_boxes=args.clip_boxes, human_verified=args.human_verified,
                annotator=args.annotator, reviewer=args.reviewer, target_person_id=args.target_person_id,
                media_root=args.media_root)
            print(canonical(summary))
        elif args.command == 'evaluate':
            annotations = loads(Path(args.annotations).read_text()) if args.annotations else None
            report = compare_dataset(args.dataset, annotations, media_root=args.media_root, trackers=args.trackers)
            json_write(args.output, report)
            print(report['real_accuracy_status'])
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
