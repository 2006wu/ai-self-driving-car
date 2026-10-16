"""Synthetic P2.6 contracts; no training, video edits, or model artifact writes."""

import unittest
from pathlib import Path

import numpy as np

import step6


class Step6Fixtures(unittest.TestCase):
    def setUp(self):
        self.raw = np.zeros((1, 2383), dtype=np.float32)

    def test_01_boundaries_match_training(self):
        self.assertEqual(step6.BOUNDS, tuple(step6.TARGET_BOUNDS))

    def test_02_total_width(self):
        self.assertEqual(step6.BOUNDS[-1], 2383)

    def test_03_twelve_slices(self):
        self.assertEqual(len(step6.split_output(self.raw)), 12)

    def test_04_slice_lengths(self):
        parts = step6.split_output(self.raw)
        self.assertEqual([parts[n].shape[1] for n in step6.NAMES],
                         [385, 386, 386, 58, 200, 200, 200, 8, 4, 32, 12, 512])

    def test_05_short_output_fails(self):
        with self.assertRaises(ValueError):
            step6.split_output(np.zeros((1, 2382)))

    def test_06_flat_output_fails(self):
        with self.assertRaises(ValueError):
            step6.split_output(np.zeros(2383))

    def test_07_nonfinite_output_fails(self):
        self.raw[0, 100] = np.nan
        with self.assertRaises(ValueError):
            step6.split_output(self.raw)

    def test_08_final_registry(self):
        self.assertEqual(step6.MODELS['final']['file'], 'B6.keras')
        self.assertEqual(len(step6.MODELS['final']['sha256']), 64)

    def test_09_best_registry(self):
        self.assertEqual(step6.MODELS['best']['file'], 'B6BW.hdf5')
        self.assertEqual(len(step6.MODELS['best']['sha256']), 64)

    def test_10_usa_configuration(self):
        self.assertEqual((step6.CONFIGS['usa']['start_point'], step6.CONFIGS['usa']['right_offset_m']), (4, -0.5))

    def test_11_taiwan_configuration(self):
        self.assertEqual((step6.CONFIGS['taiwan']['start_point'], step6.CONFIGS['taiwan']['right_offset_m']), (3, -0.7))

    def test_12_domain_camera_distinct(self):
        self.assertNotEqual(step6.CONFIGS['usa']['vanishing_x'], step6.CONFIGS['taiwan']['vanishing_x'])

    def test_13_model_directories_distinct(self):
        self.assertNotEqual(step6.output_dir('usa', 'final'), step6.output_dir('usa', 'best'))

    def test_14_domain_directories_distinct(self):
        self.assertNotEqual(step6.output_dir('usa', 'final'), step6.output_dir('taiwan', 'final'))

    def test_15_smoke_separate(self):
        self.assertNotEqual(step6.output_dir('usa', 'final', True), step6.output_dir('usa', 'final'))

    def test_16_source_output_rejected(self):
        with self.assertRaises(ValueError):
            step6.validated_output_dir(step6.SOURCES['usa'])

    def test_17_professor_output_rejected(self):
        with self.assertRaises(ValueError):
            step6.validated_output_dir(step6.PROFESSOR / 'output')

    def test_18_state_zero(self):
        self.assertEqual(step6.zero_state().shape, (1, 512))
        self.assertTrue((step6.zero_state() == 0).all())

    def test_19_state_advances(self):
        parts = step6.split_output(self.raw)
        parts['state'][0, 0] = 5
        self.assertEqual(step6.next_state(parts)[0, 0], 5)

    def test_20_state_runs_independent(self):
        first = step6.zero_state()
        first[0, 0] = 7
        self.assertEqual(step6.zero_state()[0, 0], 0)

    def test_21_parser_structure(self):
        parsed = step6.parse_parts(step6.split_output(self.raw), 'usa')
        self.assertEqual(parsed['path'].shape, (1, 192))
        self.assertEqual(parsed['lll'].shape, (1, 192))
        self.assertEqual(parsed['rll'].shape, (1, 192))

    def test_22_slide_offsets_adapt_parser(self):
        parts = step6.split_output(self.raw)
        usa = step6.parse_parts(parts, 'usa')
        taiwan = step6.parse_parts(parts, 'taiwan')
        self.assertAlmostEqual(float(usa['path'][0, 0]), 0.1, places=5)
        self.assertAlmostEqual(float(usa['lll'][0, 0]), 1.9, places=5)
        self.assertAlmostEqual(float(usa['rll'][0, 0]), -2.3, places=5)
        self.assertAlmostEqual(float(taiwan['path'][0, 0]), 0.0, places=5)
        self.assertAlmostEqual(float(taiwan['lll'][0, 0]), 1.6, places=5)
        self.assertAlmostEqual(float(taiwan['rll'][0, 0]), -2.5, places=5)

    def test_23_parser_lead(self):
        parsed = step6.parse_parts(step6.split_output(self.raw), 'usa')
        self.assertEqual(parsed['lead_xyva'].shape, (1, 4))
        self.assertEqual(parsed['lead_prob'].shape, (1,))

    def test_24_parser_longitudinal_meta_pose(self):
        parsed = step6.parse_parts(step6.split_output(self.raw), 'usa')
        self.assertEqual(parsed['long_x'].shape, (1, 200))
        self.assertEqual(parsed['meta'].shape, (1, 4))
        self.assertEqual(parsed['desire'].shape, (1, 32))
        self.assertEqual(parsed['trans'].shape, (1, 3))

    def test_25_projection_lengths(self):
        for domain, config in step6.CONFIGS.items():
            x, y = step6.project(np.zeros(192), domain)
            self.assertEqual(len(x), 192 - config['start_point'])
            self.assertEqual(len(y), 192 - config['start_point'])

    def test_26_usa_projection_matches_professor_helper(self):
        from lanes_image_space import transform_points
        line = np.linspace(-1, 1, 192)
        x, y = step6.project(line, 'usa')
        professor_x, professor_y = transform_points(np.arange(1, 193), line)
        np.testing.assert_allclose(x, professor_x)
        np.testing.assert_allclose(y, professor_y)

    def test_27_bad_projection_input_fails(self):
        with self.assertRaises(ValueError):
            step6.project(np.zeros(191), 'usa')

    def test_28_descriptive_metrics_labeled(self):
        row = {'path': [0] * 192, 'left_lane': [2] * 192,
               'right_lane': [-2] * 192, 'lead_xyva': [10, 0, 0, 0],
               'lead_prob': 0.5, 'state_l2': 0}
        result = step6.summarize([row, row])
        self.assertEqual(result['category'], 'DESCRIPTIVE')
        self.assertIsNone(result['ground_truth_accuracy'])

    def test_29_traffic_is_professor_step6_zero(self):
        self.assertEqual(step6.CONFIGS['usa']['traffic'], [0.0, 0.0])
        self.assertEqual(step6.CONFIGS['taiwan']['traffic'], [0.0, 0.0])

    def test_30_source_paths_are_not_outputs(self):
        for source in step6.SOURCES.values():
            self.assertFalse(str(Path(source)).startswith(str(step6.OUTPUT)))

    def test_31_large_finite_softplus_stays_finite(self):
        raw = self.raw.copy()
        raw[0, 192] = 1000.0  # path standard deviation logit
        parsed = step6.parse_parts(step6.split_output(raw), 'usa')
        self.assertTrue(all(np.isfinite(v).all() for v in parsed.values()))
        self.assertAlmostEqual(float(parsed['path_stds'][0, 0]), 1000.0, places=3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
