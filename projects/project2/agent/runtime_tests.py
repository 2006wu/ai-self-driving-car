"""Offline runtime/record/timeout regressions; subprocess fixtures never use a network."""
import argparse
import hashlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

import live_runtime as runtime
from live_worker import RedactingLog
from report_output import format_report
from report_contract import validate_visual_boundaries, validate_unified_comparison
from vision_agent import VisualVerificationReport
from v2_evidence import ROOT as EVIDENCE_ROOT
from test_file_helpers import requires_file


def options(root,**kwargs):
    values=dict(timeout=10.,attempt_timeout=2.,request_timeout=1.,retries=0,
                progress_every=.05,model='offline-test-model',output_dir=Path(root),tool_mode='preload',json=False)
    values.update(kwargs)
    return SimpleNamespace(**values)


class RuntimeTests(unittest.TestCase):
    def test_required_check_forces_one_model_tool_without_output_schema(self):
        from agno.run.agent import RunStatus
        def get_encoder_evidence(): return 'must not be called directly'
        execution=SimpleNamespace(tool_name='get_encoder_evidence',tool_call_error=False,result='fixture')
        with patch('agno.agent.Agent') as agent:
            agent.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,tools=[execution])
            actual=runtime.collect_verification_tools([get_encoder_evidence])
        self.assertEqual(actual,[execution])
        kwargs=agent.call_args.kwargs
        self.assertEqual(kwargs['tool_choice'],'any');self.assertEqual(kwargs['tool_call_limit'],1)
        self.assertTrue(kwargs['tools'][0].stop_after_tool_call)
        self.assertNotIn('output_schema',kwargs)

    def test_required_check_missing_result_stops_before_next_request(self):
        from agno.run.agent import RunStatus
        def first(): pass
        def second(): pass
        with patch('agno.agent.Agent') as agent:
            agent.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,tools=[])
            with self.assertRaisesRegex(RuntimeError,'missing successful tools'):
                runtime.collect_verification_tools([first,second])
        self.assertEqual(agent.call_count,1)

    def test_required_check_rejects_wrong_claim_argument(self):
        from agno.run.agent import RunStatus
        def check_diagnostic_claim(claim_id): pass
        execution=SimpleNamespace(tool_name='check_diagnostic_claim',tool_call_error=False,
                                  result='fixture',tool_args={'claim_id':'driving_quality'})
        with patch('agno.agent.Agent') as agent:
            agent.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,tools=[execution])
            with self.assertRaisesRegex(RuntimeError,'overfitting claim check'):
                runtime.collect_verification_tools([check_diagnostic_claim])

    def test_required_check_preserves_provider_status(self):
        from agno.run.agent import RunStatus
        def check(): pass
        with patch('agno.agent.Agent') as agent:
            agent.return_value.run.return_value=SimpleNamespace(status=RunStatus.error,tools=[],content={'error':{'code':503}})
            with self.assertRaises(runtime.ProviderRunError) as caught:
                runtime.collect_verification_tools([check])
        self.assertEqual(caught.exception.status_code,503)

    def test_verification_context_contains_actual_result_and_selection_boundary(self):
        context=runtime.verification_context([SimpleNamespace(tool_name='fixture',result={'value':3})])
        self.assertEqual(context['results'][0]['result'],{'value':3})
        self.assertIn('not autonomous',context['protocol'])

    @requires_file(EVIDENCE_ROOT / 'export_manifest.json',
                   'Run projects/project2/agent/prepare_v2.py with the existing Docker output volume available.')
    def test_unified_report_receives_checked_results_without_structured_tool_mix(self):
        import vision_agent
        from v2_tests import integrated_fixture_report
        from agno.run.agent import RunStatus
        executions=[SimpleNamespace(tool_name=name,tool_call_error=False,result='fixture')
                    for name in ('get_verification_evidence','compare_domains')]
        with patch.dict(os.environ,{'GOOGLE_API_KEY':'offline-dummy'}), \
             patch.object(vision_agent,'collect_verification_tools',return_value=executions), \
             patch.object(vision_agent,'build_agent') as builder:
            builder.return_value.model.id='offline-model'
            builder.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,
                content=integrated_fixture_report().model_copy(update={'numerical_agreements':'Synthetic check of /output/step6/taiwan/comparison.json frames; not a live observation.'}),tools=[])
            result=vision_agent.run('step6/taiwan/best/frame_00001.png',True,tool_mode='verify')
        self.assertEqual(len(result['tool_audit']),2)
        self.assertEqual(builder.return_value.tools,[])
        self.assertIn('required_tool_checks',builder.return_value.run.call_args.args[0])
        self.assertEqual(result['tool_verification']['selection'],'APPLICATION_REQUIRED_MODEL_CALLS')

    @requires_file(EVIDENCE_ROOT / 'export_manifest.json',
                   'Run projects/project2/agent/prepare_v2.py with the existing Docker output volume available.')
    def test_diagnosis_report_preserves_all_required_tool_receipts(self):
        import diagnosis_agent
        from agno.run.agent import RunStatus
        executions=[SimpleNamespace(tool_name=name,tool_call_error=False,result='fixture',
                                    tool_args={'claim_id':'overfitting'}) for name in
            ('get_training_evidence','get_gradient_evidence','get_encoder_evidence','check_diagnostic_claim')]
        with patch.dict(os.environ,{'GOOGLE_API_KEY':'offline-dummy'}), \
             patch.object(diagnosis_agent,'collect_verification_tools',return_value=executions), \
             patch.object(diagnosis_agent,'build_agent') as builder:
            builder.return_value.model.id='offline-model'
            builder.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content='Fixture interpretation.',tools=[])
            result=diagnosis_agent.run_live('fixture',tool_mode='verify')
        self.assertEqual(len(result['tool_audit']),4)
        self.assertEqual(builder.return_value.tools,[])
        self.assertIn('required_tool_checks',builder.return_value.run.call_args.args[0])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def worker(self,body):
        path=self.root/'fixture_worker.py'
        path.write_text('import sys,json,time\nfrom pathlib import Path\nd=Path(sys.argv[2])\n'+body)
        return path
    def execute(self,body,**kwargs):
        with patch('sys.stderr',new_callable=io.StringIO):
            return runtime.execute_job('diagnosis',{'question':'synthetic'},options(self.root/'records',**kwargs),
                                       worker=self.worker(body),require_key=False)
    def test_success_persists_configuration_result_report_and_hashes(self):
        result,directory=self.execute("(d/'response.json').write_text(json.dumps({'ok':True,'result':{'mode':'diagnosis','model':'offline-test-model','report':'synthetic','tools':[]}}))")
        self.assertEqual(json.loads((directory/'run.json').read_text())['status'],'COMPLETED')
        self.assertEqual(result['report'],'synthetic')
        self.assertTrue((directory/'report.md').exists())
        manifest=json.loads((directory/'manifest.json').read_text())['files']
        for name,digest in manifest.items(): self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest)
        self.assertNotIn('GOOGLE_API_KEY',(directory/'request.json').read_text())
    def test_attempt_timeout_terminates_child_and_records_failure(self):
        started=time.monotonic()
        with self.assertRaises(TimeoutError): self.execute('time.sleep(20)',attempt_timeout=.15,timeout=1)
        self.assertLess(time.monotonic()-started,2)
        record=json.loads(next((self.root/'records').rglob('run.json')).read_text())
        self.assertEqual(record['status'],'TIMED_OUT')
        self.assertFalse(next((self.root/'records').iterdir()).joinpath('result.json').exists())
    def test_transient_retry_once_then_success(self):
        body="""response={'ok':False,'error':'503 temporary','status_code':503,'retryable':True} if d.name=='attempt-1' else {'ok':True,'result':{'mode':'diagnosis','model':'offline','report':'synthetic','tools':[]}}
(d/'response.json').write_text(json.dumps(response))
"""
        with patch.object(runtime.time,'sleep'):
            _,directory=self.execute(body,retries=1)
        record=json.loads((directory/'run.json').read_text())
        self.assertEqual(len(record['attempts']),2);self.assertEqual(record['status'],'COMPLETED')
    def test_nontransient_failure_never_retried(self):
        body="(d/'response.json').write_text(json.dumps({'ok':False,'error':'invalid source','retryable':False}))"
        with self.assertRaisesRegex(RuntimeError,'invalid source'): self.execute(body,retries=3)
        self.assertEqual(len(list((self.root/'records').rglob('attempt-*'))),1)
    def test_retries_have_finite_limit(self):
        body="(d/'response.json').write_text(json.dumps({'ok':False,'error':'503','retryable':True}))"
        with patch.object(runtime.time,'sleep'),self.assertRaises(RuntimeError): self.execute(body,retries=1)
        self.assertEqual(len(list((self.root/'records').rglob('attempt-*'))),2)
    def test_total_deadline_caps_attempt(self):
        with self.assertRaises(TimeoutError): self.execute('time.sleep(20)',attempt_timeout=10,timeout=.15,retries=3)
        self.assertEqual(len(list((self.root/'records').rglob('attempt-*'))),1)
    def test_cancellation_stops_process_and_records_cancelled(self):
        process=Mock(pid=9999999);process.poll.return_value=None
        process.wait.side_effect=[KeyboardInterrupt,None]
        with patch.object(runtime,'provenance',return_value={'scope':'synthetic'}), \
             patch.object(runtime.subprocess,'Popen',return_value=process),patch.object(runtime.os,'killpg') as kill, \
             patch('sys.stderr',new_callable=io.StringIO),self.assertRaises(KeyboardInterrupt):
            runtime.execute_job('diagnosis',{},options(self.root/'records'),require_key=False)
        kill.assert_called()
        record=json.loads(next((self.root/'records').rglob('run.json')).read_text())
        self.assertEqual(record['status'],'CANCELLED')
    def test_unique_directories_preserve_prior_results(self):
        body="(d/'response.json').write_text(json.dumps({'ok':True,'result':{'mode':'diagnosis','report':'synthetic','tools':[]}}))"
        _,first=self.execute(body);before=(first/'result.json').read_bytes()
        _,second=self.execute(body)
        self.assertNotEqual(first,second);self.assertEqual((first/'result.json').read_bytes(),before)
    def test_request_key_missing_prevents_spawn(self):
        with patch.dict(os.environ,{},clear=True),patch.object(runtime.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'not inherited'):
                runtime.execute_job('diagnosis',{},options(self.root/'records'))
        spawn.assert_not_called()
    def test_invalid_options_rejected(self):
        for changes in ({'retries':4},{'timeout':0},{'request_timeout':-1},{'progress_every':0},{'model':' '}):
            with self.subTest(changes=changes),self.assertRaises(ValueError): runtime.validate_options(options(self.root,**changes))
    def test_sdk_hidden_retries_disabled(self):
        model=runtime.configured_model()
        self.assertEqual(model.retries,0);self.assertFalse(model.retry_with_guidance)
        self.assertEqual(model.client_params['http_options']['retry_options']['attempts'],1)
    def test_structured_provider_codes_only(self):
        self.assertEqual(runtime.provider_code('{"error":{"code":503}}'),503)
        self.assertEqual(runtime.provider_code("{'error': {'code': 429}}"),429)
        self.assertIsNone(runtime.provider_code('request id 503 may be unrelated'))
        error=runtime.ProviderRunError('failed','{"error":{"code":503}}')
        self.assertEqual(error.status_code,503)
    def test_redacted_json_and_logs(self):
        secret='AIza'+'Q'*30
        with patch.dict(os.environ,{'GOOGLE_API_KEY':secret}):
            runtime.write_json(self.root/'record.json',{'message':secret,'nested':[secret]})
            logger=RedactingLog(self.root/'worker.log')
            logger.write('error '+secret[:12]);logger.write(secret[12:]+'\n');logger.flush()
        for name in ('record.json','worker.log'):
            self.assertNotIn(secret,(self.root/name).read_text());self.assertIn('[REDACTED]',(self.root/name).read_text())
    def test_verify_mode_requires_relevant_successful_tools(self):
        no_tools=SimpleNamespace(tools=[])
        with self.assertRaisesRegex(RuntimeError,'missing successful tools'):
            runtime.verify_tool_mode(no_tools,'verify',['compare_domains'])
        self.assertEqual(runtime.verify_tool_mode(no_tools,'preload',[])['status'],'NOT_DEMONSTRATED')
        checked=SimpleNamespace(tools=[SimpleNamespace(tool_name='compare_domains',tool_call_error=False,result='synthetic validated result')])
        self.assertEqual(runtime.verify_tool_mode(checked,'verify',['compare_domains'])['status'],'RECORDED')
    def test_tool_audit_hashes_results_without_arguments(self):
        result=SimpleNamespace(tools=[SimpleNamespace(tool_name='compare_domains',tool_call_error=False,result='synthetic result',tool_args={'private':'do not log'})])
        audit=runtime.tool_audit(result)
        self.assertTrue(audit[0]['result_sha256']);self.assertNotIn('private',json.dumps(audit))
    def test_default_output_does_not_dump_references(self):
        value={'mode':'diagnosis','model':'offline','report':'synthetic interpretation','tools':[],
               'verified_reference':{'domain_reference':{},'provenance':'RAW_CONTEXT_SENTINEL','sources':{'hash':'SECRET_HASH_SENTINEL'}}}
        formatted=format_report(value)
        self.assertIn('已核對事實',formatted);self.assertIn('模型解讀',formatted)
        self.assertNotIn('RAW_CONTEXT_SENTINEL',formatted);self.assertNotIn('SECRET_HASH_SENTINEL',formatted)
    def test_observed_unified_averaging_claim_rejected(self):
        values={k:'synthetic' for k in VisualVerificationReport.model_fields}
        values['bounded_interpretation']='Local spatial jitter is averaged out over the 1201-frame clip.'
        with self.assertRaisesRegex(RuntimeError,'averaged out'):
            validate_visual_boundaries(VisualVerificationReport.model_validate(values))
    def test_negated_averaging_claim_allowed(self):
        values={k:'synthetic' for k in VisualVerificationReport.model_fields}
        values['bounded_interpretation']='These metrics cannot establish that spatial jitter is averaged out.'
        validate_visual_boundaries(VisualVerificationReport.model_validate(values))

    def test_heartbeat_and_elapsed_time_are_recorded(self):
        body="time.sleep(.35)\n(d/'response.json').write_text(json.dumps({'ok':True,'result':{'mode':'diagnosis','report':'synthetic','tools':[]}}))"
        _,directory=self.execute(body,progress_every=.05)
        events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
        self.assertTrue(any(e['stage']=='waiting' for e in events))
        self.assertTrue(all('elapsed_seconds' in e for e in events))

    def test_tool_name_without_result_is_not_verification(self):
        result=SimpleNamespace(tools=[SimpleNamespace(tool_name='compare_domains',tool_call_error=False,result=None)])
        with self.assertRaises(RuntimeError): runtime.verify_tool_mode(result,'verify',['compare_domains'])

    def test_unrelated_claim_call_does_not_complete_diagnosis_verification(self):
        result=SimpleNamespace(tools=[SimpleNamespace(tool_name='check_diagnostic_claim',tool_call_error=False,
            result='synthetic',tool_args={'claim_id':'unrelated'})])
        with self.assertRaisesRegex(RuntimeError,'overfitting claim'):
            runtime.verify_tool_mode(result,'verify',['check_diagnostic_claim'])
        result.tools[0].tool_args={'claim_id':'overfitting'}
        runtime.verify_tool_mode(result,'verify',['check_diagnostic_claim'])

    def test_step6_counts_cannot_be_labeled_median(self):
        fields={k:'synthetic' for k in VisualVerificationReport.model_fields}
        fields['numerical_agreements']='From /output/step6/taiwan/comparison.json aggregation=median, lane_width_near_nonpositive_frames is 0.'
        reference={'source':{'path':'/output/step6/taiwan/comparison.json'},'metrics':{'lane_width_near_nonpositive_frames':0}}
        with self.assertRaisesRegex(RuntimeError,'means/maxima/counts'):
            validate_unified_comparison(VisualVerificationReport.model_validate(fields),reference)

    def test_step6_count_label_remains_valid(self):
        fields={k:'synthetic' for k in VisualVerificationReport.model_fields}
        fields['numerical_agreements']='From /output/step6/taiwan/comparison.json lane_width_near_nonpositive_frames count is 0.'
        reference={'source':{'path':'/output/step6/taiwan/comparison.json'},'metrics':{'lane_width_near_nonpositive_frames':0}}
        validate_unified_comparison(VisualVerificationReport.model_validate(fields),reference)
