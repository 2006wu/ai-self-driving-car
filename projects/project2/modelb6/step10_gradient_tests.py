"""Small unit tests for the P2.10 control audit."""
import unittest
from pathlib import Path
from unittest.mock import patch

import step10_gradient_controls as audit


class GradientControlTests(unittest.TestCase):
    def test_seeds_are_distinct(self):
        self.assertEqual(len(audit.SEEDS), 3)
        self.assertEqual(len(set(audit.SEEDS)), 3)

    def test_output_isolated(self):
        self.assertEqual(audit.OUTPUT, Path('/output/p210-gradient-controls'))

    def test_completed_output_rejected_before_any_model_construction(self):
        with patch.object(audit.Path, 'exists', return_value=True), patch.object(audit, 'get_model') as build:
            with self.assertRaises(FileExistsError): audit.run()
            build.assert_not_called()

    def test_original_gradient_collection_rejects_disconnected_tensor(self):
        with self.assertRaises(ValueError): audit.p29.grad_stats(None)


if __name__ == '__main__':
    unittest.main()
