"""Export fixed existing evidence and Step 6 PNGs; never modify source volumes."""
import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from v2_evidence import CANONICAL, ROOT, approved_path

REPO = Path(__file__).resolve().parents[3]
# No user path or code interpolation reaches the container. Only fixed canonical files.
COLLECT = """
import base64,hashlib,json
from pathlib import Path
base=Path('/output')
paths=PATHS
for domain in ('usa','taiwan'):
    for role in ('final','best'):
        p=base/'step6'/domain/role
        m=json.loads((p/'manifest.json').read_text())
        if m['status']!='complete' or m['run_type']!='production' or m['domain']!=domain or m['model']['role']!=role:
            raise ValueError('invalid production manifest')
        for name,h in m['artifact_sha256'].items():
            if name.endswith('.png'):
                f=p/name
                if Path(name).name!=name or f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=h:
                    raise ValueError('invalid production image')
                paths.append(str(f.relative_to(base)))
        paths.append(str((p/'manifest.json').relative_to(base)))
result={}
for rel in paths:
    p=base/rel
    if p.is_symlink() or base not in p.resolve().parents: raise ValueError('unsafe source')
    raw=p.read_bytes()
    if len(raw)>5000000: raise ValueError('source too large')
    result[rel]={'source':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content':base64.b64encode(raw).decode()}
print(json.dumps(result))
"""


def collect():
    script = COLLECT.replace('PATHS', repr(list(CANONICAL.values())))
    result = subprocess.run(['docker','run','--rm','--network','none','--read-only',
        '--mount','type=volume,src=ai-self-driving-car_modelb6-output,dst=/output,readonly',
        '--entrypoint','python3.8','ai-self-driving-car-modelb6:latest','-c',script],
        capture_output=True, text=True, check=True, cwd=REPO)
    return json.loads(result.stdout)


def export(verify=False):
    bundle = collect()
    entries = {}
    for rel, entry in bundle.items():
        raw = base64.b64decode(entry['content'], validate=True)
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('transfer hash mismatch')
        p = approved_path(rel)
        if p.exists():
            if p.read_bytes() != raw: raise ValueError('existing export differs')
        elif verify:
            raise FileNotFoundError(p)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as stream: stream.write(raw)
        entries[rel] = {k: entry[k] for k in ('source','sha256','bytes')}
    raw = (json.dumps({'version': 1, 'files': entries}, indent=2, sort_keys=True)+'\n').encode()
    p = approved_path('export_manifest.json')
    if p.exists():
        if p.read_bytes()!=raw: raise ValueError('export manifest differs')
    elif verify: raise FileNotFoundError(p)
    else:
        with p.open('xb') as stream: stream.write(raw)
    return {'status':'PASS','files':len(entries),'mode':'verify' if verify else 'export'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true')
    print(json.dumps(export(parser.parse_args().verify)))
