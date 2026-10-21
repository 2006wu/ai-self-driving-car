"""Synthetic MOT fixtures only; these tests are not real annotation evidence."""
import copy
import os
from pathlib import Path
import subprocess
import sys

from test_milestone2 import OfflineFixture
from p3.research.annotations import validate_annotations
from p3.research.dataset import loads
from p3.research.evaluate_dataset import compare_dataset
from p3.research.mot_import import import_mot


class MOTImportTests(OfflineFixture):
    def setUp(self):
        super().setUp()
        self.mot = self.root/'gt.txt'
        self.output = self.root/'annotations.json'
        self.mot.write_text('1,9,141,101,40,100,1,1,1\n'
                            '1,12,11,21,20,30,1,1,0.5\n'
                            '3,9,141,101,40,100,1,1,0\n')

    def import_file(self, **options):
        return import_mot(self.bundle, self.mot, self.output, **options)

    def cli(self, *args):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        return subprocess.run([sys.executable, '-m', 'p3.research.offline', *map(str, args)],
                              env=env, capture_output=True, text=True)

    def test_valid_draft_mapping_and_visibility(self):
        summary = self.import_file(target_person_id=9)
        doc = loads(self.output.read_text())
        validate_annotations(doc, self.manifest, self.records, require_reviewed=False)
        self.assertEqual(summary['imported_person_rows'], 3)
        self.assertEqual(summary['status'], 'draft')
        self.assertEqual(doc['frames'][0]['persons'][0]['box'], [140,100,180,200])
        self.assertEqual(doc['frames'][0]['persons'][1]['occlusion'], 'partial')
        self.assertEqual(doc['frames'][2]['persons'][0]['occlusion'], 'full')
        self.assertEqual(doc['frames'][1]['persons'], [])
        self.assertFalse(any(f['reviewed'] for f in doc['frames']))
        self.assertEqual(loads(doc['provenance']['reference'])['source_sha256'], summary['source_sha256'])

    def test_optional_columns_offset_count_zero_origin_and_unsorted_rows(self):
        self.mot.write_text('2,9,140,100,40,100\n1,9,140,100,40,100\n')
        self.import_file(frame_offset=1, frame_count=2, box_origin=0)
        doc = loads(self.output.read_text())
        self.assertEqual([f['frame_id'] for f in doc['frames']], [1,2])
        self.assertEqual(doc['frames'][0]['persons'][0]['box'], [140,100,180,200])

    def test_malformed_rows_rejected_without_output(self):
        cases = ['1,9,141,101,40', 'text,9,141,101,40,100',
                 '1,9,NaN,101,40,100', '1,9,141,101,inf,100',
                 '1,9,141,101,0,100', '1,9,141,101,40,-1',
                 '1,0,141,101,40,100', '1,1.5,141,101,40,100',
                 '1.5,9,141,101,40,100', '0,9,141,101,40,100',
                 '1,9,141,101,40,100,.9', '1,9,141,101,40,100,1,1.5',
                 '1,9,141,101,40,100,1,0', '1,9,141,101,40,100,1,1,-.1',
                 '1,9,141,101,40,100,1,1,1.1', '1,9,141,101,40,100,1,1,nan',
                 '1,9,141,101,40,100,1,1,1,-1',
                 '1,9,141,101,40,100\n2,9,141,101,40,100,1', '']
        for text in cases:
            with self.subTest(text=text):
                self.mot.write_text(text+'\n')
                with self.assertRaises(ValueError): self.import_file()
                self.assertFalse(self.output.exists())

    def test_out_of_range_frame_and_invalid_span(self):
        for frame in (-1, 5, 100):
            self.mot.write_text(f'{frame},9,141,101,40,100\n')
            with self.assertRaises(ValueError): self.import_file()
        for options in ({'frame_offset': -1}, {'frame_offset': 4}, {'frame_count': 0},
                        {'frame_offset': 2, 'frame_count': 3}, {'frame_offset': True}):
            with self.assertRaises(ValueError): self.import_file(**options)
        self.mot.write_text('2,9,141,101,40,100\n')
        with self.assertRaisesRegex(ValueError, 'outside'): self.import_file(frame_count=1)

    def test_duplicate_id_per_frame_even_ignored_rows(self):
        for mark in (0, 1):
            self.mot.write_text(f'1,9,141,101,40,100,1\n1,9,11,21,20,30,{mark}\n')
            with self.assertRaisesRegex(ValueError, 'line 2: duplicate'): self.import_file()
            self.assertFalse(self.output.exists())

    def test_bounds_and_explicit_clipping_report(self):
        self.mot.write_text('1,9,0,0,400,400,1,1,1\n')
        with self.assertRaisesRegex(ValueError, 'outside image'): self.import_file()
        summary = self.import_file(clip_boxes=True)
        doc = loads(self.output.read_text())
        self.assertEqual(doc['frames'][0]['persons'][0]['box'], [0,0,320,300])
        self.assertEqual(len(summary['clipped_boxes']), 1)
        self.assertEqual(summary['clipped_boxes'][0]['original'], [-1,-1,399,399])
        for x in (-100, 500):
            self.mot.write_text(f'1,9,{x},10,10,10\n')
            with self.assertRaisesRegex(ValueError, 'no positive area'):
                import_mot(self.bundle, self.mot, self.root/f'bad-{x}.json', clip_boxes=True)

    def test_ignored_marks_and_classes_reported_and_validated(self):
        self.mot.write_text('1,9,141,101,40,100,1,1,1\n'
                            '2,9,141,101,40,100,0,1,1\n'
                            '3,12,11,21,20,30,1,7,1\n')
        summary = self.import_file()
        self.assertEqual(summary['ignored_mark_zero_rows'], 1)
        self.assertEqual(summary['ignored_non_person_rows'], 1)
        self.assertEqual(summary['imported_person_rows'], 1)
        self.mot.write_text('1,9,141,101,-40,100,0,7,1\n')
        with self.assertRaises(ValueError):
            import_mot(self.bundle, self.mot, self.root/'invalid-ignored.json')

    def test_overwrite_refusal_preserves_source_and_output(self):
        original = self.mot.read_bytes()
        self.import_file()
        before = self.output.read_bytes()
        with self.assertRaises(FileExistsError): self.import_file(human_verified=True)
        with self.assertRaises(FileExistsError): import_mot(self.bundle, self.mot, self.mot)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.mot.read_bytes(), original)

    def test_cli_draft_stays_blocked_even_with_named_authors(self):
        result = self.cli('import-mot', self.bundle, self.mot, '--output', self.output,
                          '--annotator', 'TEST-ONLY', '--reviewer', 'TEST-ONLY')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(loads(result.stdout)['status'], 'draft')
        result = self.cli('validate-annotations', self.bundle, self.output)
        self.assertEqual(result.returncode, 2)
        report = self.root/'blocked.json'
        result = self.cli('evaluate', self.bundle, '--annotations', self.output, '--output', report, '--trackers', 'all')
        self.assertEqual(result.returncode, 0, result.stderr)  # Historical blocked-report exit behavior.
        data = loads(report.read_text())
        self.assertTrue(data['real_accuracy_status'].startswith('BLOCKED'))
        for method in data['methods'].values():
            self.assertIsNone(method['metrics'])
            self.assertIsNone(method['selected_target_continuity'])

    def test_cli_human_verified_requires_provenance_and_passes_contract(self):
        for authors in ([], ['--annotator', 'TEST-ONLY'], ['--reviewer', 'TEST-ONLY']):
            result = self.cli('import-mot', self.bundle, self.mot, '--output', self.output,
                              '--human-verified', *authors)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.output.exists())
        result = self.cli('import-mot', self.bundle, self.mot, '--output', self.output,
                          '--human-verified', '--annotator', 'TEST-ONLY', '--reviewer', 'TEST-ONLY',
                          '--target-person-id', 9)
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = loads(self.output.read_text())
        self.assertEqual(doc['status'], 'reviewed')
        self.assertTrue(all(f['reviewed'] for f in doc['frames']))
        validate_annotations(doc, self.manifest, self.records)
        self.assertEqual(self.cli('validate-annotations', self.bundle, self.output).returncode, 0)
        before = self.output.read_bytes()
        self.assertEqual(self.cli('import-mot', self.bundle, self.mot, '--output', self.output).returncode, 2)
        self.assertEqual(self.output.read_bytes(), before)

    def test_unknown_target_refused_and_no_selected_target_is_null(self):
        with self.assertRaisesRegex(ValueError, 'unknown imported target'): self.import_file(target_person_id=99)
        self.import_file(human_verified=True, annotator='TEST-ONLY', reviewer='TEST-ONLY')
        report = compare_dataset(self.bundle, loads(self.output.read_text()), trackers='kalman_iou')
        self.assertIsNone(report['methods']['kalman_iou']['selected_target_continuity'])

    def test_three_tracker_cli_comparison_on_same_stored_detections(self):
        # Two people; target is lost once, then jumps beyond each association gate.
        records = copy.deepcopy(self.records)
        lines = []
        for i, record in enumerate(records):
            x = 10 if i < 2 else 250
            target = {'class_id': 0, 'box': [x,100,x+40,200], 'objectness': .9}
            other = {'class_id': 0, 'box': [110,0,130,20], 'objectness': .9}
            record['observations']['value']['detections'] = [other] if i == 1 else [target, other]
            lines += [f'{i+1},9,{x+1},101,40,100,1,1,1', f'{i+1},12,111,1,20,20,1,1,1']
        self.rewrite(records)
        self.mot.write_text('\n'.join(lines)+'\n')
        self.import_file(human_verified=True, annotator='TEST-ONLY', reviewer='TEST-ONLY', target_person_id=9)
        report_path = self.root/'comparison.json'
        result = self.cli('evaluate', self.bundle, '--annotations', self.output,
                          '--trackers', 'all', '--output', report_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = loads(report_path.read_text())
        self.assertEqual(set(report['methods']), {'greedy_iou', 'hungarian', 'kalman_iou'})
        self.assertEqual({m['input_sha256'] for m in report['methods'].values()}, {report['detector_input_sha256']})
        for method in report['methods'].values():
            metrics = method['metrics']
            self.assertEqual(metrics['ID_switches'], 1)
            self.assertEqual(metrics['IDFN'], 2)
            self.assertEqual(metrics['detection_matches'], 7)
            continuity = method['selected_target_continuity']
            self.assertEqual(continuity['same_initial_id_frames'], 1)
            self.assertEqual(continuity['lost_frames'], 1)
            self.assertEqual(continuity['different_id_frames'], 2)
            self.assertEqual(continuity['target_absent_or_unboxed_frames'], 0)
        # No option retains historical methods and method fields.
        baseline = compare_dataset(self.bundle, loads(self.output.read_text()))
        self.assertEqual(list(baseline['methods']), ['greedy_iou', 'hungarian'])
        self.assertTrue(all(set(m) == {'input_sha256', 'tracking_ms', 'metrics', 'predictions'}
                            for m in baseline['methods'].values()))

    def test_tracker_list_validation_and_unboxed_target(self):
        for trackers in ('', 'all,greedy_iou', 'greedy_iou,greedy_iou', 'unknown'):
            with self.assertRaises(ValueError): compare_dataset(self.bundle, trackers=trackers)
        doc = self.reviewed_test_annotations()
        doc['frames'][1]['persons'][0].update(box=None, occlusion='full')
        report = compare_dataset(self.bundle, doc, trackers='kalman_iou,greedy_iou')
        self.assertEqual(list(report['methods']), ['kalman_iou', 'greedy_iou'])
        for method in report['methods'].values():
            continuity = method['selected_target_continuity']
            self.assertEqual(continuity['same_initial_id_frames'], 3)
            self.assertEqual(continuity['target_absent_or_unboxed_frames'], 1)
            self.assertEqual(continuity['lost_frames'], 0)
