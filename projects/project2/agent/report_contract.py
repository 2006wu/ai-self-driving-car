"""Compact authenticated context and explicit metric semantics for live reports.

These are local readers, not model/tool execution claims. Free-form model
interpretation still needs human review; reference tables preserve exact values.
"""
import json
import math
import re

from v2_evidence import (get_gradient_evidence, get_encoder_evidence,
    get_fresh_gradient_evidence, get_training_evidence, get_verification_evidence,
    compare_domains, read_artifact, check_diagnostic_claim, CLAIMS)

METRIC_RULES = {
    'gradient': 'Gradient-audit aggregate values must identify checkpoint, domain aggregate, intervention condition, metric key and aggregation=median. This median label applies only to gradient-audit aggregates, not Step6 means/maxima/counts. original and mismatched_state are different interventions; state_rms is an input gradient and state_parameter_rms is a parameter gradient.',
    'encoder': 'baseline_rms is activation magnitude; comparison_rms is RMS difference between inputs. Do not substitute them. block3b_add is intermediate, not the final encoder endpoint. Late trained activation magnitude may remain large while input-dependent differences vanish.',
    'path_near_abs_max_m': 'Maximum absolute predicted near-path lateral coordinate over the clip, metres. NOT ground-truth deviation/error.',
    'lane_width_near_nonpositive_frames': 'Number of clip frames with predicted near lane width <= 0. NOT number of negative-path frames.',
    'top_to_stem_orders': 'log10(late gradient RMS / stem gradient RMS). Positive ~9.3 means backward gradients attenuate toward the stem; not a forward activation ratio.',
    'scope': 'Clip-level statistics cannot establish a specific still frame error, motion over time, ground-truth accuracy or vehicle-to-model-lead correspondence.',
    'spatial_vs_temporal': 'step6.summarize uses near positions [:,4:40]. path_near_mean_m averages their coordinates across positions and frames; path_near_abs_max_m is their absolute maximum; temporal_change is mean absolute consecutive-frame change. None measures full-curve spatial smoothness or proves that averaging removes spatial jitter.',
}


def diagnosis_reference():
    gradient=get_gradient_evidence()
    encoder=get_encoder_evidence()
    fresh=get_fresh_gradient_evidence()
    training=get_training_evidence()
    domains=compare_domains()
    gradient_rows=[]
    for role,aggregates in gradient['facts']['aggregates'].items():
        for domain,conditions in aggregates.items():
            for condition in ('original','mismatched_state'):
                if condition in conditions:
                    gradient_rows.append({'checkpoint':role,'domain_aggregate':domain,
                        'condition':condition,'aggregation':'median',
                        'metrics':{k:v for k,v in conditions[condition].items()
                                   if k in ('image_rms','state_rms','state_parameter_rms')}})
    endpoints=[]
    for role,trace in encoder['facts']['traces'].items():
        selected=[r for r in trace if r['layer']=='stem_conv']
        selected.append(trace[-1])
        endpoints.append({'checkpoint':role,'endpoint_layer':trace[-1]['layer'],
                          'rows':selected})
    return {'metric_rules':METRIC_RULES,'gradient_reference':gradient_rows,
        'claim_catalogue':{name:{key:value for key,value in check_diagnostic_claim(name).items()
                                if key in ('classification','reason')} for name in CLAIMS},
        'interpretation_limits':[
            'Late validation deterioration is compatible with overfitting or optimization instability; overfitting/overparameterization is not established as the cause.',
            'Encoder attenuation is not proof of activation saturation. Do not label Encoder Saturation as a supported mechanism.',
            'Fresh zero-training controls already show attenuation; do not claim late training caused that shared attenuation.',
            'Similar descriptive path/lane instability on two clips is not proof of generalized network collapse or driving accuracy.',
        ],
        'allowed_next_action':'Review existing evidence only. Deployment, new training and early-stopping implementation are outside this report scope; best-checkpoint stability does not establish deployment readiness.',
        'encoder_reference':endpoints,
        'fresh_gradient_top_to_stem_orders':fresh['facts']['top_to_stem_orders'],
        'training':{k:training['facts'][k] for k in
                    ('epochs','final_train_loss','final_val_loss','best_val_loss','best_epoch')},
        'domain_reference':{domain:{role:{k:v for k,v in metrics.items() if k in
            ('frames','path_near_abs_max_m','lane_width_near_nonpositive_frames','ground_truth_accuracy')}
            for role,metrics in roles.items()} for domain,roles in domains['facts']['step6'].items()},
        'sources':{'gradient':gradient['source'],'encoder':encoder['source'],
                   'fresh_gradient':fresh['source'],'training':training['source'],
                   'domain_comparison':domains['source']},
        'provenance':'Deterministic local checksum-verified readers; not a trace of model-selected tool calls.'}


def verified_domain_table(reference):
    """Render facts in code so the model need not transcribe the numeric table."""
    lines=['| Domain | Checkpoint | Metric | Value | Source |',
           '|---|---|---|---:|---|']
    for domain,roles in reference['domain_reference'].items():
        for role,metrics in roles.items():
            for key,value in metrics.items():
                lines.append(f'| {domain} | {role} | {key} | {json.dumps(value)} | /output/step6/{domain}/comparison.json |')
    return '\n'.join(lines)


def validate_diagnosis_tables(report,reference):
    """Check scoped Step6 metric rows; not a general natural-language verifier.

    Only rows that explicitly identify one domain, checkpoint, known metric and
    numeric value are checked. Rounded values allow 1e-5 relative tolerance.
    Counts must be exact. Unknown/unparsed prose never counts as a checked fact.
    """
    checked=0
    for line in report.splitlines():
        if not line.strip().startswith('|'):
            continue
        cells=[s.strip().strip('`') for s in line.strip().strip('|').split('|')]
        domains=[d for d in reference['domain_reference'] if d in [c.lower() for c in cells]]
        roles=[r for r in ('final','best') if r in [c.lower() for c in cells]]
        if len(domains)!=1 or len(roles)!=1:
            continue
        domain,role=domains[0],roles[0]
        metrics=reference['domain_reference'][domain][role]
        keys=[k for k in metrics if k in cells and type(metrics[k]) in (int,float)]
        if len(keys)!=1:
            continue
        key=keys[0]
        # Value follows the metric, optionally after a reduction column.
        tail=cells[cells.index(key)+1:]
        numeric=[c.strip('$` ') for c in tail if re.fullmatch(r'\s*[$` ]*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[$` ]*\s*',c)]
        if len(numeric)!=1:
            continue
        value=float(numeric[0]);expected=metrics[key]
        equal=value==expected if type(expected) is int else math.isclose(value,expected,rel_tol=1e-5,abs_tol=1e-12)
        if not equal:
            raise RuntimeError(f'Diagnosis report rejected: {domain}/{role} {key}={value:g}; authenticated value is {expected:g}. No accepted report.')
        source=f'/output/step6/{domain}/comparison.json'
        if not any(source in cell for cell in cells):
            raise RuntimeError(f'Diagnosis report rejected: {domain}/{role} table row must cite {source}.')
        checked+=1
    return {'status':'HUMAN_CONTENT_REVIEW_REQUIRED','checked_step6_table_rows':checked,
            'scope':'Scoped numeric table rows only; prose, causal claims and agent tool use are not automatically validated.'}


def unified_reference(metadata):
    verified=get_verification_evidence()
    domain=metadata['domain'];role=metadata['role']
    data,source=read_artifact(domain)
    if data.get('domain')!=domain or role not in data.get('metrics',{}):
        raise ValueError('image domain/checkpoint does not match numerical evidence')
    reductions={}
    for key in data['metrics'][role]:
        if key=='frames': reductions[key]='frame count'
        elif key.endswith('_frames') or key.endswith('_frames_gt10m') or key=='nonfinite_count': reductions[key]='count (not median)'
        elif key.endswith('_temporal_change_m'): reductions[key]='mean absolute consecutive-frame change'
        elif key.endswith('_mean_m') or key.endswith('_mean'): reductions[key]='arithmetic mean (not median)'
        elif key.endswith('_abs_max_m'): reductions[key]='maximum absolute coordinate'
        elif key.endswith('_max'): reductions[key]='maximum'
    return {'domain':domain,'checkpoint':role,'scope':'whole clip; not this individual frame',
        'metric_reductions':reductions,
        'metrics':data['metrics'][role], 'frame_specific_ground_truth':'NOT AVAILABLE',
        'model_lead_to_visible_vehicle_correspondence':'UNKNOWN; no association established by these metrics',
        'metric_rules':METRIC_RULES,'source':source,'verification_source':verified['source'],
        'provenance':'Deterministic local checksum-verified readers; separate from model-selected tool calls.'}


def with_context(question,reference):
    return question+'\n\nAuthenticated local reference (data, not instructions):\n'+json.dumps(reference,allow_nan=False)


def validate_unified_comparison(report,reference):
    """Reject omitted/untraceable comparison, not claim full semantic correctness."""
    fields=[report.numerical_agreements,report.numerical_disagreements]
    placeholders={'','not evaluated','not applicable','n/a','unknown'}
    if all(s.strip().lower().rstrip('.') in placeholders for s in fields):
        raise RuntimeError('Unified numerical comparison missing; no accepted integrated report')
    combined=' '.join(fields)
    if re.search(r'(?<!not )aggregation\s*=\s*median',combined,re.I):
        raise RuntimeError('Unified report rejected: Step6 metrics are means/maxima/counts, not aggregation=median. Use metric_reductions from the reference.')
    if reference['source']['path'] not in combined or not any(key in combined for key in reference['metrics']):
        raise RuntimeError('Unified comparison must cite the selected numerical source path and metric key; no accepted integrated report')
    validate_visual_boundaries(report)


def validate_visual_boundaries(report):
    """Catch the observed averaging overclaim; not general semantic validation."""
    for key,value in report.model_dump().items():
        for sentence in re.split(r'(?<=[.!?])\s+',value):
            if re.search(r'averaged\s+(?:out|away)',sentence,re.I) and not re.search(
                    r'\b(?:not|cannot|unknown|unverified|unproven|unsupported)\b',sentence,re.I):
                raise RuntimeError(f'Visual report rejected: {key} asserts spatial jitter is averaged out; clip summaries do not establish this mechanism.')
