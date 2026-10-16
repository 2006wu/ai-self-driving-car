"""Production Step 5 data/stream fixtures; no real labels or training."""

import json
from pathlib import Path
import tempfile
import unittest

import h5py
import numpy as np

from step5 import ensure_shapes, stream_for_split
from step5_data import MARKER_NAME, prepare, validate_all, validate_one


class ProductionFixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="step5-fixtures-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = root / "source"
        self.derived = root / "derived"
        self.teacher = root / "fake-teacher.keras"
        self.teacher.write_bytes(b"fixture teacher identity")
        self.names = ["seq-train-a", "seq-train-b", "seq-validation"]
        self.config = {"train_sequences": self.names[:2], "validation_sequences": self.names[2:],
                       "batch_size": 2, "target_width": 2383}
        for ident, name in enumerate(self.names, 1):
            directory = self.source / name
            directory.mkdir(parents=True)
            with h5py.File(directory / "yuv.h5", "w") as file:
                frames = file.create_dataset("X", (8, 6, 128, 256), dtype="float32")
                for row in range(8):
                    frames[row] = ident * 100 + row
        self.generate()

    def fake_generator(self, staged_yuv, unused_teacher):
        with h5py.File(staged_yuv, "r") as source:
            values = source["X"][:, 0, 0, 0]
        with h5py.File(Path(staged_yuv).with_name("outSC.h5"), "w") as output:
            labels = output.create_dataset("X", (len(values) - 1, 2383), dtype="float32")
            for row, value in enumerate(values[:-1]):
                labels[row] = value

    def generate(self, force=False):
        return prepare(self.config, force=force, source_root=self.source,
                       derived_root=self.derived, teacher_path=self.teacher,
                       generator=self.fake_generator)

    def marker(self, name):
        return self.derived / name / MARKER_NAME

    def test_a_explicit_multi_sequence_order_and_boundary(self):
        names, stream = stream_for_split("train", self.config, self.source, self.derived)
        self.assertEqual(names, self.names[:2])
        first = next(stream)
        second = next(stream)
        boundary = next(stream)
        self.assertEqual(float(first[0][0, 0, 0, 0]), 100)
        self.assertEqual(float(second[0][0, 0, 0, 0]), 102)
        self.assertEqual(float(boundary[0][0, 0, 0, 0]), 200)
        self.assertEqual(float(np.hstack(boundary[4:])[0, 0]), 200)
        np.testing.assert_array_equal(boundary[3][0], np.zeros(512, np.float32))

    def test_b_train_excludes_validation(self):
        _, stream = stream_for_split("train", self.config, self.source, self.derived)
        self.assertTrue(all(float(next(stream)[0][0, 0, 0, 0]) < 300 for _ in range(8)))

    def test_c_validation_excludes_train(self):
        names, stream = stream_for_split("validation", self.config, self.source, self.derived)
        self.assertEqual(names, self.names[2:])
        self.assertEqual(float(next(stream)[0][0, 0, 0, 0]), 300)

    def test_d_missing_marker_rejected(self):
        self.marker(self.names[0]).unlink()
        with self.assertRaises(FileNotFoundError):
            stream_for_split("train", self.config, self.source, self.derived)

    def test_e_wrong_hash_rejected(self):
        marker = self.marker(self.names[0])
        value = json.loads(marker.read_text())
        value["label_sha256"] = "0" * 64
        marker.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            validate_one(self.names[0], self.source, self.derived)

    def test_f_wrong_row_count_rejected(self):
        path = self.derived / self.names[0] / "outSC.h5"
        with h5py.File(path, "a") as file:
            del file["X"]
            file.create_dataset("X", (6, 2383), dtype="float32")
        with self.assertRaises(ValueError):
            validate_one(self.names[0], self.source, self.derived)

    def test_g_wrong_target_width_rejected(self):
        path = self.derived / self.names[0] / "outSC.h5"
        with h5py.File(path, "a") as file:
            del file["X"]
            file.create_dataset("X", (7, 2382), dtype="float32")
        with self.assertRaises(ValueError):
            validate_one(self.names[0], self.source, self.derived)

    def test_h_incomplete_stage_rejected(self):
        stage = self.derived / self.names[0] / ".outSC-stage-interrupted"
        stage.mkdir()
        (stage / "outSC.h5").write_bytes(b"partial")
        with self.assertRaises(ValueError):
            validate_one(self.names[0], self.source, self.derived)

    def test_i_sample_alignment_within_each_sequence(self):
        _, stream = stream_for_split("train", self.config, self.source, self.derived)
        for expected in (100, 102, 200, 202):
            batch = next(stream)
            targets = ensure_shapes(batch)
            self.assertEqual(float(batch[0][0, 0, 0, 0]), expected)
            self.assertEqual(float(batch[0][0, 6, 0, 0]), expected + 1)
            self.assertEqual(float(targets[0, 0]), expected)
            self.assertEqual(float(targets[1, 0]), expected + 1)

    def test_j_source_side_labels_are_ignored(self):
        with h5py.File(self.source / self.names[0] / "outSC.h5", "w") as file:
            file.create_dataset("X", data=np.full((7, 2383), 999, np.float32))
        _, stream = stream_for_split("train", self.config, self.source, self.derived)
        self.assertEqual(float(ensure_shapes(next(stream))[0, 0]), 100)

    def test_k_server_output_contract(self):
        for split in ("train", "validation"):
            _, stream = stream_for_split(split, self.config, self.source, self.derived)
            batch = next(stream)
            self.assertEqual([item.shape for item in batch[:4]],
                             [(2, 12, 128, 256), (2, 8), (2, 2), (2, 512)])
            self.assertEqual(ensure_shapes(batch).shape, (2, 2383))

    def test_l_valid_labels_reused_on_restart(self):
        before = self.marker(self.names[0]).read_bytes()
        result = self.generate()
        self.assertEqual([item["action"] for item in result], ["reused"] * 3)
        self.assertEqual(before, self.marker(self.names[0]).read_bytes())
        self.assertEqual(len(validate_all(self.config, self.source, self.derived)), 3)

    def test_m_invalid_final_requires_force_and_is_quarantined(self):
        marker = self.marker(self.names[0])
        marker.write_text('{"status":"incomplete"}')
        with self.assertRaises(RuntimeError):
            self.generate()
        result = self.generate(force=True)
        self.assertEqual(result[0]["action"], "generated")
        self.assertEqual(len(list((self.derived / self.names[0]).glob("quarantine-*"))), 1)
        validate_one(self.names[0], self.source, self.derived)


if __name__ == "__main__":
    unittest.main(verbosity=2)
