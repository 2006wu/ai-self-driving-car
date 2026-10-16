"""Supplemental real-model perturbation and load-time evidence; no accuracy claims."""
import json
from pathlib import Path
import cv2
import numpy as np
from p3.detection import Detector, sha256
from p3.evaluation import environment, stats
from p3.tracking import Tracker

out=Path('evidence/supplemental.json')
if out.exists(): raise FileExistsError(out)
image=cv2.imread('artifacts/bus.jpg')
if image is None: raise ValueError('fetch bus.jpg first')
model=Detector()
occluded=image.copy(); h,w=image.shape[:2]
occluded[h//4:3*h//4,:w//2]=0
variants={'original':image,'low_light_25pct':(image*.25).astype(np.uint8),
          'motion_blur_horizontal':cv2.filter2D(image,-1,np.ones((1,31),np.float32)/31),
          'partial_occlusion':occluded,'all_black':np.zeros_like(image)}
result={'environment':environment(),'input_sha256':sha256('artifacts/bus.jpg'),
        'limitations':'Deterministic image perturbations, not real low-light/motion trials or accuracy/identity metrics.',
        'variants':{},'model_load_ms':{}}
for name,img in variants.items():
    ds,t=model.predict(img)
    result['variants'][name]={'detections':len(ds),'persons':sum(d['class_id']==0 for d in ds),
                              'objectness':[d['objectness'] for d in ds],'timing':t}
for provider in ['CPUExecutionProvider','CoreMLExecutionProvider']:
    loads=[]
    for _ in range(5):
        candidate=Detector(provider=provider)
        loads.append(candidate.load_ms)
        del candidate
    result['model_load_ms'][provider]=stats(loads)
# Provider comparison is real output comparison, not ground truth.
core=Detector(provider='CoreMLExecutionProvider')
tensor=model.preprocess(image)
a=model.session.run(None,{'image':tensor})[0]
b=core.session.run(None,{'image':tensor})[0]
result['provider_comparison']={'raw_mean_abs':float(np.abs(a-b).mean()),
 'raw_max_abs':float(np.abs(a-b).max()),
 'cpu_detections':model.predict(image)[0],'coreml_detections':core.predict(image)[0],
 'note':'CoreML uses CPU fallback partitions; hardware unit/GPU utilization not measured.'}
with out.open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(result['model_load_ms'],indent=2))
