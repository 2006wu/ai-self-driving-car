"""Small numerical contracts for the P2.8 encoder audit."""
import unittest
import numpy as np
import tensorflow as tf
import step8_encoder_audit as audit


class EncoderTests(unittest.TestCase):
    def test_stats_preserve_small_float_values(self):
        self.assertAlmostEqual(audit.stats(np.array([1e-20, -1e-20]))['rms'], 1e-20)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            audit.stats(np.array([np.nan]))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            audit.stats(np.array([]))

    def test_previous_outputs_rejected(self):
        for p in ('/output/step5/new', '/output/step6/new', '/output/p27-sensitivity/new', '/data/new'):
            with self.assertRaises(ValueError):
                audit.target(p)

    def test_elu_saturation_stat(self):
        self.assertEqual(audit.stats(np.array([-1, 0, 1]))['elu_negative_saturation_fraction'], 1 / 3)

    def test_gradient_on_known_function(self):
        x = tf.constant([2., 3.])
        with tf.GradientTape(watch_accessed_variables=False) as tape:
            tape.watch(x)
            y = tf.reduce_mean(tf.square(3 * x))
        np.testing.assert_allclose(tape.gradient(y, x).numpy(), [18, 27])


if __name__ == '__main__':
    unittest.main(verbosity=2)
