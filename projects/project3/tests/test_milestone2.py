"""Offline-only dataset tests; all injected detections/annotations are test data."""
import copy
import hashlib
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from p3.research.dataset import loads, validate_record as validate_v1
from p3.research.dataset_v2 import (canonical, digest, load_bundle, quality_report,
                                   validate_record, validate_records, session_id)
from p3.research.recorder import record_media
from p3.research.annotations import (annotation_template, validate_annotations, extract_annotation_frames)
from p3.research.evaluate_dataset import compare_dataset
from p3.follow import FollowController


class FakeDetector:
    def predict(self, image):
        return [{'class_id': 0, 'label': 'person', 'objectness': .9,
                 'box': [140., 100., 180., 200.]}], {}


class Clock:
    def __init__(self): self.t = 1000.
    def __call__(self): self.t += .01; return self.t


class OfflineFixture(unittest.TestCase):
    def setUp(self):
        # Keep generated fixtures within this repository; no camera or network.
        # artifacts/ is gitignored, so a fresh clone does not have the directory yet.
        base = Path(__file__).resolve().parents[1]/'artifacts'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base, prefix='milestone2-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source.avi'
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*'MJPG'), 20, (320, 300))
        self.assertTrue(writer.isOpened())
        for i in range(4): writer.write(np.full((300,320,3), i*30, np.uint8))
        writer.release()
        self.bundle = self.root/'dataset'
        self.manifest = self.record(self.bundle)
        self.records = load_bundle(self.bundle)[1]

    def record(self, directory, **options):
        defaults = dict(max_frames=10, detector=FakeDetector(),
                        detector_fingerprint={'kind':'synthetic_test_detections', 'reference':'unit-test-only'},
                        clock=Clock())
        defaults.update(options)
        return record_media(self.source, directory, **defaults)

    def rewrite(self, records=None, manifest=None):
        records = self.records if records is None else records
        manifest = copy.deepcopy(self.manifest if manifest is None else manifest)
        (self.bundle/'records.jsonl').write_text(''.join(canonical(r)+'\n' for r in records))
        manifest['records']['sha256'] = digest(self.bundle/'records.jsonl')
        (self.bundle/'manifest.json').write_text(canonical(manifest)+'\n')

    def reviewed_test_annotations(self):
        # Deliberately authored test-only values exercise the human-label validator.
        # Never exported as real evidence or offered as annotations of source media.
        document = annotation_template(self.bundle)
        document['status'] = 'reviewed'
        document['provenance'] = {'kind':'human_annotation', 'annotator':'TEST-ONLY',
                                  'reviewer':'TEST-ONLY', 'reference':'unit-test-contract-fixture'}
        document['target_person_id'] = 9
        for row in document['frames']:
            row['reviewed'] = True
            row['persons'] = [{'person_id':9, 'box':[140,100,180,200], 'occlusion':'none'}]
        return document


class RecorderTests(OfflineFixture):
    def test_video_order_references_pixels_and_source_preservation(self):
        self.assertEqual(len(self.records), 4)
        self.assertEqual(self.manifest['termination']['reason'], 'EOF')
        self.assertEqual(digest(self.source), self.manifest['media']['sha256'])
        self.assertEqual(self.manifest['media']['path_kind'], 'absolute')
        self.assertEqual(self.manifest['media']['path'], str(self.source.resolve()))
        self.assertEqual(load_bundle(self.bundle, verify_pixels=True)[1], self.records)
        for i, row in enumerate(self.records):
            self.assertEqual(row['frame_id'], i)
            self.assertEqual(row['frame_reference']['decoded_index'], i)
            self.assertEqual(row['observations']['value']['camera_metadata']['width'], 320)
            self.assertIsNone(row['capture_timestamp']['value'])
            self.assertEqual(row['timestamp']['value']['semantics'], 'processing_complete')
            self.assertEqual(row['legacy_decision']['action'], 'STOP')

    def test_stable_identity_separate_run_clocks(self):
        other = self.root/'other'
        manifest = self.record(other, clock=Clock())
        self.assertEqual(manifest['session_id'], self.manifest['session_id'])
        self.assertEqual((other/'records.jsonl').read_bytes(), (self.bundle/'records.jsonl').read_bytes())
        altered = self.record(self.root/'alternate', method='hungarian')
        self.assertNotEqual(altered['session_id'], self.manifest['session_id'])

    def test_explicit_selection_cancel_and_numerical_parity(self):
        directory = self.root/'selected'
        self.record(directory, selection_schedule={0:1, 2:None, 3:1})
        rows = load_bundle(directory)[1]
        baseline = FollowController()
        for row in rows:
            tracks = row['observations']['value']['tracks']
            if row['frame_id'] in (0,3): expected = baseline.select(1, tracks)
            elif row['frame_id'] == 2: expected = baseline.cancel()
            else: expected = baseline.update(tracks, (300,320), row['processing']['age_at_decision_seconds'])
            self.assertEqual(row['legacy_decision'], expected)
        self.assertEqual(rows[1]['legacy_decision']['speed'], .3)
        self.assertEqual(rows[2]['selection']['event'], 'cancel')
        self.assertEqual(rows[2]['operator_command']['provenance']['kind'], 'offline_selection_schedule')

    def test_image_and_bounded_frame_limit(self):
        image = self.root/'image.png'; cv2.imwrite(str(image), np.zeros((300,320,3),np.uint8))
        m = record_media(image,self.root/'image-dataset',max_frames=1,detector=FakeDetector(),
                         detector_fingerprint={'kind':'synthetic_test','reference':'test'},clock=Clock())
        self.assertEqual(m['records']['count'],1)
        self.assertEqual(m['termination']['reason'],'frame_limit')

    def test_existing_output_and_source_refused(self):
        before = self.source.read_bytes()
        with self.assertRaises(FileExistsError): self.record(self.bundle)
        with self.assertRaises(FileExistsError): self.record(self.source)
        self.assertEqual(before,self.source.read_bytes())

    def test_no_hardware_and_input_validation(self):
        for value in ('0', 'https://example.invalid/video.mp4'):
            with self.assertRaises(ValueError): record_media(value,self.root/'forbidden')
        for options in ({'max_frames':0},{'selection_schedule':{True:1}},
                        {'selection_schedule':{0:True}},{'method':'kalman'}):
            with self.assertRaises(ValueError): self.record(self.root/'bad-config',**options)
        with patch('p3.pipeline.cv2.VideoCapture', wraps=cv2.VideoCapture) as factory:
            self.record(self.root/'file-only')
            self.assertTrue(all(isinstance(call.args[0],str) and call.args[0] == str(self.source) for call in factory.call_args_list))

    def test_failure_partial_journal_final_stop_and_cleanup(self):
        destination = self.root/'failed'
        detector = FakeDetector()
        detector.predict = lambda _: (_ for _ in ()).throw(RuntimeError('inference failed'))
        with self.assertRaises(RuntimeError): self.record(destination,detector=detector)
        failure = loads((destination/'failure.json').read_text())
        self.assertEqual(failure['final_decision']['action'],'STOP')
        self.assertFalse((destination/'manifest.json').exists())
        self.assertEqual(quality_report(destination)['status'],'FAIL')

    def test_invalid_or_backward_clock_rejected(self):
        values = iter([10.,11.,10.,12.,13.,14.])
        with self.assertRaises(ValueError): self.record(self.root/'clock',clock=lambda:next(values))
        self.assertTrue((self.root/'clock/failure.json').is_file())

    def test_stale_processing_age_stops_without_reinterpreting_time(self):
        class SlowClock:
            def __init__(self): self.t=100.
            def __call__(self): self.t+=.3; return self.t
        directory=self.root/'stale'
        self.record(directory,selection_schedule={0:1},clock=SlowClock())
        rows=load_bundle(directory)[1]
        self.assertGreater(rows[1]['processing']['age_at_decision_seconds'],.5)
        self.assertEqual(rows[1]['legacy_decision']['action'],'STOP')
        self.assertEqual(rows[1]['legacy_decision']['reason'],'stale_or_invalid_frame_age')

    def test_env_media_root_used_when_argument_omitted(self):
        directory = self.root/'env-dataset'
        with patch.dict(os.environ, {'P3_MEDIA_ROOT': str(self.root)}):
            manifest = self.record(directory)
            self.assertEqual(manifest['media']['path'], 'source.avi')
            self.assertEqual(manifest['media']['path_kind'], 'relative')
            self.assertEqual(quality_report(directory)['status'], 'PASS')

    def test_media_root_stores_relative_path(self):
        directory = self.root/'relative-dataset'
        manifest = self.record(directory, media_root=self.root)
        self.assertEqual(manifest['media']['path'], 'source.avi')
        self.assertEqual(manifest['media']['path_kind'], 'relative')
        self.assertEqual(quality_report(directory, media_root=self.root)['status'], 'PASS')
        outside = self.root/'not-a-root'
        outside.mkdir()
        rejected = self.root/'rejected'
        with self.assertRaises(ValueError):
            self.record(rejected, media_root=outside)
        self.assertFalse(rejected.exists())

    def test_detector_mutating_image_rejected(self):
        detector = FakeDetector()
        original = detector.predict
        def mutate(image):
            image[:]=255
            return original(image)
        detector.predict = mutate
        with self.assertRaises(ValueError): self.record(self.root/'mutated',detector=detector)


class ContractTests(OfflineFixture):
    def test_v1_contract_not_silently_extended(self):
        with self.assertRaises(ValueError): validate_v1(self.records[0])
        validate_record(self.records[0])

    def test_order_duplicates_missing_frames(self):
        for rows in (list(reversed(self.records)), [self.records[0],self.records[0]], self.records[1:], [None]):
            with self.assertRaises(ValueError): validate_records(rows)
        rows = copy.deepcopy(self.records); rows[1]['processing']['read_start']=0
        with self.assertRaises(ValueError): validate_records(rows)

    def test_missing_fields_media_provenance_geometry_units_metadata(self):
        mutations = [
            lambda r:r.pop('processing'),
            lambda r:r['observations']['value'].update(camera_frame_reference=None),
            lambda r:r['observations'].update(provenance={}),
            lambda r:r['observations']['value']['detections'][0].update(box=[0,0,999,999]),
            lambda r:r['observations']['value']['tracks'][0].update(box=[0,0,0,2]),
            lambda r:r['rule_based_pseudo_labels']['value'].update(units='m/s,rad/s'),
            lambda r:r['rule_based_pseudo_labels']['value'].update(source_controller='AI'),
            lambda r:r['legacy_decision'].update(target_id=20),
            lambda r:r['processing'].update(decision_end=float('nan')),
            lambda r:r['frame_reference'].update(decoded_index=True),
            lambda r:r['observations']['value'].update(target_box=[0,0,1,1]),
            lambda r:r['selection'].update(controller_target_id=True),
        ]
        for mutation in mutations:
            record=copy.deepcopy(self.records[0]); mutation(record)
            with self.assertRaises(ValueError): validate_record(record)

    def test_integrity_tamper_and_corrupt_records(self):
        with (self.bundle/'records.jsonl').open('a') as stream:stream.write('{corrupt}\n')
        self.assertEqual(quality_report(self.bundle)['status'],'FAIL')
        self.rewrite()
        rows=copy.deepcopy(self.records); rows[0]['timestamp']['value']['semantics']='camera_capture'
        self.rewrite(rows)
        self.assertEqual(quality_report(self.bundle)['status'],'FAIL')

    def test_missing_or_modified_original_media(self):
        raw=self.source.read_bytes()
        self.source.write_bytes(raw+b'changed')
        failed=quality_report(self.bundle)
        self.assertEqual(failed['status'],'FAIL')
        self.assertIn('media integrity failure', failed['errors'][0])
        library=self.root/'library'
        library.mkdir()
        (library/'source.avi').write_bytes(raw)
        # A wrong file at the recorded absolute path is corruption even if a good copy exists.
        self.assertEqual(quality_report(self.bundle, media_root=library)['status'],'FAIL')
        self.source.write_bytes(raw)
        self.source.unlink()
        missing=quality_report(self.bundle)
        self.assertEqual(missing['status'],'WARN')
        self.assertEqual(missing['original_media'],'missing')
        self.assertFalse(missing['media_hash_verified'])
        self.assertTrue(missing['record_hash_verified'])
        self.assertTrue(any(item.startswith('missing original media reference:') for item in missing['warnings']))
        self.assertGreater(missing['frames'],0)
        with self.assertRaises(ValueError) as caught:
            load_bundle(self.bundle)
        self.assertIn('missing original media reference', str(caught.exception))
        (library/'source.avi').write_bytes(raw+b'not-the-original')
        self.assertEqual(quality_report(self.bundle, media_root=library)['status'],'WARN')
        (library/'source.avi').write_bytes(raw)
        relocated=quality_report(self.bundle, media_root=library)
        self.assertEqual(relocated['status'],'PASS')
        self.assertTrue(relocated['media_hash_verified'])
        self.assertEqual(relocated['original_media'],'present')

    def test_legacy_manifest_without_path_kind_and_relative_not_cwd(self):
        manifest=copy.deepcopy(self.manifest)
        manifest['media'].pop('path_kind', None)
        self.rewrite(manifest=manifest)
        stored=loads((self.bundle/'manifest.json').read_text())
        self.assertNotIn('path_kind', stored['media'])
        self.assertEqual(quality_report(self.bundle)['status'],'PASS')
        manifest['media']['path']='source.avi'
        manifest['media']['path_kind']='relative'
        self.rewrite(manifest=manifest)
        cwd=os.getcwd()
        try:
            os.chdir(self.root)
            report=quality_report(self.bundle)
        finally:
            os.chdir(cwd)
        self.assertEqual(report['status'],'WARN')
        self.assertFalse(report['media_hash_verified'])
        self.assertEqual(quality_report(self.bundle, media_root=self.root)['status'],'PASS')
        manifest['media']['path']='../source.avi'
        self.rewrite(manifest=manifest)
        escaped=quality_report(self.bundle, media_root=self.bundle)
        self.assertEqual(escaped['status'],'FAIL')
        self.assertIn('escapes media root', escaped['errors'][0])

    def test_cli_validate_missing_media_warns(self):
        self.source.unlink()
        env=dict(os.environ)
        env.pop('P3_MEDIA_ROOT', None)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
        output=self.root/'warn-quality.json'
        result=subprocess.run([sys.executable,'-m','p3.research.offline','validate',str(self.bundle),'--output',str(output)],
                              env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('WARN', result.stdout)
        self.assertIn('missing original media reference', result.stdout)
        report=loads(output.read_text())
        self.assertEqual(report['status'],'WARN')
        self.assertTrue(report['record_hash_verified'])
        pixels=self.root/'warn-pixels.json'
        result=subprocess.run([sys.executable,'-m','p3.research.offline','validate',str(self.bundle),'--output',str(pixels),'--verify-pixels'],
                              env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        skipped=loads(pixels.read_text())
        self.assertEqual(skipped['status'],'WARN')
        self.assertFalse(skipped['decoded_pixels_verified'])
        self.assertTrue(any('pixel verification skipped' in item for item in skipped['warnings']))

    def test_pixel_integrity_even_when_record_hash_recomputed(self):
        rows=copy.deepcopy(self.records); rows[0]['frame_reference']['decoded_bgr_sha256']='0'*64
        self.rewrite(rows)
        self.assertEqual(quality_report(self.bundle,verify_pixels=True)['status'],'FAIL')

    def test_missing_implementation_or_detector_provenance(self):
        for key in ('implementation','detector'):
            m=copy.deepcopy(self.manifest)
            if key=='implementation':m['identity'][key]={}
            else:m['identity']['configuration'][key]={}
            m['session_id']=session_id(m['identity'])
            rows=copy.deepcopy(self.records)
            for r in rows:r['session_id']=m['session_id']
            self.rewrite(rows,m)
            self.assertEqual(quality_report(self.bundle)['status'],'FAIL')

    def test_corrupt_json_even_with_matching_manifest_hash(self):
        for text in ('{', '{"frame_id":0,"frame_id":1}', '{"x":NaN}', 'null'):
            (self.bundle/'records.jsonl').write_text(text+'\n')
            manifest=copy.deepcopy(self.manifest)
            manifest['records']['sha256']=digest(self.bundle/'records.jsonl')
            (self.bundle/'manifest.json').write_text(canonical(manifest)+'\n')
            self.assertEqual(quality_report(self.bundle)['status'],'FAIL')

    def test_cli_validate_failure_and_draft_annotations_exit_nonzero(self):
        env=dict(os.environ)
        env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
        command=[sys.executable,'-m','p3.research.offline']
        template=self.root/'template.json'
        result=subprocess.run(command+['template',str(self.bundle),'--output',str(template)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run(command+['validate-annotations',str(self.bundle),str(template)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        (self.bundle/'records.jsonl').write_text('corrupt')
        output=self.root/'failed-quality.json'
        result=subprocess.run(command+['validate',str(self.bundle),'--output',str(output)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertEqual(loads(output.read_text())['status'],'FAIL')

    def test_quality_report_counts_and_failed_marker(self):
        q=quality_report(self.bundle,verify_pixels=True)
        self.assertEqual(q['status'],'PASS');self.assertEqual(q['person_detections'],4)
        self.assertEqual(q['simulated_follow_rows'],0)
        (self.bundle/'failure.json').write_text('{}')
        self.assertEqual(quality_report(self.bundle)['status'],'FAIL')


class AnnotationTests(OfflineFixture):
    def test_blank_template_does_not_copy_predictions(self):
        document=annotation_template(self.bundle)
        self.assertTrue(all(f['persons']==[] for f in document['frames']))
        validate_annotations(document,self.manifest,self.records,require_reviewed=False)
        with self.assertRaises(ValueError):validate_annotations(document,self.manifest,self.records)
        report=compare_dataset(self.bundle,document)
        self.assertTrue(report['real_accuracy_status'].startswith('BLOCKED'))
        self.assertTrue(all(m['metrics'] is None for m in report['methods'].values()))

    def test_test_only_reviewed_contract_metrics_and_identical_inputs(self):
        doc=self.reviewed_test_annotations()
        report=compare_dataset(self.bundle,doc)
        a,b=report['methods'].values()
        self.assertEqual(a['input_sha256'],b['input_sha256'])
        for method in (a,b):
            self.assertEqual(method['metrics']['IDF1'],1.)
            self.assertEqual(method['metrics']['ID_switches'],0)
            self.assertEqual(method['tracking_ms']['count'],120)

    def test_occlusion_persistent_identity_target(self):
        doc=self.reviewed_test_annotations()
        doc['frames'][1]['persons'][0].update(box=None,occlusion='full')
        doc['frames'][2]['persons'][0]['occlusion']='partial'
        validate_annotations(doc,self.manifest,self.records)
        report=compare_dataset(self.bundle,doc)
        self.assertEqual(report['annotation_coverage']['fully_occluded_without_box_excluded'],1)
        self.assertEqual(report['methods']['greedy_iou']['metrics']['target_recovery']['rate'],1.)

    def test_reject_invalid_human_annotation_contracts(self):
        mutations=[lambda d:d['provenance'].update(kind='synthetic_ground_truth'),
            lambda d:d['provenance'].update(annotator=''),
            lambda d:d['provenance'].update(reviewer=''),
            lambda d:d['frames'][0].update(reviewed=False),
            lambda d:d.update(target_person_id=99),
            lambda d:d['frames'][0]['persons'][0].update(occlusion='invented'),
            lambda d:d['frames'][0]['persons'][0].update(box=None),
            lambda d:d['frames'][0]['persons'][0].update(box=[0,0,400,200]),
            lambda d:d['frames'][0]['persons'].append(dict(d['frames'][0]['persons'][0])),
            lambda d:d['dataset_reference'].update(media_sha256='0'*64),
            lambda d:d['frames'][0].update(frame_id=True),
            lambda d:d['frames'][0].update(frame_reference='fake')]
        for mutation in mutations:
            document=self.reviewed_test_annotations();mutation(document)
            with self.assertRaises(ValueError):validate_annotations(document,self.manifest,self.records)

    def test_extract_original_pixels_and_refuse_overwrite(self):
        destination=self.root/'annotation-frames'
        index=extract_annotation_frames(self.bundle,destination,[0,3])
        self.assertEqual([r['frame_id'] for r in index],[0,3])
        decoded=cv2.imread(str(destination/'frame-000000.png'))
        self.assertEqual(hashlib.sha256(decoded.tobytes()).hexdigest(),self.records[0]['frame_reference']['decoded_bgr_sha256'])
        with self.assertRaises(FileExistsError):extract_annotation_frames(self.bundle,destination,[0])
        for ids in ([3,0],[0,0],[True],[9]):
            with self.assertRaises(ValueError):annotation_template(self.bundle,ids)

    def test_unannotated_evaluation_is_blocked_latency_available(self):
        report=compare_dataset(self.bundle)
        self.assertTrue(report['real_accuracy_status'].startswith('BLOCKED'))
        for method in report['methods'].values():
            self.assertIsNone(method['metrics'])
            self.assertGreater(method['tracking_ms']['mean'],0)
