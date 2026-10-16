"""P2.9 scientific negative controls and safety contracts."""
import unittest
import numpy as np
import tensorflow as tf
import step9_gradient_audit as a


class GradientTests(unittest.TestCase):
    def test_actual_loss_weights(self):
        y = tf.zeros((1,2383)); p = tf.ones((1,2383))
        self.assertAlmostEqual(float(a.custom_loss(y,p).numpy()[0]), 1.)

    def test_actual_loss_derivative_bounds(self):
        p = tf.ones((1,2383))
        with tf.GradientTape() as tape:
            tape.watch(p)
            loss = tf.reduce_mean(a.custom_loss(tf.zeros_like(p),p))
        grad = tape.gradient(loss,p).numpy()[0]
        for i in (0,383,385,768,771,1154):
            self.assertAlmostEqual(float(grad[i]),2*(.3/384+.1/2383),places=9)
        for i in (384,769,770,1155,1871,2382):
            self.assertAlmostEqual(float(grad[i]),2*.1/2383,places=10)

    def test_multioutput_tape_captures_input_intermediate_parameter(self):
        inp = tf.keras.Input((1,))
        layer = tf.keras.layers.Dense(1,use_bias=False,kernel_initializer=tf.keras.initializers.Constant(3))
        hidden = layer(inp)
        model = tf.keras.Model(inp,[hidden*2,hidden])
        x = tf.constant([[2.]])
        before = layer.kernel.numpy().copy()
        with tf.GradientTape() as tape:
            tape.watch(x)
            output, intermediate = model(x,training=True)
            loss = tf.reduce_sum(output)
        g = tape.gradient(loss,[x,intermediate,layer.kernel])
        for actual, expected in zip(g,(6,2,4)):
            self.assertEqual(a.grad_stats(actual)['rms'],expected)
        np.testing.assert_array_equal(before,layer.kernel.numpy())

    def test_disconnected_gradient_rejected(self):
        with self.assertRaises(ValueError): a.grad_stats(None)

    def test_nonfinite_gradient_rejected(self):
        with self.assertRaises(ValueError): a.grad_stats(np.array([np.nan]))

    def test_small_gradients_preserved(self):
        self.assertLess(abs(a.grad_stats(np.array([1e-20,-1e-20]))['rms']/1e-20-1),1e-12)

    def test_group_rms_size_independent(self):
        self.assertEqual(a.grad_stats([np.ones(2),np.ones(8)])['rms'],1)

    def test_original_sample_indices_respect_training_trim(self):
        self.assertEqual(a.sample_indices(1200),[0,1,299,599,898,1195])
        self.assertEqual(a.sample_indices(1202),[0,1,300,600,900,1197])

    def test_prior_outputs_rejected(self):
        for p in ('/output/step5/a','/output/p28-encoder-audit/a','/data/new','../../data/new'):
            with self.assertRaises(ValueError): a.target(p)

    def test_state_removal_preserves_image(self):
        im=np.ones((12,2,2)); st=np.ones(512)
        x,s=a.variant(im,st,'zero_state',st*2)
        np.testing.assert_array_equal(x,im); self.assertTrue((s==0).all()); self.assertTrue((st==1).all())

    def test_image_removal_preserves_state(self):
        im=np.ones((12,2,2)); st=np.ones(512)
        x,s=a.variant(im,st,'zero_image',st*2)
        self.assertTrue((x==0).all()); np.testing.assert_array_equal(s,st)

    def test_zero_denominator_is_not_hidden(self):
        self.assertIsNone(a.ratio(1,0))


if __name__=='__main__': unittest.main(verbosity=2)
