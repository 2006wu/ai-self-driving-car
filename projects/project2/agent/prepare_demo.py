"""Export verified small evidence JSON from Docker volumes for the host Agent."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from evidence_agent import ARTIFACTS, summarize_p2_evidence

REPO = Path(__file__).resolve().parents[3]
# Fixed source paths; this code only reads the isolated container's mounted data.
COLLECT = '''
import json
from pathlib import Path
import step6
import step9_gradient_audit as p29
import step10_gradient_controls as p210
inventory = p29.inventory()
for base in (p29.OUTPUT, p210.OUTPUT):
    for p in sorted(base.rglob('*')):
        if p.is_file():
            inventory[str(p)] = {'bytes': p.stat().st_size, 'sha256': step6.sha256(p)}
for base in (p29.OUTPUT, p210.OUTPUT):
    m=json.loads((base/'run_metadata.json').read_text())
    for name, h in m['artifacts'].items():
        if Path(name).name != name or step6.sha256(base/name) != h:
            raise RuntimeError('saved artifact changed: '+name)
print(json.dumps({'protected_inventory': inventory,
    'p29': json.loads((p29.OUTPUT/'summary.json').read_text()),
    'p210': json.loads((p210.OUTPUT/'summary.json').read_text()),
    'p210_verification': p210.verify_results()}))
'''


def preserve(path, value):
    """An identical export may be reused; differing evidence is never overwritten."""
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('existing export differs: ' + str(path))
    else:
        with path.open('xb') as stream: stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='compare all protected files with this closure snapshot')
    args = parser.parse_args()
    result = subprocess.run(['docker','compose','-f',str(REPO/'docker/docker-compose.yaml'),
                             '--profile','project2','run','--rm','--no-deps','modelb6',
                             'python3.8','-c',COLLECT], cwd=REPO, capture_output=True, text=True, check=True)
    bundle = json.loads(result.stdout)
    snapshot = ARTIFACTS/'closure_integrity_before.json'
    if args.verify:
        if json.loads(snapshot.read_text()) != bundle['protected_inventory']:
            raise ValueError('protected files changed since closure snapshot')
        print(json.dumps({'status':'PASS','protected_files':len(bundle['protected_inventory']),
                          'p210':bundle['p210_verification']['status']}))
        return
    preserve(snapshot, bundle['protected_inventory'])
    preserve(ARTIFACTS/'p29-gradient-audit/summary.json', bundle['p29'])
    preserve(ARTIFACTS/'p210-gradient-controls/summary.json', bundle['p210'])
    preserve(ARTIFACTS/'p210-verification.json', bundle['p210_verification'])
    demo = {'mode':'offline_tool_only','gemini_executed':False,
            'evidence':summarize_p2_evidence()}
    preserve(ARTIFACTS/'offline_demo.json',demo)
    print(json.dumps({'status':'PASS','mode':demo['mode'],
                      'protected_files':len(bundle['protected_inventory']),
                      'demo':str(ARTIFACTS/'offline_demo.json'),
                      'demo_sha256':hashlib.sha256((ARTIFACTS/'offline_demo.json').read_bytes()).hexdigest()}))


if __name__ == '__main__': main()
