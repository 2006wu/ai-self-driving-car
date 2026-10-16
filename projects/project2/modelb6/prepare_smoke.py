"""Prepare only explicitly selected real-data smoke labels under /derived."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import h5py
import numpy as np
from tensorflow.keras.models import load_model

import datagenB6 as professor_data
from corrections import corrected_datagen, derived_teacher_path, generate_derived_teacher


ORIGINAL_ROOT = Path("/data/dataB6")
DERIVED_ROOT = Path("/derived/smoke/dataB6")
TEACHER_MODEL = Path("/workspace/professor/saved_model/supercombo079.keras")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-sequence", required=True)
    parser.add_argument("--validation-sequence", required=True)
    parser.add_argument("--smoke-frames", type=int, default=5)
    args = parser.parse_args()
    if args.train_sequence == args.validation_sequence:
        raise ValueError("train and validation sequences must be distinct")
    if args.smoke_frames != 5:
        raise ValueError("this controlled P2.3 run uses exactly five frames per sequence")
    for path in (ORIGINAL_ROOT, TEACHER_MODEL.parent):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError(f"expected read-only input mount: {path}")
    if os.statvfs("/derived").f_flag & os.ST_RDONLY:
        raise RuntimeError("expected writable /derived mount")

    selections = [args.train_sequence, args.validation_sequence]
    paths = [ORIGINAL_ROOT / name / "yuv.h5" for name in selections]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        with h5py.File(path, "r") as source:
            if source["X"].shape[1:] != (6, 128, 256):
                raise ValueError(f"unexpected frame shape: {path}")
            if len(source["X"]) < args.smoke_frames:
                raise ValueError(f"insufficient frames: {path}")
    before = {str(path): file_hash(path) for path in paths}
    teacher = load_model(str(TEACHER_MODEL), compile=False)
    records = []
    for name, path in zip(selections, paths):
        target = derived_teacher_path(path, ORIGINAL_ROOT, DERIVED_ROOT)
        if target.exists():
            raise FileExistsError(f"smoke label file already exists: {target}")
        generated = generate_derived_teacher(
            path,
            lambda staged_yuv: professor_data.oSC_Gen(staged_yuv, teacher),
            ORIGINAL_ROOT,
            DERIVED_ROOT,
            frame_limit=args.smoke_frames,
        )
        with h5py.File(generated, "r") as labels:
            rows = labels["X"][:]
        if rows.shape != (args.smoke_frames - 1, 2383) or not np.isfinite(rows).all():
            raise ValueError(f"invalid teacher rows: {generated} {rows.shape}")
        stream = corrected_datagen([str(path)], steps=1, original_root=ORIGINAL_ROOT,
                                   derived_root=DERIVED_ROOT, frame_limit=args.smoke_frames)
        batch = next(stream)
        with h5py.File(path, "r") as source:
            np.testing.assert_array_equal(batch[0][0], np.vstack((source["X"][0], source["X"][1])))
            np.testing.assert_array_equal(batch[0][1], np.vstack((source["X"][1], source["X"][2])))
        np.testing.assert_array_equal(np.hstack(batch[4:])[0], rows[0])
        np.testing.assert_array_equal(np.hstack(batch[4:])[1], rows[1])
        records.append({"sequence": name, "original": str(path), "derived": str(generated),
                        "frame_count": args.smoke_frames, "teacher_shape": list(rows.shape),
                        "teacher_dtype": str(rows.dtype), "finite": True, "alignment": True})
    after = {str(path): file_hash(path) for path in paths}
    if before != after:
        raise RuntimeError("original data changed during preparation")
    print(json.dumps({"status": "PASS", "records": records, "original_sha256": after}, indent=2), flush=True)


if __name__ == "__main__":
    main()
