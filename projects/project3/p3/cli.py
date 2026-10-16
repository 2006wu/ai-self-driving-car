import argparse
import json
from pathlib import Path

from .detection import Detector, sha256
from .evaluation import benchmark, environment
from .pipeline import run


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def main():
    parser = argparse.ArgumentParser(description='Project 3 perception; no robot controls')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('--output')
    for name in ['run','benchmark']:
        item = sub.add_parser(name)
        item.add_argument('source')
        item.add_argument('--output', required=True)
        item.add_argument('--provider', default='CPUExecutionProvider')
        item.add_argument('--confidence', type=float, default=.3)
        if name == 'run':
            item.add_argument('--camera', action='store_true')
            item.add_argument('--display', action='store_true')
            item.add_argument('--track', action='store_true')
            item.add_argument('--max-frames', type=int, default=300)
            item.add_argument('--max-seconds', type=float)
            item.add_argument('--no-record', action='store_true')
            item.add_argument('--simulate-follow', action='store_true')
            item.add_argument('--target-id', type=int)
        else:
            item.add_argument('--samples', type=int, default=30)
            item.add_argument('--track', action='store_true')
            item.add_argument('--simulate-follow', action='store_true')
            item.add_argument('--warmup', type=int, default=5)
            item.add_argument('--resolution', help='source frame widthxheight; model stays 640x416')
    tracking = sub.add_parser('tracking-eval', help='evaluate annotated JSON box sequence')
    tracking.add_argument('source')
    tracking.add_argument('--output', required=True)
    tracking.add_argument('--iou', type=float, default=.5)
    fixtures = sub.add_parser('tracking-fixtures', help='synthetic evaluation only')
    fixtures.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'tracking-fixtures':
            from .scenarios import scenario_suite
            save(args.output, scenario_suite())
        elif args.command == 'tracking-eval':
            from .tracking_eval import evaluate_sequence
            data=json.loads(Path(args.source).read_text())
            result=evaluate_sequence(data['frames'],data['annotation_kind'],args.iou,data.get('target_gt_id'))
            result['input_sha256']=sha256(args.source)
            save(args.output,result)
        elif args.command == 'check':
            info = {'environment': environment(), 'model': Detector().info}
            if args.output:
                save(args.output, info)
            print(json.dumps(info, indent=2))
        elif args.command == 'benchmark':
            resolution = tuple(map(int,args.resolution.split('x'))) if args.resolution else None
            if resolution and (len(resolution)!=2 or min(resolution)<1):
                raise ValueError('resolution must be positive widthxheight')
            result = benchmark(args.source,args.samples,args.warmup,args.provider,args.confidence,resolution,args.track,args.simulate_follow)
            save(args.output,result)
            print(json.dumps({k:result[k] for k in ['inference_fps','file_pipeline_fps','requested_samples']}))
        else:
            if args.simulate_follow and not args.track:
                raise ValueError('--simulate-follow requires --track')
            if args.target_id is not None and not args.simulate_follow:
                raise ValueError('--target-id requires --simulate-follow')
            if args.track:
                from .tracking import Tracker
            from .follow import FollowController
            detector = Detector(provider=args.provider,conf=args.confidence)
            records = run(detector,args.source,args.output,args.camera,args.max_frames,args.display,
                          Tracker() if args.track else None,
                          FollowController() if args.simulate_follow else None,args.target_id,args.max_seconds,not args.no_record)
            save(Path(args.output)/'run.json',{'environment':environment(),'model':detector.info,
                 'input':args.source,'input_sha256':None if args.camera else sha256(args.source),
                 'camera':args.camera,'display':args.display,'tracking':args.track,'max_frames':args.max_frames,
                 'scope':'acquisition + detector + optional tracking + overlay + optional GUI wait; export IO excluded',
                 'frames':records})
            print(f'processed {len(records)} frame(s); evidence: {args.output}')
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped by user; resources released and simulated output STOP.\n')
    except Exception as error:
        parser.exit(2, f'ERROR: {error}\n')


if __name__ == '__main__':
    main()
