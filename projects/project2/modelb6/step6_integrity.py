"""Hash immutable inputs and Step 5 outputs before/after the Step 6 experiment."""

import argparse
import json
from pathlib import Path

from step6 import OUTPUT, sha256, write_json


ROOTS = (Path('/workspace/professor'), Path('/data/dataB6'),
         Path('/opt/openpilot/tools/replay/dataC'), Path('/derived/step5'),
         Path('/output/step5'))
BASELINE = OUTPUT / 'integrity_before.json'


def inventory():
    records = {}
    for root in ROOTS:
        if not root.is_dir():
            raise FileNotFoundError(root)
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                records[str(path)] = {'link_target': str(path.readlink())}
            elif path.is_file():
                records[str(path)] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('snapshot', 'verify'))
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    current = inventory()
    if args.command == 'snapshot':
        if BASELINE.exists():
            raise FileExistsError(BASELINE)
        write_json(BASELINE, current)
        print(json.dumps({'status': 'snapshot', 'files': len(current), 'path': str(BASELINE)}))
    else:
        expected = json.loads(BASELINE.read_text())
        missing = sorted(set(expected) - set(current))
        new = sorted(set(current) - set(expected))
        changed = sorted(key for key in expected.keys() & current.keys() if expected[key] != current[key])
        result = {'status': 'PASS' if not (missing or new or changed) else 'FAIL',
                  'files': len(current), 'missing': missing, 'new': new, 'changed': changed}
        print(json.dumps(result, indent=2))
        if result['status'] != 'PASS':
            raise RuntimeError('Step 6 input / Step 5 integrity changed')


if __name__ == '__main__':
    main()
