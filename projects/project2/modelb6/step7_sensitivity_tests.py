"""P2.7 synthetic contracts; no video decode or model inference."""

import unittest
from pathlib import Path

import numpy as np

import step6
import step7_sensitivity as s


class SensitivityFixtures(unittest.TestCase):
    def setUp(self):
        self.image = np.ones((1, 12, 128, 256), np.float32)
        self.base = s.inputs(self.image)

    def changed(self, factor, value):
        altered = s.intervention(self.base, factor, value)
        self.assertEqual([n for n in s.INPUT_NAMES if s.hashes(self.base)[n] != s.hashes(altered)[n]], [factor])

    def test_01_model_hashes_immutable_registry(self):
        self.assertEqual(step6.MODELS['final']['sha256'], '7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03')
        self.assertEqual(step6.MODELS['best']['sha256'], '97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a')

    def test_02_output_width(self):
        self.assertEqual(step6.BOUNDS[-1], 2383)

    def test_03_sample_indices(self):
        self.assertEqual(s.selected_indices(1200), [0, 299, 599, 898, 1198])
        self.assertEqual(s.selected_indices(1202), [0, 300, 600, 900, 1200])

    def test_04_static_state_resets(self):
        first = s.inputs(self.image)
        first[3][0, 0] = 8
        self.assertEqual(s.inputs(self.image)[3][0, 0], 0)

    def test_05_image_swap_only(self):
        self.changed('image', self.image + 1)

    def test_06_zero_image_only(self):
        self.changed('image', np.zeros_like(self.image))

    def test_07_traffic_only(self):
        self.changed('traffic', np.array([[1, 0]], np.float32))

    def test_08_desire_only(self):
        self.changed('desire', s.one_hot(1))

    def test_09_real_state_only(self):
        self.changed('state', np.ones((1, 512), np.float32))

    def test_10_models_separate(self):
        self.assertNotEqual(step6.MODELS['final']['file'], step6.MODELS['best']['file'])
        self.assertNotEqual(step6.MODELS['final']['sha256'], step6.MODELS['best']['sha256'])

    def test_11_domains_separate(self):
        self.assertNotEqual(step6.SOURCES['usa'], step6.SOURCES['taiwan'])
        self.assertNotEqual(s.selected_indices(s.COUNTS['usa']), s.selected_indices(s.COUNTS['taiwan']))

    def test_12_section_boundaries(self):
        a = np.zeros((1, 2383), np.float32)
        b = a.copy()
        b[0, 385] = 2
        m = s.output_metrics(a, b)
        self.assertEqual(m['sections']['path']['mae'], 0)
        self.assertEqual(m['sections']['left_lane']['different_values'], 1)
        self.assertEqual(m['sections']['right_lane']['mae'], 0)

    def test_13_nonfinite_output_fails(self):
        a = np.zeros((1, 2383), np.float32)
        a[0, 0] = np.nan
        with self.assertRaises(ValueError):
            s.output_metrics(a, np.zeros_like(a))

    def test_14_source_not_output(self):
        with self.assertRaises(ValueError):
            s.output_target(step6.SOURCES['usa'])

    def test_15_previous_outputs_not_target(self):
        for path in ('/output/step5/new', '/output/step6/new', '/workspace/professor/new'):
            with self.assertRaises(ValueError):
                s.output_target(path)

    def test_16_identical_intervention_fails(self):
        with self.assertRaises(ValueError):
            s.intervention(self.base, 'image', self.image)

    def test_17_wrong_shape_fails(self):
        with self.assertRaises(ValueError):
            s.intervention(self.base, 'traffic', np.zeros((2,), np.float32))

    def test_18_unrecognized_desire_fails(self):
        with self.assertRaises(ValueError):
            s.one_hot(7)

    def test_19_temporal_pair_layout(self):
        first = np.ones((6, 128, 256), np.float32)
        second = np.full_like(first, 2)
        pair = np.vstack((first, second))[None]
        self.assertEqual(pair.shape, (1, 12, 128, 256))
        self.assertTrue((pair[0, :6] == 1).all())
        self.assertTrue((pair[0, 6:] == 2).all())

    def test_20_metric_denominator_stable_at_zero(self):
        a = np.zeros((1, 4), np.float32)
        b = np.ones_like(a)
        self.assertEqual(s.metrics(a, b)['relative_to_max_baseline_mean_abs_or_1'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
