"""Read-only, provenance-checked readers for existing ModelB6 experiments."""
import hashlib
import json
import math
from functools import wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'artifacts' / 'do-new-v2'
CANONICAL = {
    'training': 'step5/runs/p25-baseline-20261005/run.json',
    'verification': 'step6/report.json',
    'usa': 'step6/usa/comparison.json',
    'taiwan': 'step6/taiwan/comparison.json',
    'sensitivity': 'p27-sensitivity/results.json',
    'encoder': 'p28-encoder-audit/results.json',
    'encoder_controls': 'p28-encoder-audit/reference_controls.json',
    'gradient': 'p29-gradient-audit/summary.json',
    'interpretation': 'p29-gradient-audit/interpretation.json',
    'fresh_gradient': 'p210-gradient-controls/summary.json',
}
LIMITATION = ('Diagnostic consistency is not driving-quality generalization. '
              'No quantitative ground truth, closed-loop safety or driving quality is established.')


def approved_path(relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError('only approved relative artifact paths are permitted')
    root = ROOT.absolute()
    if root.resolve() != root:
        raise ValueError('evidence root must not be a symlink')
    result = root / p
    if not result.resolve().is_relative_to(root) or result.resolve() != result:
        raise ValueError('symlink/path escape rejected')
    return result


def load_json(relative):
    p = approved_path(relative)
    if p.stat().st_size > 5_000_000:
        raise ValueError('artifact exceeds JSON size bound')
    def reject(value):
        raise ValueError('nonfinite JSON value')
    try:
        value = json.loads(p.read_text(), parse_constant=reject)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed evidence JSON') from exc
    if not isinstance(value, dict):
        raise ValueError('artifact must be an object')
    def check_numbers(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('nonfinite JSON measurement')
        if isinstance(item, dict):
            for child in item.values(): check_numbers(child)
        elif isinstance(item, list):
            for child in item: check_numbers(child)
    check_numbers(value)
    return value


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('missing/nonfinite numeric measurement')
    return value


def validate_schema(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (KeyError, TypeError, IndexError, ZeroDivisionError) as exc:
            raise ValueError('malformed evidence schema for ' + function.__name__) from exc
    return checked


def read_artifact(name):
    relative = CANONICAL[name]
    manifest = load_json('export_manifest.json')
    expected = manifest.get('files', {}).get(relative)
    if not isinstance(expected, dict) or expected.get('source') != '/output/' + relative:
        raise ValueError('missing canonical artifact provenance')
    p = approved_path(relative)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != expected.get('sha256'):
        raise ValueError('export checksum mismatch')
    data = load_json(relative)
    if name not in ('verification', 'usa', 'taiwan') and data.get('status') != 'complete':
        raise ValueError('experiment is not complete')
    return data, {'path': '/output/' + relative, 'sha256': digest}


def evidence(name, facts, source, interpretation, classification='SUPPORTED'):
    return {'category': name, 'classification': classification, 'source': source,
            'facts': facts, 'interpretation': interpretation, 'limitations': LIMITATION}


@validate_schema
def get_training_evidence():
    d, s = read_artifact('training')
    train = [finite(v) for v in d['loss_history']]
    val = [finite(v) for v in d['val_loss_history']]
    if not train or len(train) != len(val) or len(val) != d['epochs_completed']:
        raise ValueError('inconsistent epoch histories')
    best = finite(d['best_val_loss'])
    if best != min(val) or val[d['best_epoch'] - 1] != best:
        raise ValueError('inconsistent best epoch')
    return evidence('training', {'epochs': len(val), 'final_train_loss': train[-1],
        'final_val_loss': val[-1], 'best_val_loss': best, 'best_epoch': d['best_epoch'],
        'train_loss_history': train, 'val_loss_history': val,
        'train_sequences': d['train_sequences'], 'validation_sequences': d['validation_sequences'],
        'resume_semantics': d['resume_semantics']}, s,
        'Late validation deterioration supports instability/possible overfitting; '
        'sampling and one validation sequence prevent a definitive overfitting diagnosis.',
        'PARTIALLY SUPPORTED')


@validate_schema
def get_verification_evidence():
    d, s = read_artifact('verification')
    if d.get('matrix_complete') is not True or d.get('ground_truth_accuracy') is not None:
        raise ValueError('unexpected verification schema')
    return evidence('verification', {k: d[k] for k in ('cells', 'comparisons',
        'cross_domain_raw_response', 'behavioral_quality', 'limitations')}, s,
        'Four-cell technical verification completed; stability does not establish accuracy.')


@validate_schema
def get_sensitivity_evidence():
    d, s = read_artifact('sensitivity')
    facts = {}
    for role in ('final', 'best'):
        facts[role] = {}
        for domain in ('usa', 'taiwan'):
            records = d['roles'][role]['domains'][domain]['records']
            if not records:
                raise ValueError('missing domain sensitivity records')
            grouped = {}
            for r in records:
                group = grouped.setdefault(r['intervention'], [])
                m = r['metrics']['full']
                group.append({k: finite(m[k]) for k in ('mae', 'max_abs', 'rms')})
            facts[role][domain] = {key: {'count': len(v),
                'max_mae': max(x['mae'] for x in v),
                'max_absolute_difference': max(x['max_abs'] for x in v)} for key, v in grouped.items()}
    return evidence('sensitivity', facts, s,
        'Controlled image swaps show near image-invariance in tested pairs; '
        'state interventions affect outputs. This does not quantify driving accuracy.')


@validate_schema
def get_encoder_evidence():
    d, s = read_artifact('encoder')
    c, cs = read_artifact('encoder_controls')
    traces = {}
    for role in ('final', 'best', 'fresh_reference'):
        traces[role] = [{
            'layer': row['layer'],
            'baseline_rms': finite(row['baseline']['rms']),
            'comparison_rms': {key: finite(value['rms'])
                               for key, value in row['comparisons'].items()}}
            for row in d['models'][role]['encoder_trace']]
        if not traces[role]:
            raise ValueError('missing encoder trace')
    return evidence('encoder', {'traces': traces, 'input_scale': d['input_scale'],
        'fresh_controls': c['records'], 'reference_caveat': d['reference_caveat']},
        [s, cs], 'Progressive attenuation appears in trained and fresh controls; '
        'native preprocessing agreement does not isolate initializer causality.')


@validate_schema
def get_gradient_evidence():
    d, s = read_artifact('gradient')
    interpretation, si = read_artifact('interpretation')
    facts = {}
    for role in ('final', 'best'):
        facts[role] = {}
        for domain in ('overall', 'usa', 'taiwan'):
            facts[role][domain] = {condition: {metric: finite(values['median'])
                for metric, values in metrics.items()} for condition, metrics
                in d['aggregates'][role][domain].items()}
    return evidence('gradient', {'aggregates': facts, 'records': d['records'],
        'samples': d['samples'], 'shortcut_claim': interpretation['shared_shortcut_claim']},
        [s, si], 'Strong local image-gradient attenuation; conditional state effects. '
        'Tiny nonzero gradients are not numerical zero and do not prove universal shortcut learning.')


@validate_schema
def get_fresh_gradient_evidence():
    d, s = read_artifact('fresh_gradient')
    depths = {}
    if len(d['seeds']) != 3 or d['training_steps'] != 0 or d['optimizer_created'] is not False:
        raise ValueError('fresh-control schema mismatch')
    for seed in d['seeds']:
        a = d['aggregates'][str(seed)]
        stem, late = finite(a['stem_rms']), finite(a['late_rms'])
        if min(stem, late) <= 0:
            raise ValueError('gradient ratio must be positive')
        depths[str(seed)] = math.log10(late / stem)
    return evidence('fresh_gradient', {'seeds': d['seeds'], 'records': d['records'],
        'top_to_stem_orders': depths, 'aggregates': d['aggregates'], 'caveat': d['caveat']}, s,
        'Severe attenuation exists before training in this architecture/default-initialization '
        'combination; the initializer alone is not proven as the cause.')


@validate_schema
def compare_domains():
    sensitivity = get_sensitivity_evidence()
    gradients = get_gradient_evidence()
    comparisons = {}
    sources = []
    for domain in ('usa', 'taiwan'):
        d, s = read_artifact(domain)
        if d.get('domain') != domain or set(d['metrics']) != {'final', 'best'}:
            raise ValueError('domain mismatch')
        comparisons[domain] = d['metrics']; sources.append(s)
    return evidence('domain_comparison', {'step6': comparisons,
        'sensitivity': sensitivity['facts'], 'gradients': gradients['facts']['aggregates']},
        sources + [sensitivity['source'], gradients['source']],
        'Cross-domain diagnostic consistency is distinct from driving-quality generalization. '
        'USA is train-seen; Taiwan uses a different projection and teacher targets are not human ground truth.')


CLAIMS = {
    'image_invariance': ('SUPPORTED', ['sensitivity'], 'Near image-invariance on tested controlled pairs only.'),
    'state_dependence': ('SUPPORTED', ['sensitivity', 'gradient'], 'Material output/state sensitivity; magnitude and effects depend on checkpoint/domain.'),
    'training_caused_collapse': ('UNSUPPORTED', ['fresh_gradient'], 'Fresh zero-training controls already show severe attenuation.'),
    'initializer_sole_cause': ('UNSUPPORTED', ['fresh_gradient', 'encoder'], 'Architecture and default initialization were not independently isolated.'),
    'driving_quality': ('UNKNOWN / NOT EVALUATED', ['verification'], 'No independent ground-truth driving-quality evaluation.'),
    'overfitting': ('PARTIALLY SUPPORTED', ['training'], 'Validation deterioration is compatible with overfitting/instability, not a definitive cause.'),
    'universal_shortcut': ('UNSUPPORTED', ['interpretation'], 'Conditional final-USA evidence does not establish a universal shortcut.'),
}


def check_diagnostic_claim(claim_id):
    if claim_id not in CLAIMS:
        return {'claim': claim_id, 'classification': 'UNKNOWN / NOT EVALUATED',
                'reason': 'Claim is outside the audited claim catalogue.', 'sources': [], 'limitations': LIMITATION}
    status, names, reason = CLAIMS[claim_id]
    sources = []
    validators = {'training': get_training_evidence, 'verification': get_verification_evidence,
                  'sensitivity': get_sensitivity_evidence, 'encoder': get_encoder_evidence,
                  'gradient': get_gradient_evidence, 'fresh_gradient': get_fresh_gradient_evidence}
    for name in names:
        try:
            if name in validators: validators[name]()
            _, source = read_artifact(name); sources.append(source)
        except FileNotFoundError:
            return {'claim': claim_id, 'classification': 'UNKNOWN / NOT EVALUATED',
                    'reason': 'Required evidence unavailable.', 'sources': [], 'limitations': LIMITATION}
    return {'claim': claim_id, 'classification': status, 'reason': reason,
            'sources': sources, 'limitations': LIMITATION}


def diagnostic_report():
    sections = {}
    for tool in (get_training_evidence, get_verification_evidence, get_sensitivity_evidence,
                 get_encoder_evidence, get_gradient_evidence, get_fresh_gradient_evidence, compare_domains):
        try:
            sections[tool.__name__] = tool()
        except FileNotFoundError:
            sections[tool.__name__] = {'classification': 'UNKNOWN / NOT EVALUATED', 'reason': 'Evidence unavailable.'}
    return {'title': 'Model B6 Diagnostic Report', 'sections': sections,
            'claims': {name: check_diagnostic_claim(name) for name in CLAIMS},
            'most_supported_diagnosis': sections['get_fresh_gradient_evidence'],
            'alternative_explanations': 'Architecture/default-initialization combination; neither initializer alone nor training-only causation established.',
            'unsupported_claims': ['initializer_sole_cause', 'training_caused_collapse', 'universal_shortcut'],
            'driving_quality_limitations': LIMITATION,
            'next_action': 'Review existing technical/qualitative evidence; no new ModelB6 training or P2.11.'}
