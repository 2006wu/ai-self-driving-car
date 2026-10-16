"""Validate P2.9 saved evidence and render reports without model execution."""
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from step6 import sha256, write_json

ROOT = Path('/output/p29-gradient-audit')


def finite(value):
    if isinstance(value, dict):
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite saved evidence')


def main():
    for name in ('README.md', 'interpretation.json', 'gradient_depth.png'):
        if (ROOT/name).exists(): raise FileExistsError(ROOT/name)
    metadata = json.loads((ROOT/'run_metadata.json').read_text())
    for name, expected in metadata['artifacts'].items():
        if sha256(ROOT/name) != expected: raise ValueError('artifact changed: '+name)
    records = json.loads((ROOT/'records.json').read_text())
    samples = json.loads((ROOT/'samples.json').read_text())['samples']
    summary = json.loads((ROOT/'summary.json').read_text())
    component = json.loads((ROOT/'component_gradients.json').read_text())
    for item in (records, samples, summary, component): finite(item)
    if len(records) != 144 or len(samples) != 18: raise ValueError('coverage changed')
    identities = set()
    for r in records:
        key=(r['role'],r['sample'],r['condition'])
        if key in identities: raise ValueError('duplicate record')
        identities.add(key)
        s=samples[r['sample']]
        if r['target_sha256'] != s['target_sha256']: raise ValueError('counterfactual target changed')
        if r['condition'] != 'zero_image' and r['image_sha256'] != s['image_sha256']: raise ValueError('image changed')
        if r['condition'] in ('original','zero_image') and r['state_sha256'] != s['state_sha256']: raise ValueError('state changed')
        if r['condition']=='mismatched_state' and r['state_sha256'] != samples[s['mismatched_state_sample']]['state_sha256']: raise ValueError('state replacement changed')
        if r['input_gradients']['image']['elements'] != 393216 or r['input_gradients']['state']['elements'] != 512: raise ValueError('input geometry changed')
    layers=('stem_activation','block1b_add','block3c_add','block4d_add','block5d_add',
            'block6e_add','block7b_add','top_activation','flatten')
    fig, axes=plt.subplots(1,2,figsize=(13,5))
    for ax,role in zip(axes,('final','best')):
        for condition in ('original','zero_state'):
            selected=[r for r in records if r['role']==role and r['condition']==condition]
            y=[np.median([r['activation_gradients'][name]['rms'] for r in selected]) for name in layers]
            ax.plot(range(len(layers)),y,marker='o',label=condition)
        ax.set_yscale('log'); ax.set_xticks(range(len(layers)))
        ax.set_xticklabels(layers,rotation=55,ha='right',fontsize=8)
        ax.set_title(role+' — median supervised gradient RMS')
        ax.set_ylabel('Gradient per activation element'); ax.grid(alpha=.25); ax.legend()
    fig.tight_layout(); fig.savefig(ROOT/'gradient_depth.png',dpi=160); plt.close(fig)
    table=['| Measure (median) | Final | Best |','| --- | ---: | ---: |']
    for label,key in (('Image input gradient RMS','image_rms'),('State input gradient RMS','state_rms'),
                      ('Image/state RMS ratio','image_state_ratio'),('Stem gradient RMS','stem_rms'),
                      ('Block4 gradient RMS','middle_rms'),('Top gradient RMS','late_rms'),('Original loss','loss')):
        values=[summary['aggregates'][role]['overall']['original'][key]['median'] for role in ('final','best')]
        table.append('| '+label+' | '+' | '.join('%.6g'%v for v in values)+' |')
    table.append('| Zero-state loss | '+' | '.join('%.6g'%summary['aggregates'][r]['overall']['zero_state']['loss']['median'] for r in ('final','best'))+' |')
    table.append('| Paired zero-state image-gradient amplification (15 nonzero histories) | '+' | '.join('%.6g'%summary['nonzero_history_counterfactuals'][r]['zero_state']['image_gradient_amplification']['median'] for r in ('final','best'))+' |')
    text='''# P2.9 supervised gradient attribution

Decision: **P2.9-B; H1 is the strongest shared explanation.** Both models have
strong encoder-gradient attenuation under the actual loss. Final-USA additionally
shows state-dependent image-gradient suppression. Best does not increase total
image gradient when state is removed, and Taiwan loss improves without state in
both models. A universal shortcut explanation is not established.

## Method

Original `train_modelB6.custom_loss` is differentiated with TensorFlow GradientTape:
0.3*MSE(path[0:384]) + 0.3*MSE(left[385:769]) + 0.3*MSE(right[771:1155])
+ 0.1*MSE(all 2383 values). Traffic is [1,0], desire zero. State is the previous
teacher output's final 512 values, or zero at sequence start. Targets are held
fixed under all interventions. There is no optimizer or parameter update.

18 samples cover USA training --37, USA validation --32 and Taiwan dataC --61;
each has six deterministic pairs. USA starts are 0/1/299/599/898/1195; Taiwan
0/1/300/600/900/1197. Tail positions respect actual batch-2 generator trimming.
Taiwan targets are a P2.9 extension from the frozen local teacher, rolled from
frame zero using identical YUV and traffic conventions, not historical training
targets or independent human ground truth. Three sequence-start samples have
zero original state and are excluded from paired state-removal aggregates.

Each checkpoint/sample has original, zero-state, mismatched-state and zero-image
conditions (144 trials). Mismatched state is a fixed rotation of real same-sequence
states, including one valid sequence-start zero state. Detailed shape, count,
mean-absolute, RMS, L2, max, zero and below-1e-12 statistics live in records.json.
Parameters are grouped into encoder, kernel/bias, state projections, fusion and
heads. RMS comparisons avoid tensor-size confounding. Per-sample derivatives are
twice that sample's contribution to a batch-of-two mean; batch parity is checked.

## Numbers

'''+ '\n'.join(table)+'''

Table losses are medians of 18 losses, not reported training/validation epoch
metrics. The amplification is a median of 15 paired ratios; it is not the ratio
of the two table medians. Consult CSVs for domain spread and paired loss effects.

## Interpretation and limits

Zero images leave loss effectively unchanged. Removing state increases final-USA
image gradients, but they remain extremely small; best's total image gradients
remain unchanged. Component probes show path/lane image gradients can respond
to removal while the total is dominated by the all-output MSE contribution.
The sum of four component gradients matches gradients of the original loss.
Downstream gradient exists, but early encoder gradients are many orders smaller.
Parameter gradients, especially late biases, are not interchangeable with image
input gradients and do not by themselves prove scene learning.

Teacher forcing is confirmed by dataflow. The state contains previous teacher
latent output, not the current target or a future target. Strong temporal
correlation is expected; confirmed target leakage is not supported. Historical
optimizer moments and initial weights are unavailable, so current local gradients
cannot reconstruct the full optimization trajectory. Raw gradient ratios also
depend on input units; scale-adjusted input ratios are stored separately.

## Artifacts and next experiment

summary.json contains distributions by checkpoint/domain/condition; records.json
contains all tensor and parameter statistics; per_sample_gradients.csv,
counterfactual_gradients.csv, checkpoint_comparison.csv and layer_gradient_profile.csv
are tabular views. component_gradients.json contains the 12 component probes.
samples.json identifies source, pairing, causal state/target alignment and hashes;
samples.npz caches only this audit's selected arrays. run_metadata.json captures
loss/checkpoint identities and runtime checks. gradient_depth.png is derived from
saved records. No old checkpoint or experiment output is overwritten.

Recommended P2.10: run this same actual supervised-loss gradient audit on three
fresh default-initialized architecture controls, with the same cached samples and
state conditions, without updates. This separates pre-training attenuation from
suppression acquired during training. P2.10 is not executed here.
'''
    (ROOT/'README.md').write_text(text)
    write_json(ROOT/'interpretation.json',{'status':'complete','classification':'P2.9-B','best_supported_hypothesis':'H1',
        'shared_shortcut_claim':'not established; final-USA conditional evidence',
        'validated_records':len(records),'component_records':len(component['records']),
        'artifact_sha256':{p.name:sha256(p) for p in ROOT.iterdir() if p.is_file()}})
    print(json.dumps({'status':'PASS','records':len(records),'report':str(ROOT/'README.md')}))


if __name__=='__main__': main()
