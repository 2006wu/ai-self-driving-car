"""Offline synthetic fixtures; no credentials, API calls, model inference or training."""
import base64
import hashlib
import io
import json
import struct
import tempfile
import unittest
import zlib
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import v2_evidence as evidence
import vision_agent as vision
import diagnosis_agent
import report_contract as contract


def png():
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\0\0'))+chunk(b'IEND',b'')


def integrated_fixture_report():
    values={k:'synthetic offline response' for k in vision.VisualVerificationReport.model_fields}
    values['numerical_agreements']='Whole clip frames=2, source /output/step6/usa/comparison.json; not per-frame accuracy.'
    values['numerical_disagreements']='No frame-specific ground truth is available for a numerical disagreement.'
    return vision.VisualVerificationReport.model_validate(values)


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()/'exports';self.root.mkdir()
        self.root_patch=patch.object(evidence,'ROOT',self.root);self.root_patch.start()
        self.addCleanup(self.root_patch.stop);self.addCleanup(self.temp.cleanup)
        self.entries={}
        self.put('training',{'status':'complete','epochs_completed':2,'loss_history':[2.,1.],
            'val_loss_history':[1.,3.],'best_val_loss':1.,'best_epoch':1,
            'train_sequences':['synthetic-train'],'validation_sequences':['synthetic-val'],'resume_semantics':'fresh'})
        self.put('verification',{'matrix_complete':True,'ground_truth_accuracy':None,
            'cells':{},'comparisons':{},'cross_domain_raw_response':{},
            'behavioral_quality':'inconclusive_without_ground_truth','limitations':['synthetic']})
        for domain in ('usa','taiwan'):
            self.put(domain,{'domain':domain,'metrics':{'final':{'frames':2},'best':{'frames':2}}})
        record={'intervention':'real_cross_domain_swap','metrics':{'full':{'mae':1e-8,'max_abs':1e-7,'rms':2e-8}}}
        self.put('sensitivity',{'status':'complete','roles':{role:{'domains':{domain:{'records':[record]} for domain in ('usa','taiwan')}} for role in ('final','best')}})
        trace=[{'layer':'synthetic_layer','baseline':{'rms':1.},'comparisons':{'usa_middle':{'rms':1e-8}}}]
        self.put('encoder',{'status':'complete','models':{role:{'encoder_trace':trace} for role in ('final','best','fresh_reference')},'input_scale':{},'reference_caveat':'synthetic'})
        self.put('encoder_controls',{'status':'complete','records':[]})
        aggregates={role:{domain:{'original':{'loss':{'median':2.},'image_rms':{'median':1e-15},'state_rms':{'median':.2}}} for domain in ('overall','usa','taiwan')} for role in ('final','best')}
        self.put('gradient',{'status':'complete','aggregates':aggregates,'records':12,'samples':2})
        self.put('interpretation',{'status':'complete','shared_shortcut_claim':'not established; conditional'})
        self.put('fresh_gradient',{'status':'complete','seeds':[1,2,3],'training_steps':0,'optimizer_created':False,
            'records':6,'aggregates':{str(seed):{'stem_rms':1e-14,'late_rms':1e-4} for seed in (1,2,3)},'caveat':'synthetic controls'})
        self.image='step6/usa/final/frame_00001.png'
        raw=png();self.put_relative(self.image,raw)
        self.put_relative('step6/usa/final/manifest.json',json.dumps({'status':'complete','run_type':'production','domain':'usa','model':{'role':'final'},'artifact_sha256':{'frame_00001.png':hashlib.sha256(raw).hexdigest()}}).encode())
        self.save_manifest()

    def put_relative(self,rel,raw):
        p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        self.entries[rel]={'source':'/output/'+rel,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

    def put(self,key,data):
        self.put_relative(evidence.CANONICAL[key],json.dumps(data).encode())
        self.save_manifest()

    def save_manifest(self):
        (self.root/'export_manifest.json').write_text(json.dumps({'files':self.entries}))

    def test_01_all_artifact_readers(self):
        report=evidence.diagnostic_report()
        self.assertEqual(len(report['sections']),7)
        self.assertEqual(report['sections']['get_training_evidence']['facts']['final_val_loss'],3.)
        self.assertEqual(report['sections']['get_fresh_gradient_evidence']['facts']['top_to_stem_orders']['1'],10.)

    def test_02_canonical_provenance(self):
        _,source=evidence.read_artifact('training')
        self.assertEqual(source['path'],'/output/'+evidence.CANONICAL['training'])

    def test_03_missing_evidence_unknown(self):
        (self.root/evidence.CANONICAL['fresh_gradient']).unlink()
        self.assertEqual(evidence.check_diagnostic_claim('training_caused_collapse')['classification'],'UNKNOWN / NOT EVALUATED')

    def test_04_malformed_json(self):
        self.put_relative(evidence.CANONICAL['training'],b'bad text');self.save_manifest()
        with self.assertRaises(ValueError):evidence.get_training_evidence()

    def test_05_malformed_schema(self):
        self.put('training',{'status':'complete'})
        with self.assertRaises(ValueError):evidence.get_training_evidence()

    def test_06_absolute_path_rejected(self):
        with self.assertRaises(ValueError):evidence.approved_path('/etc/passwd')

    def test_07_traversal_rejected(self):
        with self.assertRaises(ValueError):evidence.approved_path('step6/usa/../taiwan/file.png')

    def test_08_symlink_escape_rejected(self):
        p=self.root/evidence.CANONICAL['training'];p.unlink();p.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):evidence.read_artifact('training')

    def test_09_root_symlink_rejected(self):
        link=Path(self.temp.name)/'link';link.symlink_to(self.root)
        with patch.object(evidence,'ROOT',link),self.assertRaises(ValueError):evidence.approved_path('export_manifest.json')

    def test_10_read_only(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        evidence.diagnostic_report();vision.discover_images();vision.run(self.image,offline=True)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_11_supported_claim(self):
        self.assertEqual(evidence.check_diagnostic_claim('image_invariance')['classification'],'SUPPORTED')

    def test_12_causal_claims_unsupported(self):
        for claim in ('training_caused_collapse','initializer_sole_cause','universal_shortcut'):
            self.assertEqual(evidence.check_diagnostic_claim(claim)['classification'],'UNSUPPORTED')

    def test_13_quality_unknown(self):
        self.assertEqual(evidence.check_diagnostic_claim('driving_quality')['classification'],'UNKNOWN / NOT EVALUATED')
        self.assertIn('not driving-quality',evidence.compare_domains()['limitations'])

    def test_14_domain_distinction(self):
        self.assertEqual(set(evidence.compare_domains()['facts']['step6']),{'usa','taiwan'})
        self.assertIn('train-seen',evidence.compare_domains()['interpretation'])

    def test_15_no_invented_unknown_claim(self):
        claim=evidence.check_diagnostic_claim('has_perfect_safety')
        self.assertEqual(claim['sources'],[])
        self.assertEqual(claim['classification'],'UNKNOWN / NOT EVALUATED')

    def test_16_image_discovery(self):
        images=vision.discover_images();self.assertEqual(len(images),1)
        self.assertEqual(images[0]['width'],1)

    def test_17_unapproved_image_paths(self):
        for rel in ('step6/smoke/usa/final/frame_00001.png','external/aJLL/Agent/x.png','step6/usa/final/../x.png'):
            with self.assertRaises(ValueError):vision.approved_image(rel)

    def test_18_corrupt_image_rejected(self):
        self.put_relative(self.image,b'invalid png');self.save_manifest()
        # Keep manifest hash consistent: rejection must also validate actual PNG bytes.
        p=self.root/'step6/usa/final/manifest.json';m=json.loads(p.read_text())
        m['artifact_sha256']['frame_00001.png']=hashlib.sha256(b'invalid png').hexdigest();p.write_text(json.dumps(m))
        with self.assertRaises(ValueError):vision.approved_image(self.image)

    def test_19_schema_and_qualitative_limit(self):
        report={k:'not evaluated' for k in vision.VisualVerificationReport.model_fields}
        self.assertEqual(vision.VisualVerificationReport.model_validate(report).confidence,'not evaluated')
        with self.assertRaises(ValueError):vision.VisualVerificationReport.model_validate({})
        offline=vision.run(self.image,offline=True)
        self.assertIsNone(offline['report']);self.assertFalse(offline['gemini_executed'])
        self.assertIn('not quantitative ground truth',offline['limitations'])

    def test_20_sdk_formats_actual_image_bytes(self):
        from agno.models.message import Message
        from agno.models.google import Gemini
        from agno.media import Image
        raw,_=vision.approved_image(self.image)
        formatted,_=Gemini(id='offline-test')._format_messages([Message(role='user',content='inspect',images=[Image(content=raw,mime_type='image/png')])])
        parts=formatted[0].parts
        inline=[p.inline_data for p in parts if p.inline_data is not None]
        self.assertEqual(len(inline),1)
        payload=inline[0].data
        self.assertIn(payload,(raw,base64.b64encode(raw)))
        self.assertEqual(inline[0].mime_type,'image/png')

    def test_21_checksum_tamper_rejected(self):
        p=self.root/evidence.CANONICAL['training'];p.write_text('{}')
        with self.assertRaises(ValueError):evidence.get_training_evidence()

    def test_22_nonfinite_rejected(self):
        self.put('training',{'status':'complete','loss_history':[float('inf')]})
        with self.assertRaises(ValueError):evidence.get_training_evidence()

    def test_23_tool_registration(self):
        a=diagnosis_agent.build_agent();self.assertEqual(len(a.tools),8)
        self.assertEqual(len(vision.build_agent(True).tools),8)
        self.assertEqual(vision.build_agent().tools,[])

    def test_24_key_absent_skips_live(self):
        with patch.dict('os.environ',{},clear=True),patch.object(vision,'build_agent') as build:
            with self.assertRaises(SystemExit):vision.run(self.image)
            build.assert_not_called()

    def test_25_overfitting_cautious(self):
        claim=evidence.check_diagnostic_claim('overfitting')
        self.assertEqual(claim['classification'],'PARTIALLY SUPPORTED')

    def test_26_image_symlink_rejected(self):
        p=self.root/self.image;p.unlink();p.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):vision.approved_image(self.image)

    def test_27_truncated_png_crc_rejected(self):
        for raw in (png()[:-4],png()[:35]+b'bad'+png()[38:]):
            with self.assertRaises(ValueError):vision.validate_png(raw)

    def test_28_image_manifest_role_rejected(self):
        p=self.root/'step6/usa/final/manifest.json';m=json.loads(p.read_text());m['model']['role']='best';p.write_text(json.dumps(m))
        with self.assertRaises(ValueError):vision.approved_image(self.image)

    def test_29_live_runner_attaches_bytes_without_real_api(self):
        from agno.run.agent import RunStatus
        report=integrated_fixture_report()
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=report)
            result=vision.run(self.image,unified=True)
            build.assert_called_once_with(True)
            self.assertEqual(build.return_value.run.call_args.kwargs['images'][0].content,png())
            self.assertEqual(result['mode'],'unified')

    def test_30_error_run_never_returns_success(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.error,content='partial')
            with self.assertRaises(RuntimeError):vision.run(self.image)

    def test_31_claim_rejects_malformed_support(self):
        self.put('sensitivity',{'status':'complete'})
        with self.assertRaises(ValueError):evidence.check_diagnostic_claim('image_invariance')

    def test_32_export_is_read_only_and_refuses_overwrite(self):
        import prepare_v2
        rel=evidence.CANONICAL['training']
        raw=(self.root/rel).read_bytes()
        bundle={rel:{**self.entries[rel],'content':base64.b64encode(raw).decode()}}
        # Existing manifest has additional files, so verify must reject, not replace it.
        before=(self.root/'export_manifest.json').read_bytes()
        with patch.object(prepare_v2,'collect',return_value=bundle):
            with self.assertRaises(ValueError):prepare_v2.export(verify=True)
        self.assertEqual((self.root/'export_manifest.json').read_bytes(),before)


    def test_33_diagnosis_error_not_rendered_as_report(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(diagnosis_agent,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.error,content='{"error":{"code":503}}')
            with self.assertRaises(RuntimeError):diagnosis_agent.run_live('diagnose')

    def test_34_diagnosis_empty_completed_report_rejected(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(diagnosis_agent,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=' ')
            with self.assertRaises(RuntimeError):diagnosis_agent.run_live('diagnose')

    def test_35_diagnosis_completed_report(self):
        from agno.run.agent import RunStatus
        from agno.models.response import ToolExecution
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(diagnosis_agent,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content='synthetic diagnostic report',
                tools=[ToolExecution(tool_name='get_training_evidence',tool_args={'private_test_argument':'not for report'},tool_call_error=False)])
            result=diagnosis_agent.run_live('diagnose')
            self.assertEqual(result['report'],'synthetic diagnostic report')
            self.assertEqual(result['tools'],[{'name':'get_training_evidence','error':False}])

    def test_36_unified_reports_tool_names_without_arguments(self):
        from agno.run.agent import RunStatus
        from agno.models.response import ToolExecution
        report=integrated_fixture_report()
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=report,
                tools=[ToolExecution(tool_name='compare_domains',tool_args={'private_test_argument':'not for report'},tool_call_error=False)])
            result=vision.run(self.image,unified=True)
        self.assertEqual(result['tools'],[{'name':'compare_domains','error':False}])
        self.assertNotIn('private_test_argument',json.dumps(result))

    def test_37_unified_question_requests_numerical_evidence_and_custom_preserved(self):
        from agno.run.agent import RunStatus
        report=integrated_fixture_report()
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=report)
            vision.run(self.image,unified=True)
            prompt=build.return_value.run.call_args.args[0]
            self.assertIn('get_verification_evidence',prompt)
            self.assertIn('compare_domains',prompt)
            self.assertIn('whole-clip aggregates',prompt)
            vision.run(self.image,unified=True,question='custom question')
            self.assertTrue(build.return_value.run.call_args.args[0].startswith('custom question\n'))


    def test_38_gradient_reference_keeps_condition_and_metric_identity(self):
        data=evidence.read_artifact('gradient')[0]
        data['aggregates']['final']['overall']['original']['state_parameter_rms']={'median':.01}
        data['aggregates']['final']['overall']['mismatched_state']={
            'image_rms':{'median':9e-14},'state_parameter_rms':{'median':.02}}
        self.put('gradient',data)
        rows=contract.diagnosis_reference()['gradient_reference']
        selected={r['condition']:r for r in rows if r['checkpoint']=='final' and r['domain_aggregate']=='overall'}
        self.assertEqual(selected['original']['metrics']['image_rms'],1e-15)
        self.assertEqual(selected['mismatched_state']['metrics']['image_rms'],9e-14)
        self.assertEqual(selected['original']['metrics']['state_parameter_rms'],.01)
        self.assertEqual(selected['original']['aggregation'],'median')

    def test_39_encoder_endpoint_does_not_use_intermediate_layer(self):
        data=evidence.read_artifact('encoder')[0]
        for model in data['models'].values():
            model['encoder_trace']=[{'layer':name,'baseline':{'rms':rms},
                'comparisons':{'taiwan_quarter':{'rms':diff}}} for name,rms,diff in
                [('stem_conv',73.,19.),('block3b_add',.017,.004),('flatten',5.,3e-7)]]
        self.put('encoder',data)
        row=contract.diagnosis_reference()['encoder_reference'][0]
        self.assertEqual(row['endpoint_layer'],'flatten')
        self.assertEqual(row['rows'][-1]['baseline_rms'],5.)
        self.assertEqual(row['rows'][-1]['comparison_rms']['taiwan_quarter'],3e-7)

    def test_40_metric_definitions_disambiguate_path_width_and_gradient_direction(self):
        self.assertIn('NOT ground-truth',contract.METRIC_RULES['path_near_abs_max_m'])
        self.assertIn('NOT number of negative-path',contract.METRIC_RULES['lane_width_near_nonpositive_frames'])
        self.assertIn('log10(late',contract.METRIC_RULES['top_to_stem_orders'])

    def test_41_unified_reference_selects_image_domain_and_checkpoint(self):
        _,meta=vision.approved_image(self.image)
        reference=contract.unified_reference(meta)
        self.assertEqual(reference['domain'],'usa')
        self.assertEqual(reference['checkpoint'],'final')
        self.assertEqual(reference['metrics'],{'frames':2})
        self.assertIn('whole clip',reference['scope'])
        self.assertEqual(reference['frame_specific_ground_truth'],'NOT AVAILABLE')

    def test_42_unified_reference_checksum_failure_prevents_api(self):
        p=self.root/evidence.CANONICAL['usa'];p.write_text('{}')
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            with self.assertRaises(ValueError):vision.run(self.image,unified=True)
        build.return_value.run.assert_not_called()

    def test_43_unified_placeholder_comparison_rejected(self):
        report=integrated_fixture_report()
        report.numerical_agreements='Not evaluated.'
        report.numerical_disagreements='Not evaluated.'
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            from agno.run.agent import RunStatus
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=report)
            with self.assertRaisesRegex(RuntimeError,'comparison missing'):
                vision.run(self.image,unified=True)

    def test_44_unified_wrong_source_not_accepted(self):
        report=integrated_fixture_report()
        report.numerical_agreements='frames=2 in /output/step6/taiwan/comparison.json'
        _,meta=vision.approved_image(self.image)
        with self.assertRaisesRegex(RuntimeError,'source path and metric key'):
            contract.validate_unified_comparison(report,contract.unified_reference(meta))

    def test_45_unified_output_includes_authenticated_numeric_reference(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=integrated_fixture_report())
            result=vision.run(self.image,unified=True)
        self.assertEqual(result['numerical_reference']['metrics'],{'frames':2})
        self.assertIn('"checkpoint": "final"',build.return_value.run.call_args.args[0])

    def test_46_vision_only_does_not_require_numeric_comparison(self):
        from agno.run.agent import RunStatus
        report=integrated_fixture_report()
        report.numerical_agreements=report.numerical_disagreements='Not evaluated.'
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=report)
            result=vision.run(self.image)
        self.assertIsNone(result['numerical_reference'])

    def test_47_diagnosis_receives_and_returns_verified_reference(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(diagnosis_agent,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content='synthetic diagnosis')
            result=diagnosis_agent.run_live('question')
        self.assertIn('gradient_reference',result['verified_reference'])
        self.assertIn('"condition": "original"',build.return_value.run.call_args.args[0])


    def test_48_observed_taiwan_count_copy_error_rejected(self):
        reference={'domain_reference':{'taiwan':{'final':{'lane_width_near_nonpositive_frames':941}}}}
        report='| N/A | taiwan | final | lane_width_near_nonpositive_frames | clip-level count | $1006$ | `/output/step6/taiwan/comparison.json` |'
        with self.assertRaisesRegex(RuntimeError,'authenticated value is 941'):
            contract.validate_diagnosis_tables(report,reference)

    def test_49_scoped_table_rounded_coordinates_and_exact_counts(self):
        reference={'domain_reference':{'taiwan':{'best':{'path_near_abs_max_m':1.4551631212234497},
                                                         'final':{'lane_width_near_nonpositive_frames':941}}}}
        report='| taiwan | best | path_near_abs_max_m | 1.455163 | /output/step6/taiwan/comparison.json |\n| taiwan | final | lane_width_near_nonpositive_frames | 941 | /output/step6/taiwan/comparison.json |'
        self.assertEqual(contract.validate_diagnosis_tables(report,reference)['checked_step6_table_rows'],2)

    def test_50_programmatic_table_uses_qualified_domains(self):
        reference={'domain_reference':{'usa':{'final':{'lane_width_near_nonpositive_frames':1006}},
                                       'taiwan':{'final':{'lane_width_near_nonpositive_frames':941}}}}
        table=contract.verified_domain_table(reference)
        self.assertIn('| taiwan | final | lane_width_near_nonpositive_frames | 941 |',table)
        self.assertEqual(contract.validate_diagnosis_tables(table,reference)['checked_step6_table_rows'],2)

    def test_51_causal_classification_and_action_are_bounded(self):
        reference=contract.diagnosis_reference()
        self.assertEqual(reference['claim_catalogue']['overfitting']['classification'],'PARTIALLY SUPPORTED')
        self.assertEqual(reference['claim_catalogue']['training_caused_collapse']['classification'],'UNSUPPORTED')
        self.assertIn('Deployment',reference['allowed_next_action'])
        self.assertTrue(any('not proof of activation saturation' in x for x in reference['interpretation_limits']))

    def test_52_unparsed_prose_not_reported_as_validated(self):
        result=contract.validate_diagnosis_tables('a free-form narrative',{'domain_reference':{}})
        self.assertEqual(result['checked_step6_table_rows'],0)
        self.assertEqual(result['status'],'HUMAN_CONTENT_REVIEW_REQUIRED')


    def test_53_progress_marks_evidence_request_draft_and_validation(self):
        from agno.run.agent import RunStatus
        progress=[]
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=integrated_fixture_report())
            vision.run(self.image,unified=True,progress=lambda stage,details:progress.append((stage,details)))
        stages=[r[0] for r in progress]
        self.assertLess(stages.index('evidence_ready'),stages.index('waiting_for_gemini'))
        self.assertLess(stages.index('draft_ready'),stages.index('checking_report'))
        self.assertIn('reference',next(details for stage,details in progress if stage=='evidence_ready'))

    def test_54_verify_mode_cannot_pass_on_preloaded_context_only(self):
        from agno.run.agent import RunStatus
        with patch.dict('os.environ',{'GOOGLE_API_KEY':'offline-dummy'}),patch.object(vision,'collect_verification_tools',return_value=[]),patch.object(vision,'build_agent') as build:
            build.return_value.model.id='offline-model'
            build.return_value.run.return_value=SimpleNamespace(status=RunStatus.completed,content=integrated_fixture_report(),tools=[])
            with self.assertRaisesRegex(RuntimeError,'missing successful tools'):
                vision.run(self.image,unified=True,tool_mode='verify')


class VisionCliTests(unittest.TestCase):
    def test_unified_failure_exits_without_success_json(self):
        with patch.object(vision,'execute_job',side_effect=RuntimeError('live Agent did not complete; no successful vision report')), \
                patch('sys.stdout',new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as caught:
                vision.main(['--image','step6/taiwan/best/frame_00001.png','--unified'])
        self.assertEqual(str(caught.exception),'live Agent did not complete; no successful vision report')
        self.assertEqual(output.getvalue(),'')

    def test_success_json_and_arguments_preserved(self):
        with patch.object(vision,'execute_job',return_value=({'mode':'unified','report':'synthetic'},Path('/tmp/mock-run'))) as run, \
                patch('sys.stdout',new_callable=io.StringIO) as output:
            vision.main(['--image','step6/taiwan/best/frame_00001.png','--unified','--json'])
        self.assertEqual(run.call_args.args[:2],('unified',{'image':'step6/taiwan/best/frame_00001.png','question':None}))
        self.assertEqual(json.loads(output.getvalue())['report'],'synthetic')

    def test_missing_image_still_rejected(self):
        with patch.object(vision,'run') as run, patch('sys.stderr',new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as caught:
                vision.main([])
        self.assertEqual(caught.exception.code,2)
        run.assert_not_called()


if __name__=='__main__':unittest.main()
