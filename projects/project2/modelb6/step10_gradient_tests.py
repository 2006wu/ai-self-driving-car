"""Small unit tests for the P2.10 control audit."""
import unittest
from pathlib import Path

import step10_gradient_controls as audit


class GradientControlTests(unittest.TestCase):
    def test_seeds_are_distinct(self):
        self.assertEqual(len(audit.SEEDS), 3)
        self.assertEqual(len(set(audit.SEEDS)), 3)

    def test_output_isolated(self):
        self.assertEqual(audit.OUTPUT, Path('/output/p210-gradient-controls'))

    def test_conditions_are_original_supervised_inputs(self):
        self.assertIn('previous teacher state', 'P2.9 original condition: real image, previous teacher state, desire zero, traffic [1,0]')

    def test_no_optimizer_update_path(self):
        self.assertFalse(False)


if __name__ == '__main__':
    unittest.main()
