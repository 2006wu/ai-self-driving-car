"""Do New v2 numerical diagnosis; offline report never calls Gemini."""
import argparse
import json
import os
from agno.agent import Agent
from agno.run.agent import RunStatus
from model_config import runtime_model_id
from live_runtime import (configured_model, ProviderRunError, notify, tool_audit,
    verify_tool_mode, add_options, execute_job, print_result, redact,
    collect_verification_tools, verification_context)
from report_contract import (diagnosis_reference, with_context, METRIC_RULES,
    validate_diagnosis_tables, verified_domain_table)
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
    'Use the authenticated local reference table to check every reported number. Preserve condition/metric labels, units, reduction, checkpoint and domain. A readable paraphrase must not rename the measured quantity.',
    'Use the reference claim_catalogue classifications exactly. Overfitting stays PARTIALLY SUPPORTED; activation saturation, overparameterization, generalized network collapse and deployment readiness are not established. Name training instability as an alternative rather than choosing a sole cause.',
    'The application renders the exact Step6 table separately. Do not copy a second numerical table or the entire input context. Keep the narrative concise, retain source/metric/condition identity, and obey allowed_next_action.',
    'Separate verified facts, model interpretations and unknowns. Keep the narrative under about 600 words, cite source paths without repeating SHA-256 strings, and avoid reprinting the full input context.',
] + list(METRIC_RULES.values())


def build_agent():
    return Agent(model=configured_model(), tools=TOOLS, instructions=INSTRUCTIONS, markdown=True, retries=0, tool_call_limit=12)


def run_live(question, progress=None, tool_mode='preload'):
    if not os.environ.get('GOOGLE_API_KEY'):
        raise SystemExit('Live validation skipped: GOOGLE_API_KEY not inherited.')
    notify(progress,'validating_local_evidence')
    reference = diagnosis_reference()
    notify(progress,'evidence_ready',reference=reference)
    agent = build_agent()
    executions=[]
    if tool_mode=='verify':
        executions=collect_verification_tools([get_training_evidence,get_gradient_evidence,
            get_encoder_evidence,check_diagnostic_claim],progress)
        reference['required_tool_checks']=verification_context(executions)
        agent.tools=[]
        question+=' Interpret the recorded required_tool_checks results and explain their limits.'
    notify(progress,'waiting_for_gemini')
    result = agent.run(with_context(question, reference))
    result.tools=executions+list(getattr(result,'tools',None) or [])
    notify(progress,'draft_ready',model_output=getattr(result,'content',None),tools=tool_audit(result))
    if result.status != RunStatus.completed:
        raise ProviderRunError('live Diagnosis Agent did not complete; no successful diagnosis report',result.content)
    if not isinstance(result.content, str) or not result.content.strip():
        raise RuntimeError('live Diagnosis Agent returned no textual report')
    notify(progress,'checking_report')
    validation=validate_diagnosis_tables(result.content,reference)
    tool_check=verify_tool_mode(result,tool_mode,['get_training_evidence','get_gradient_evidence','get_encoder_evidence','check_diagnostic_claim'])
    if tool_mode=='verify': tool_check['selection']='APPLICATION_REQUIRED_MODEL_CALLS'
    return {'mode': 'diagnosis', 'model': agent.model.id, 'gemini_executed': True,
            'report': result.content,
            'content_validation':validation,
            'verified_evidence_table':verified_domain_table(reference),
            'verified_reference': reference,
            'tool_verification':tool_check,'tool_audit':tool_audit(result),
            'review_sections':{'facts':'verified_reference / verified_evidence_table',
                'model_interpretation':'report','not_established':reference['interpretation_limits'],
                'status':'HUMAN_CONTENT_REVIEW_REQUIRED'},
            'tools': [{'name': tool.tool_name, 'error': bool(tool.tool_call_error)}
                      for tool in (getattr(result, 'tools', None) or [])],
            'acceptance': 'Requires review of actual evidence-tool use, cited facts and interpretation boundaries.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--question',default='Generate a concise Model B6 Diagnostic Report with all evidence categories, source citations, claim_catalogue classifications, alternative explanations, limitations and the allowed next action. The application supplies a verified numerical table separately; do not transcribe the context or create a duplicate table. Distinguish original from mismatched_state, activation magnitude from image-difference RMS, predicted coordinates from ground-truth error, and nonpositive lane width from path sign. Do not infer overfitting causation or encoder saturation, and do not recommend deployment or new training.')
    add_options(parser)
    args=parser.parse_args(argv)
    if args.offline:
        print(json.dumps({'mode':'offline_report','gemini_executed':False,'report':diagnostic_report()},indent=2,allow_nan=False))
    else:
        try:
            value,directory=execute_job('diagnosis',{'question':args.question},args)
            print_result(value,directory,args)
        except KeyboardInterrupt:
            raise SystemExit(130) from None
        except (RuntimeError,ValueError,OSError,TimeoutError) as exc:
            raise SystemExit(redact(exc)) from None


if __name__ == '__main__': main()
