"""Bounded, reproducible software validation. Local files only, no camera/network.

Commands from projects/project3. Each output folder must be new/empty.
"""
import argparse
import json
from pathlib import Path
import time
import psutil
import onnxruntime as ort

from p3.evaluation import benchmark, stats, environment
from p3.tracking import Tracker
from p3.scenarios import scenario_suite


def write(path, value):
    with path.open('x') as stream: json.dump(value, stream, indent=2, allow_nan=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--samples',type=int,default=30)
    args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise FileExistsError(out)
    write(out/'tracking-synthetic.json',scenario_suite())
    scenarios=[('cpu-image','CPUExecutionProvider','artifacts/bus.jpg',False,False,None,.3),
               ('cpu-track-follow','CPUExecutionProvider','artifacts/bus.jpg',True,True,None,.3),
               ('cpu-source-small','CPUExecutionProvider','artifacts/bus.jpg',True,True,(640,480),.3),
               ('cpu-source-large','CPUExecutionProvider','artifacts/bus.jpg',True,True,(1920,1080),.3),
               ('cpu-conf50','CPUExecutionProvider','artifacts/bus.jpg',True,True,None,.5),
               ('cpu-video','CPUExecutionProvider','artifacts/inputs/usa.hevc',True,True,None,.3)]
    if 'CoreMLExecutionProvider' in ort.get_available_providers():
        scenarios += [('coreml-image','CoreMLExecutionProvider','artifacts/bus.jpg',False,False,None,.3),
                      ('coreml-track-follow','CoreMLExecutionProvider','artifacts/bus.jpg',True,True,None,.3),
                      ('coreml-video','CoreMLExecutionProvider','artifacts/inputs/usa.hevc',True,True,None,.3)]
    for name,provider,source,tracking,follow,resolution,conf in scenarios:
        result=benchmark(source,args.samples,5,provider,conf,resolution,tracking,follow)
        write(out/f'{name}.json',result)
        print(name,round(result['inference_fps'],2),round(result['file_pipeline_fps'],2),flush=True)
    workloads=[]
    for count in [1,2,5,10,20]:
        tracker=Tracker();latencies=[];rss=[]
        for i in range(1005):
            detections=[{'class_id':0,'label':'person','objectness':.9,'box':[j*80+i%5,100,j*80+i%5+40,200]} for j in range(count)]
            start=time.perf_counter();tracker.update(detections);end=time.perf_counter()
            if i>=5:latencies.append((end-start)*1000);rss.append(psutil.Process().memory_info().rss)
        workloads.append({'synthetic_person_boxes':count,'tracking_ms':stats(latencies),'max_sampled_rss_bytes':max(rss)})
    write(out/'tracking-workload.json',{'environment':environment(),'scope':'synthetic box-only tracker cost, not detector or camera FPS','workloads':workloads})


if __name__=='__main__':main()
