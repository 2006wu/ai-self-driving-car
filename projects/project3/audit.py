"""Read-only source provenance + structural comparison; never imports reference code."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from p3.detection import ROOT, MODEL, sha256

paths=['course-materials/2603 MR Projects.docx','course-materials/2609 AI Course Notes.docx',
       'external/aJLL/bodyjim/YoloPC.py','external/aJLL/bodyjim/follow_human.py',
       'external/aJLL/bodyjim/data_stream.py','external/aJLL/UI/uiviewJLL.py',
       'external/aJLL/UI/uiviewJLL1.py','projects/project3/artifacts/reference/uiview.py']
result={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'sources':{}, 'model_sha256':sha256(MODEL)}
for rel in paths:
    path=ROOT/rel
    if not path.exists():
        result['sources'][rel]={'status':'MISSING'};continue
    data={'sha256':sha256(path),'bytes':path.stat().st_size}
    if path.suffix=='.py':
        tree=ast.parse(path.read_text())
        data['imports']=[ast.unparse(n) for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
        data['functions']=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
        data['literal_process_lists']=[ast.literal_eval(n.value) for n in ast.walk(tree)
           if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='procs' for t in n.targets)]
    result['sources'][rel]=data
exact=ast.parse((ROOT/paths[-1]).read_text());jll=ast.parse((ROOT/paths[-3]).read_text())
result['uiview_same_active_ast']=ast.dump(exact)==ast.dump(jll)
result['uiview_download_url']='https://drive.usercontent.google.com/download?id=1Sf4PztfOjutOdgJz7CqQow5UUZlW9xl8&export=download&confirm=t'
result['findings']={'ui_location':'C2C per exact source instructions',
 'network':'PC SSH over Wi-Fi for remote shell / source transfer. No PC video-stream API in this script.',
 'IPC':'cereal local PubMaster: controlsState/deviceState/pandaStates/carParams',
 'params':'exact script persistently writes CarParams(notCar=True); not executed against host/device',
 'model':'exact script starts modeld using device model; not Run1 YOLO',
 'mock_scope':'injected process/cereal API only; no Capnp serialization, msgq IPC, Wi-Fi or hardware verification'}
with Path('evidence/source-audit.json').open('x') as f: json.dump(result,f,indent=2)
print('Source provenance written; no reference code executed.')
