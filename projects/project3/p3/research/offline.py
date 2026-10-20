"""Standalone local-file CLI. Opt-in: p3.cli defaults are unchanged.

Original media may be an absolute path, or relative to --media-root / P3_MEDIA_ROOT.
validate exits 0 with WARN when recorded data is intact but original media is absent.
A present file whose size or SHA256 differs is still a failure.
"""
import argparse
from pathlib import Path

from .dataset import loads
from .dataset_v2 import json_write, quality_report, load_bundle
from .recorder import record_media
from .annotations import annotation_template, validate_annotations, extract_annotation_frames
from .evaluate_dataset import compare_dataset


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
    quality.add_argument('--verify-pixels', action='store_true')
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
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('dataset'); evaluate.add_argument('--output', required=True)
    evaluate.add_argument('--annotations')
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
            report = quality_report(args.dataset, verify_pixels=args.verify_pixels, media_root=args.media_root)
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
        elif args.command == 'evaluate':
            annotations = loads(Path(args.annotations).read_text()) if args.annotations else None
            report = compare_dataset(args.dataset, annotations, media_root=args.media_root)
            json_write(args.output, report)
            print(report['real_accuracy_status'])
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
