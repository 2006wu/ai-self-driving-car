"""Fast draft-figure checks. Synthetic settings only; no hardware acceptance."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

from p3.research.controllers import RuleBasedController
from p3.research.pid_controller import PIDFollowController
from p3.research.report3_figures import (DEFAULT_EVIDENCE, DRAFT_RELATIVE, REPO_ROOT, Settings,
    build_draft, cell, main, output_directory, parse_stream_stop_latency, parse_unittest_text,
    simulate_series, summarize_evidence)
from p3.research.tracker_benchmark import METHODS


def small_settings(evidence):
    return Settings(tracker_seed=2026, pid_steps=5, pid_seed=0,
                    pid_scenarios=('straight_walk', 'too_close'), bc_episodes=8,
                    bc_dataset_steps=4, bc_dataset_seed=0, bc_seed=0, bc_eval_steps=5,
                    bc_scenarios=('straight_walk', 'turn'), evidence_dir=Path(evidence))


class Report3ParseTests(unittest.TestCase):
    def test_cells_and_output_path(self):
        self.assertEqual(cell(None), 'null')
        self.assertEqual(cell(True), 'true')
        self.assertEqual(cell(False), 'false')
        root = Path('/tmp/report3-repo')
        self.assertEqual(output_directory(None, True, root), root/DRAFT_RELATIVE)
        with self.assertRaisesRegex(ValueError, 'only one'):
            output_directory(Path('out'), True, root)
        with self.assertRaisesRegex(ValueError, '--output'):
            output_directory(None, False, root)
        self.assertFalse((REPO_ROOT/DRAFT_RELATIVE).exists())

    def test_unittest_and_stream_parsers(self):
        text = 'Ran 1 test in 0.2s\n\nOK\n\nRan 3 tests in 1.25s\n\nFAILED (failures=1, errors=2, skipped=4)\n'
        rows = parse_unittest_text(text)
        self.assertEqual(rows[0]['tests'], 1)
        self.assertEqual(rows[0]['elapsed_s'], '0.2')
        self.assertEqual(rows[0]['status'], 'OK')
        self.assertEqual(rows[1]['elapsed_s'], '1.25')
        self.assertEqual((rows[1]['failures'], rows[1]['errors'], rows[1]['skipped']), (1, 2, 4))
        self.assertEqual(parse_unittest_text('mean_inference_ms 12\n') , [])
        latency = parse_stream_stop_latency('noise mean_inference_ms: 48\nstream_stop_latency_ms: 12.5\n')
        self.assertEqual(latency, [{'line': 2, 'key': 'stream_stop_latency_ms', 'raw': '12.5', 'unit': 'ms'}])
        phrase = parse_stream_stop_latency('stream stop-latency: 3\n')
        self.assertEqual(phrase[0]['unit'], 'NOT AVAILABLE')
        self.assertEqual(phrase[0]['raw'], '3')

    def test_evidence_fixture_does_not_invent_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'tests.txt').write_text('Ran 4 tests in 0.5s\n\nOK\n')
            (root/'latency.txt').write_text('mean_inference_ms: 40\nstream_stop_latency_s = 0.02\n')
            (root/'status.md').write_text(
                '| Physical C2C | **NOT TESTED** | deferred |\n'
                '| Safety handling software | **PASS** | not physical safety |\n')
            summary = summarize_evidence(root)
            self.assertEqual(summary['test_counts'][0]['tests'], 4)
            self.assertEqual(summary['test_counts'][0]['elapsed_s'], '0.5')
            self.assertEqual(summary['stream_stop_latency'][0]['raw'], '0.02')
            self.assertEqual(summary['stream_stop_latency'][0]['unit'], 's')
            self.assertNotIn('40', [row['raw'] for row in summary['stream_stop_latency']])
            self.assertEqual(summary['real_hardware'], 'NOT TESTED')
            joined = '\n'.join(row['text'] for row in summary['hardware_statements'])
            self.assertIn('Physical C2C', joined)
            self.assertNotIn('Safety handling', joined)
            (root/'pass.md').write_text('physical C2C result PASS after the drive\n')
            self.assertNotEqual(summarize_evidence(root)['real_hardware'], 'NOT TESTED')
        missing = summarize_evidence(Path(folder)/'gone')
        self.assertEqual(missing['test_count_status'], 'NOT AVAILABLE')
        self.assertEqual(missing['stream_stop_latency_status'], 'NOT AVAILABLE')
        self.assertEqual(missing['real_hardware'], 'NOT TESTED')

    def test_repo_evidence_is_cited_not_invented(self):
        summary = summarize_evidence(DEFAULT_EVIDENCE)
        self.assertTrue(summary['directory_present'])
        self.assertEqual(summary['stream_stop_latency_status'], 'NOT AVAILABLE')
        self.assertEqual(summary['real_hardware'], 'NOT TESTED')
        docker = [row for row in summary['test_counts']
                  if row['source'].endswith('evidence/docker-20261021/project3-tests.txt')]
        self.assertEqual(len(docker), 1)
        self.assertEqual(docker[0]['tests'], 163)
        self.assertEqual(docker[0]['elapsed_s'], '5.333')
        self.assertEqual(docker[0]['status'], 'OK')
        for row in summary['test_counts']:
            text = (REPO_ROOT/row['source']).read_text(encoding='utf-8', errors='replace')
            noun = 'test' if row['tests'] == 1 else 'tests'
            self.assertIn(f"Ran {row['tests']} {noun} in {row['elapsed_s']}s", text)


class Report3DraftTests(unittest.TestCase):
    def test_trajectory_matches_simulator_distance(self):
        for name, factory in (('rule', RuleBasedController), ('pid', PIDFollowController)):
            metrics, series = simulate_series(factory(), 'straight_walk', 8, 0)
            self.assertEqual(len(series), 8)
            self.assertEqual(metrics['steps'], 8)
            self.assertEqual(series[0]['robot_x_m'], 0.)
            self.assertIn('safety_stop_steps', metrics)

    def test_draft_is_deterministic_and_labeled(self):
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder)/'evidence'
            evidence.mkdir()
            (evidence/'suite.txt').write_text('Ran 2 tests in 0.1s\n\nOK (skipped=1)\n')
            (evidence/'notes.md').write_text('Webcam live detection is BLOCKED pending hardware.\n')
            settings = small_settings(evidence)
            first, second = build_draft(settings), build_draft(settings)
            self.assertEqual(first.keys(), second.keys())
            for name in first:
                self.assertEqual(first[name], second[name], name)
            summary = first['summary.md'].decode()
            self.assertIn('Real hardware', summary)
            self.assertIn('**NOT TESTED**', summary)
            self.assertIn('synthetic', summary.lower())
            self.assertIn('NOT AVAILABLE', first['evidence/stream_stop_latency.md'].decode())
            self.assertNotIn('reports/project3-report3-draft', summary.split('Reproduction')[0])
            listed = set()
            for line in summary.splitlines():
                if line.startswith('| `'):
                    listed.add(line.split('`')[1])
            self.assertEqual(listed, set(first))
            self.assertTrue(first['tracker/id_switches.png'].startswith(b'\x89PNG\r\n\x1a\n'))
            tracker = first['tracker/comparison.csv'].decode().splitlines()
            self.assertEqual(len(tracker), 1+5*len(METHODS))
            self.assertIn('synthetic_ground_truth', tracker[1])
            pid = first['pid/metrics.csv'].decode().splitlines()
            self.assertEqual(pid[0].split(','), ['scenario', 'controller', 'centering_rms', 'distance_rms_m',
                'distance_overshoot_m', 'lateral_overshoot_m', 'settling_time_s', 'safety_stop_steps',
                'safety_pass', 'min_distance_m', 'steps', 'seed'])
            self.assertEqual(len(pid), 1+4)
            for scenario in settings.pid_scenarios:
                self.assertIn(f'pid/trajectories/{scenario}.png', first)
            bc_lines = first['bc/closed_loop.csv'].decode().splitlines()
            body = '\n'.join(bc_lines)
            for name in ('pid', 'ridge', 'mlp', 'rule'):
                self.assertIn(name, body)
            self.assertIn('nominal', body)
            self.assertIn('held_out_perturbation', body)
            run = json.loads(first['run.json'].decode())
            self.assertEqual(run['schema'], 'p3_report3_figures/1.0')
            self.assertEqual(run['real_hardware'], 'NOT TESTED')
            self.assertEqual(run['stream_stop_latency'], 'NOT AVAILABLE')
            self.assertEqual(len(run['bc_training_manifest_sha256']), 64)
            self.assertIn('p3.research.tracker_benchmark', summary)
            self.assertIn('p3.research.pid_sim', summary)
            self.assertIn('p3.research.bc_baseline', summary)
            self.assertIn('control_dataset build-sim', summary)
            self.assertFalse((REPO_ROOT/DRAFT_RELATIVE).exists())

    def test_cli_refuses_overwrite_and_requires_a_new_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            existing = root/'already'
            existing.mkdir()
            (existing/'keep.txt').write_text('same')
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    main(['--output', str(existing), '--pid-steps', '5', '--bc-episodes', '8',
                          '--bc-dataset-steps', '4', '--bc-eval-steps', '5',
                          '--pid-scenarios', 'straight_walk', '--bc-scenarios', 'straight_walk,turn',
                          '--evidence', str(root)])
            self.assertIn('already exists', err.getvalue())
            self.assertEqual((existing/'keep.txt').read_text(), 'same')
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    main([])
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    main(['--draft', '--output', str(root/'other')])
            output = root/'draft'
            evidence = root/'evidence'
            evidence.mkdir()
            (evidence/'suite.txt').write_text('Ran 2 tests in 0.1s\n\nOK\n')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--output', str(output), '--pid-steps', '4', '--pid-seed', '0',
                                       '--pid-scenarios', 'straight_walk', '--bc-episodes', '8',
                                       '--bc-dataset-steps', '4', '--bc-dataset-seed', '0', '--bc-seed', '0',
                                       '--bc-eval-steps', '4', '--bc-scenarios', 'straight_walk,turn',
                                       '--tracker-seed', '2026', '--evidence', str(evidence)]), 0)
            self.assertTrue((output/'summary.md').is_file())
            before = (output/'summary.md').read_bytes()
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    main(['--output', str(output), '--evidence', str(evidence)])
            self.assertIn('already exists', err.getvalue())
            self.assertEqual((output/'summary.md').read_bytes(), before)
            self.assertFalse((REPO_ROOT/DRAFT_RELATIVE).exists())


if __name__ == '__main__':
    unittest.main()
