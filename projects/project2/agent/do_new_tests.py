"""Offline tests for the original read-only evidence-agent feature."""
import json
import tempfile
import unittest
from pathlib import Path

from evidence_agent import summarize_p2_evidence


class EvidenceAgentTests(unittest.TestCase):
    def test_summary_is_read_only_and_structured(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as directory:
            root = Path(directory)
            (root / 'summary.json').write_text(json.dumps({
                'status': 'complete', 'records': 2, 'samples': 1,
                'aggregates': {'final': {'overall': {'original': {
                    'loss': {'median': 1.0}, 'image_rms': {'median': 2e-14},
                    'state_rms': {'median': 0.2}, 'image_state_ratio': {'median': 1e-13}}}}}
            }))
            before = (root / 'summary.json').read_bytes()
            result = summarize_p2_evidence(str(root))
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(result['records'], 2)
            self.assertEqual(result['checkpoints']['final']['image_state_ratio_median'], 1e-13)
            self.assertEqual((root / 'summary.json').read_bytes(), before)

    def test_rejects_unapproved_root(self):
        with self.assertRaises(ValueError):
            summarize_p2_evidence('/etc')


if __name__ == '__main__':
    unittest.main()
