"""Original Project 2 feature: a read-only evidence-reporting Agent tool."""
import json
import os
from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.reasoning import ReasoningTools


ALLOWED_ROOTS = (Path('/output'), Path('/tmp'), Path('/private/tmp'))


def _safe_root(root):
    path = Path(root).resolve()
    if not any(path == base or base in path.parents for base in ALLOWED_ROOTS):
        raise ValueError('evidence root must be under /output or /tmp')
    return path


def summarize_p2_evidence(root='/output/p29-gradient-audit'):
    """Read saved P2 evidence and return compact quantitative facts.

    This tool never writes files, loads models, runs inference, or changes
    checkpoints. It is intentionally useful in a no-GPU/no-training Agent demo.
    """
    base = _safe_root(root)
    summary_path = base / 'summary.json'
    if not summary_path.is_file():
        raise FileNotFoundError(summary_path)
    summary = json.loads(summary_path.read_text())
    result = {'source': str(summary_path), 'status': summary.get('status'),
              'records': summary.get('records'), 'samples': summary.get('samples'),
              'checkpoints': {}}
    for role, aggregate in summary.get('aggregates', {}).items():
        original = aggregate.get('overall', {}).get('original', {})
        result['checkpoints'][role] = {
            'loss_median': original.get('loss', {}).get('median'),
            'image_gradient_rms_median': original.get('image_rms', {}).get('median'),
            'state_gradient_rms_median': original.get('state_rms', {}).get('median'),
            'image_state_ratio_median': original.get('image_state_ratio', {}).get('median'),
        }
    return result


def build_agent():
    if not os.environ.get('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY must be supplied at runtime')
    return Agent(
        model=Gemini(id='gemini-2.5-flash'),
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
    agent = build_agent()
    agent.print_response(
        'Summarize the final and best supervised-gradient evidence from /output/p29-gradient-audit.',
        stream=True,
    )


if __name__ == '__main__':
    main()
