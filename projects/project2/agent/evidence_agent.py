"""Original Project 2 feature: a read-only evidence-reporting Agent tool."""
import json
import math
import argparse
import os
from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.reasoning import ReasoningTools
from model_config import runtime_model_id


ARTIFACTS = Path(__file__).resolve().parent / 'artifacts'
DEFAULT_ROOT = ARTIFACTS / 'p29-gradient-audit'
ALLOWED_ROOTS = (DEFAULT_ROOT, Path('/output/p29-gradient-audit'))


def _safe_root(root):
    path = Path(root).resolve()
    if path not in ALLOWED_ROOTS:
        raise ValueError('evidence root must be the configured P2.9 evidence directory')
    return path


def summarize_p2_evidence(root=None):
    """Read saved P2 evidence and return compact quantitative facts.

    This tool never writes files, loads models, runs inference, or changes
    checkpoints. It is intentionally useful in a no-GPU/no-training Agent demo.
    """
    base = _safe_root(root if root is not None else DEFAULT_ROOT)
    summary_path = (base / 'summary.json').resolve()
    if summary_path.parent != base:
        raise ValueError('summary symlink escapes evidence directory')
    if not summary_path.is_file():
        raise FileNotFoundError(summary_path)
    try:
        summary = json.loads(summary_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError('malformed evidence JSON') from exc
    if not isinstance(summary, dict) or summary.get('status') != 'complete':
        raise ValueError('evidence must be a completed P2.9 summary')
    for name in ('records', 'samples'):
        if type(summary.get(name)) is not int or summary[name] <= 0:
            raise ValueError('missing/invalid evidence count: ' + name)
    result = {'source': str(summary_path), 'status': summary.get('status'),
              'records': summary.get('records'), 'samples': summary.get('samples'),
              'checkpoints': {}}
    for role in ('final', 'best'):
        try:
            original = summary['aggregates'][role]['overall']['original']
            metrics = {out: original[key]['median'] for out, key in (
                ('loss_median', 'loss'), ('image_gradient_rms_median', 'image_rms'),
                ('state_gradient_rms_median', 'state_rms'),
                ('image_state_ratio_median', 'image_state_ratio'))}
        except (KeyError, TypeError) as exc:
            raise ValueError('incomplete checkpoint metrics: ' + role) from exc
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in metrics.values()):
            raise ValueError('nonfinite/invalid checkpoint metrics: ' + role)
        result['checkpoints'][role] = metrics
    return result


def build_agent():
    return Agent(
        model=Gemini(id=runtime_model_id()),
        tools=[ReasoningTools(add_instructions=True), summarize_p2_evidence],
        instructions=[
            'Answer only from the local Project 2 evidence tool.',
            'State when a requested artifact is unavailable.',
            'Never suggest changing checkpoints or source data.',
            'Use a compact table for numeric comparisons.',
        ],
        markdown=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='run only the deterministic evidence tool')
    args = parser.parse_args()
    evidence = summarize_p2_evidence()
    if args.offline:
        print(json.dumps({'mode': 'offline_tool_only', 'gemini_executed': False,
                          'evidence': evidence}, indent=2, allow_nan=False))
        return
    if not os.environ.get('GOOGLE_API_KEY'):
        raise SystemExit('GOOGLE_API_KEY must be supplied at runtime')
    agent = build_agent()
    print('Student runtime model:', agent.model.id)
    agent.print_response(
        'Use summarize_p2_evidence() with its default directory to compare final and best gradients. '
        'Distinguish technical completion from driving quality; report no new experiment results.',
        stream=True,
    )


if __name__ == '__main__':
    main()
