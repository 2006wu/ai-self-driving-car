"""Standalone Milestone 2 local-file CLI; original p3.cli defaults unchanged."""
import argparse
from pathlib import Path

from .dataset import loads
from .dataset_v2 import json_write, quality_report, load_bundle
from .recorder import record_media
from .annotations import annotation_template, validate_annotations, extract_annotation_frames
from .evaluate_dataset import compare_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    record = sub.add_parser('record')
    record.add_argument('source'); record.add_argument('--output', required=True)
    record.add_argument('--max-frames', type=int, default=120)
    record.add_argument('--tracker', choices=('greedy_iou', 'hungarian'), default='greedy_iou')
    record.add_argument('--selection-schedule', help='JSON object: zero-based frame index -> track ID, or null to cancel')
    quality = sub.add_parser('validate')
    quality.add_argument('dataset'); quality.add_argument('--output', required=True)
    quality.add_argument('--verify-pixels', action='store_true')
    annotate = sub.add_parser('template')
    annotate.add_argument('dataset'); annotate.add_argument('--output', required=True)
    annotate.add_argument('--frames', help='comma-separated decoded indices; default all recorded frames')
    extract = sub.add_parser('extract')
    extract.add_argument('dataset'); extract.add_argument('--output', required=True)
    extract.add_argument('--frames', required=True)
    check = sub.add_parser('validate-annotations')
    check.add_argument('dataset'); check.add_argument('annotations')
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('dataset'); evaluate.add_argument('--output', required=True)
    evaluate.add_argument('--annotations')
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
                                  method=args.tracker, selection_schedule=schedule)
            print(result['session_id'])
        elif args.command == 'validate':
            report = quality_report(args.dataset, verify_pixels=args.verify_pixels)
            json_write(args.output, report)
            if report['status'] != 'PASS': parser.exit(2, 'Dataset validation failed; see quality report.\n')
            print('PASS')
        elif args.command in {'template', 'extract'}:
            ids = [int(i) for i in args.frames.split(',')] if args.frames else None
            if args.command == 'template': json_write(args.output, annotation_template(args.dataset, ids))
            else: extract_annotation_frames(args.dataset, args.output, ids)
        elif args.command == 'validate-annotations':
            manifest, records = load_bundle(args.dataset)
            validate_annotations(loads(Path(args.annotations).read_text()), manifest, records)
            print('PASS: structural reviewed-human annotation contract; source truth requires human review')
        elif args.command == 'evaluate':
            annotations = loads(Path(args.annotations).read_text()) if args.annotations else None
            report = compare_dataset(args.dataset, annotations)
            json_write(args.output, report)
            print(report['real_accuracy_status'])
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
