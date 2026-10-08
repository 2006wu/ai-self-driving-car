"""Do New v2 numerical diagnosis; offline report never calls Gemini."""
import argparse
import json
import os
from agno.agent import Agent
from agno.models.google import Gemini
from agno.run.agent import RunStatus
from model_config import runtime_model_id
from v2_evidence import (get_training_evidence, get_verification_evidence,
    get_sensitivity_evidence, get_encoder_evidence, get_gradient_evidence,
    get_fresh_gradient_evidence, compare_domains, check_diagnostic_claim, diagnostic_report)

TOOLS = [get_training_evidence, get_verification_evidence, get_sensitivity_evidence,
         get_encoder_evidence, get_gradient_evidence, get_fresh_gradient_evidence,
         compare_domains, check_diagnostic_claim]
INSTRUCTIONS = [
    'Use the registered read-only evidence tools. Identify artifact paths and experiment for every major finding.',
    'Classify findings SUPPORTED, PARTIALLY SUPPORTED, UNSUPPORTED or UNKNOWN / NOT EVALUATED.',
    'Do not invent measurements or infer causality from correlation or local gradients.',
    'Tiny nonzero gradients are not numerical zero or machine-precision underflow.',
    'Fresh attenuation predates training; the initializer alone is not established as sole cause.',
    'State-removal effects vary by domain/checkpoint. Universal shortcut learning is not established.',
    'Overfitting is possible, not proven solely by validation deterioration or domain differences.',
    'Separate diagnostic consistency from driving-quality generalization; ground truth and safety are unverified.',
    'No training, checkpoint/source changes, P2.11, or new experiments. Clearly label unavailable evidence.',
]


def build_agent():
    return Agent(model=Gemini(id=runtime_model_id()), tools=TOOLS, instructions=INSTRUCTIONS, markdown=True)


def run_live(question):
    if not os.environ.get('GOOGLE_API_KEY'):
        raise SystemExit('Live validation skipped: GOOGLE_API_KEY not inherited.')
    agent = build_agent()
    print('Student runtime model:', agent.model.id)
    result = agent.run(question)
    if result.status != RunStatus.completed:
        raise RuntimeError('live Diagnosis Agent did not complete; no successful diagnosis report')
    if not isinstance(result.content, str) or not result.content.strip():
        raise RuntimeError('live Diagnosis Agent returned no textual report')
    return {'mode': 'diagnosis', 'model': agent.model.id, 'gemini_executed': True,
            'report': result.content,
            'tools': [{'name': tool.tool_name, 'error': bool(tool.tool_call_error)}
                      for tool in (getattr(result, 'tools', None) or [])],
            'acceptance': 'Requires review of actual evidence-tool use, cited facts and interpretation boundaries.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--question',default='Generate the complete Model B6 Diagnostic Report, with all evidence categories, supported diagnosis, alternatives, unsupported claims, limitations and next action.')
    args=parser.parse_args()
    if args.offline:
        print(json.dumps({'mode':'offline_report','gemini_executed':False,'report':diagnostic_report()},indent=2,allow_nan=False))
    else:
        try:
            print(json.dumps(run_live(args.question), indent=2, allow_nan=False))
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None


if __name__ == '__main__': main()
