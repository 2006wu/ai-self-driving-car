"""Offline safety and real-schema tests; never call Gemini."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evidence_agent as evidence
from agno.agent._tools import parse_tools
from model_config import DEFAULT_MODEL_ID


class EvidenceAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'p29'
        self.root.mkdir()
        self.file = self.root / 'summary.json'
        self.summary = {'status': 'complete', 'records': 144, 'samples': 18,
                        'aggregates': {role: {'overall': {'original': {
                            'loss': {'median': 1.0}, 'image_rms': {'median': 2e-14},
                            'state_rms': {'median': 0.2}, 'image_state_ratio': {'median': 1e-13}}}}
                            for role in ('final', 'best')}}
        self.file.write_text(json.dumps(self.summary))
        self.addCleanup(patch.stopall)
        patch.dict(os.environ).start()
        os.environ.pop('GEMINI_MODEL_ID', None)
        patch.object(evidence, 'ALLOWED_ROOTS', (self.root,)).start()
        patch.object(evidence, 'DEFAULT_ROOT', self.root).start()

    def test_valid_summary_is_structured_and_read_only(self):
        before = self.file.read_bytes()
        result = evidence.summarize_p2_evidence()
        self.assertEqual(set(result['checkpoints']), {'final', 'best'})
        self.assertEqual(result['records'], 144)
        self.assertEqual(result['checkpoints']['final']['image_state_ratio_median'], 1e-13)
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(list(self.root.iterdir()), [self.file])

    def test_missing_summary_fails(self):
        self.file.unlink()
        with self.assertRaises(FileNotFoundError): evidence.summarize_p2_evidence()

    def test_malformed_json_fails(self):
        self.file.write_text('{invalid')
        with self.assertRaisesRegex(ValueError, 'malformed'): evidence.summarize_p2_evidence()

    def test_unapproved_root_fails(self):
        with self.assertRaises(ValueError): evidence.summarize_p2_evidence('/etc')

    def test_incomplete_checkpoint_fails(self):
        del self.summary['aggregates']['best']
        self.file.write_text(json.dumps(self.summary))
        with self.assertRaisesRegex(ValueError, 'incomplete'): evidence.summarize_p2_evidence()

    def test_nonfinite_metrics_fail(self):
        self.summary['aggregates']['final']['overall']['original']['loss']['median'] = float('nan')
        self.file.write_text(json.dumps(self.summary))
        with self.assertRaisesRegex(ValueError, 'nonfinite'): evidence.summarize_p2_evidence()

    def test_incomplete_status_fails(self):
        self.summary['status'] = 'running'
        self.file.write_text(json.dumps(self.summary))
        with self.assertRaisesRegex(ValueError, 'completed'): evidence.summarize_p2_evidence()

    def test_summary_symlink_escape_fails(self):
        outside = self.root.parent / 'outside.json'
        outside.write_text(self.file.read_text())
        self.file.unlink()
        self.file.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'): evidence.summarize_p2_evidence()

    def test_root_symlink_escape_fails(self):
        self.file.unlink()
        self.root.rmdir()
        self.root.symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError): evidence.summarize_p2_evidence()

    def test_agent_registers_evidence_tool_without_api_call(self):
        agent = evidence.build_agent()
        self.assertEqual(agent.model.id, DEFAULT_MODEL_ID)
        self.assertIn(evidence.summarize_p2_evidence, agent.tools)
        functions = parse_tools(agent, tools=list(agent.tools), model=agent.model)
        tool = next(f for f in functions if f.name == 'summarize_p2_evidence')
        self.assertEqual(tool.entrypoint()['records'], 144)
        self.assertIn('properties', tool.parameters)

    def test_runtime_override_reaches_evidence_agent(self):
        os.environ['GEMINI_MODEL_ID'] = 'offline-evidence-test-model'
        self.assertEqual(evidence.build_agent().model.id, 'offline-evidence-test-model')


if __name__ == '__main__':
    unittest.main()
