"""Tiny P2.2 fixtures; run only in the isolated modelb6 container."""

import hashlib
from pathlib import Path
import tempfile
import unittest

import h5py
import numpy as np
import tensorflow as tf

from corrections import (corrected_datagen, derived_teacher_path,
                         generate_derived_teacher, initialize_model,
                         validation_checkpoint)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CorrectionFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="p2-2-fixtures-", dir="/tmp")
        cls.root = Path(cls.temp.name)
        cls.original = cls.root / "original" / "dataB6"
        cls.derived = cls.root / "derived" / "dataB6"
        cls.output = cls.root / "output"
        cls.original.mkdir(parents=True)
        cls.derived.mkdir(parents=True)
        cls.output.mkdir()
        cls.files = []
        cls.hashes = {}
        for sequence, base in (("sequence-A", 100), ("sequence-B", 200)):
            folder = cls.original / sequence
            folder.mkdir()
            yuv_file = folder / "yuv.h5"
            frames = np.zeros((8, 6, 128, 256), dtype="float32")
            for row in range(8):
                frames[row].fill(base + row)
            with h5py.File(yuv_file, "w") as stream:
                stream.create_dataset("X", data=frames)
            cls.files.append(yuv_file)
            cls.hashes[yuv_file] = digest(yuv_file)

        def fake_teacher(stage_yuv):
            stage_yuv = Path(stage_yuv)
            with h5py.File(stage_yuv, "r") as source:
                identifiers = source["X"][:, 0, 0, 0]
            labels = np.repeat(identifiers[:-1, None], 2383, axis=1)
            with h5py.File(stage_yuv.with_name("outSC.h5"), "w") as output:
                output.create_dataset("X", data=labels)

        for yuv_file in cls.files:
            generate_derived_teacher(yuv_file, fake_teacher, cls.original, cls.derived)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_1_fresh_start_skips_missing_checkpoint(self):
        class ModelSpy:
            def load_weights(self, path):
                raise AssertionError(f"fresh start tried to load {path}")
        self.assertFalse((self.output / "B6BW.hdf5").exists())
        self.assertFalse(initialize_model(ModelSpy(), output_root=self.output))

    def test_2_resume_loads_supplied_checkpoint(self):
        model = tf.keras.Sequential([tf.keras.layers.Dense(1, input_shape=(1,))])
        original_weights = [np.full_like(weight, 3.0) for weight in model.get_weights()]
        model.set_weights(original_weights)
        checkpoint = self.output / "resume-fixture.hdf5"
        model.save_weights(str(checkpoint))
        model.set_weights([np.zeros_like(weight) for weight in original_weights])
        self.assertTrue(initialize_model(model, checkpoint, self.output))
        for actual, expected in zip(model.get_weights(), original_weights):
            np.testing.assert_array_equal(actual, expected)

    def test_3_sequences_use_their_own_teacher_files(self):
        first = derived_teacher_path(self.files[0], self.original, self.derived)
        second = derived_teacher_path(self.files[1], self.original, self.derived)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent.name, "sequence-A")
        self.assertEqual(second.parent.name, "sequence-B")
        generator = corrected_datagen(self.files, steps=1,
                                      original_root=self.original, derived_root=self.derived)
        sequence_a = next(generator)
        next(generator)  # first sequence, second batch
        sequence_b = next(generator)
        self.assertEqual(float(sequence_a[0][0, 0, 0, 0]), 100.0)
        self.assertEqual(float(sequence_a[4][0, 0]), 100.0)
        self.assertEqual(float(sequence_b[0][0, 0, 0, 0]), 200.0)
        self.assertEqual(float(sequence_b[4][0, 0]), 200.0)
        # The professor's retained oSCfile points at sequence B for sequence A.
        self.assertNotEqual(float(sequence_a[4][0, 0]), 200.0)

    def test_4_sample_n_uses_teacher_row_n(self):
        generator = corrected_datagen([self.files[0]], steps=1,
                                      original_root=self.original, derived_root=self.derived)
        first = next(generator)
        self.assertEqual([float(value) for value in first[4][:, 0]], [100.0, 101.0])
        second = next(generator)
        image_ids = [float(value) for value in second[0][:, 0, 0, 0]]
        teacher_ids = [float(value) for value in second[4][:, 0]]
        self.assertEqual(image_ids, [102.0, 103.0])
        self.assertEqual(teacher_ids, image_ids)
        self.assertNotEqual(teacher_ids, [100.0, 101.0])  # old oSCX[bcount]

    def test_5_best_checkpoint_uses_validation_loss(self):
        callback = validation_checkpoint(self.output)
        self.assertEqual(callback.monitor, "val_loss")
        self.assertTrue(callback.save_best_only)
        self.assertTrue(callback.monitor_op(0.5, 1.0))  # mode=min
        self.assertFalse(callback.monitor_op(1.5, 1.0))
        self.assertEqual(Path(callback.filepath), self.output / "B6BW.hdf5")
        model = tf.keras.Sequential([tf.keras.layers.Dense(1, input_shape=(1,))])
        best_weights = [np.full_like(weight, 1.0) for weight in model.get_weights()]
        model.set_weights(best_weights)
        callback.set_model(model)
        callback.on_epoch_end(0, {"val_loss": 0.5})
        self.assertTrue(Path(callback.filepath).is_file())
        model.set_weights([np.full_like(weight, 2.0) for weight in best_weights])
        callback.on_epoch_end(1, {"val_loss": 1.5})
        self.assertTrue(initialize_model(model, callback.filepath, self.output))
        for actual, expected in zip(model.get_weights(), best_weights):
            np.testing.assert_array_equal(actual, expected)

    def test_6_derived_paths_stay_outside_original_data(self):
        for yuv_file in self.files:
            teacher = derived_teacher_path(yuv_file, self.original, self.derived)
            self.assertEqual(teacher.relative_to(self.derived).parts[0], yuv_file.parent.name)
            with self.assertRaises(ValueError):
                teacher.relative_to(self.original)
            self.assertEqual(teacher.name, "outSC.h5")

    def test_7_original_inputs_are_not_written(self):
        for yuv_file, before in self.hashes.items():
            self.assertEqual(digest(yuv_file), before)
            self.assertFalse((yuv_file.parent / "outSC.h5").exists())
        original_files = sorted(path.relative_to(self.original) for path in self.original.rglob("*"))
        self.assertEqual(original_files, [Path("sequence-A"), Path("sequence-A/yuv.h5"),
                                          Path("sequence-B"), Path("sequence-B/yuv.h5")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
