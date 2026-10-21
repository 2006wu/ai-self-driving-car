"""Run synthetic closed-loop comparisons. Output files must be new."""
import argparse
import json
from pathlib import Path
from .controllers import RuleBasedController
from .pid_controller import PIDConfig, PIDFollowController
from .closed_loop import SCENARIOS, SimConfig, run_scenario


def compare(controller='both', gains=None, scenarios=SCENARIOS, steps=200, seed=None):
    gains = gains or PIDConfig()
    names = ('rule', 'pid') if controller == 'both' else (controller,)
    if any(name not in ('rule', 'pid') for name in names):
        raise ValueError('unknown controller')
    results = {}
    for scenario in scenarios:
        results[scenario] = {name: run_scenario(
            RuleBasedController() if name == 'rule' else PIDFollowController(gains),
            scenario, steps, seed=seed) for name in names}
    wins = {metric: sum(row['pid'][metric] < row['rule'][metric]
                       for row in results.values()
                       if row.get('pid', {}).get(metric) is not None and row.get('rule', {}).get(metric) is not None)
            for metric in ('centering_rms', 'distance_rms_m')} if controller == 'both' else {}
    return {'kind': 'synthetic_kinematic_simulation', 'config': SimConfig().to_dict(),
            'gains': gains.to_dict(), 'scenarios': results,
            'summary': {'pid_wins': wins, 'scenario_count': len(results),
                        'all_safety_pass': all(m['safety_pass'] for row in results.values() for m in row.values())}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller', choices=('rule', 'pid', 'both'), default='both')
    parser.add_argument('--gains')
    parser.add_argument('--scenarios', default=','.join(SCENARIOS))
    parser.add_argument('--steps', type=int, default=200)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        path = Path(args.output)
        if path.exists():
            raise FileExistsError(f'output already exists: {path}')
        result = compare(args.controller, PIDConfig.from_json(args.gains) if args.gains else None,
                         args.scenarios.split(','), args.steps, args.seed)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print('scenario        controller  center RMS  distance RMS(m)  safety')
    for scenario, row in result['scenarios'].items():
        for name, metrics in row.items():
            center = metrics['centering_rms']
            center_text = f'{center:.4f}' if center is not None else 'N/A'
            print(f'{scenario:15} {name:10} {center_text:>10} {metrics["distance_rms_m"]:16.4f}  {metrics["safety_pass"]}')
    return 0


if __name__ == '__main__':
    main()
