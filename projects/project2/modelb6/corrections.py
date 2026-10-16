"""Student-owned ModelB6 data and checkpoint corrections.

This module imports professor constants but never edits professor files. It does
not start a server, generate labels, or train merely by being imported.
"""

from pathlib import Path
import shutil
import tempfile

import h5py
import numpy as np
from tensorflow.keras.callbacks import ModelCheckpoint

import datagenB6 as professor_data


ORIGINAL_ROOT = Path("/data/dataB6")
DERIVED_ROOT = Path("/derived/dataB6")
OUTPUT_ROOT = Path("/output")
TARGET_BOUNDS = (0, 385, 771, 1157, 1215, 1415, 1615, 1815,
                 1823, 1827, 1859, 1871, 2383)


def _inside(path, root):
    """Resolve an existing path and require it to remain beneath root."""
    resolved = Path(path).resolve(strict=True)
    resolved.relative_to(Path(root).resolve(strict=True))
    return resolved


def derived_teacher_path(yuv_file, original_root=ORIGINAL_ROOT, derived_root=DERIVED_ROOT):
    """Preserve the original sequence directory under the derived data root."""
    original_root = Path(original_root).resolve(strict=True)
    derived_root = Path(derived_root).resolve()
    yuv_file = _inside(yuv_file, original_root)
    relative = yuv_file.relative_to(original_root)
    if yuv_file.name != "yuv.h5" or len(relative.parts) < 2:
        raise ValueError("expected a sequence yuv.h5 below the original data root")
    try:
        derived_root.relative_to(original_root)
    except ValueError:
        pass
    else:
        raise ValueError("derived data root must be outside original data")
    return derived_root / relative.parent / "outSC.h5"


def generate_derived_teacher(yuv_file, generator, original_root=ORIGINAL_ROOT,
                             derived_root=DERIVED_ROOT, frame_limit=None):
    """Run a supplied label generator against a tiny derived HDF5 link.

    For later Step 5 use, generator may call professor_data.oSC_Gen(link, teacher).
    The professor function then writes into the staging directory under /derived.
    P2.2 fixtures supply a fake generator and never run teacher inference.
    """
    yuv_file = _inside(yuv_file, original_root)
    result = derived_teacher_path(yuv_file, original_root, derived_root)
    result.parent.mkdir(parents=True, exist_ok=True)
    if result.exists():
        raise FileExistsError(f"derived teacher output already exists: {result}")
    stage = Path(tempfile.mkdtemp(prefix=".outSC-stage-", dir=result.parent))
    try:
        stage_yuv = stage / "yuv.h5"
        with h5py.File(yuv_file, "r") as source:
            source_frames = source["X"]
            frame_count = len(source_frames) if frame_limit is None else frame_limit
            if frame_count < 2 or frame_count > len(source_frames):
                raise ValueError("frame limit must select at least two available frames")
            with h5py.File(stage_yuv, "w") as link_file:
                if frame_limit is None:
                    link_file["X"] = h5py.ExternalLink(str(yuv_file), "/X")
                else:
                    link_file.create_dataset("X", data=source_frames[:frame_count])
        generator(str(stage_yuv))
        stage_output = stage / "outSC.h5"
        with h5py.File(stage_output, "r") as output:
            if "X" not in output:
                raise ValueError("generated teacher file must contain X")
            if output["X"].shape != (frame_count - 1, 2383):
                raise ValueError("generated teacher output has the wrong shape")
        stage_output.replace(result)
        return result
    finally:
        shutil.rmtree(stage)


def corrected_datagen(camera_files, steps, original_root=ORIGINAL_ROOT,
                      derived_root=DERIVED_ROOT, frame_limit=None):
    """Yield professor-compatible arrays with sequence and row alignment fixed.

    `steps` is retained for the server-facing signature; the baseline generator
    also cycles over all sequence batches continuously rather than stopping at it.
    Missing derived labels fail clearly and are never made in original data.
    """
    del steps
    if not camera_files:
        raise ValueError("camera_files is empty")
    batch_size = professor_data.BATCH_SIZE
    trim_imgs = professor_data.TrimImgs
    if batch_size <= 0:
        raise ValueError("invalid professor batch size")
    if trim_imgs != 0 and trim_imgs <= batch_size + 1:
        raise ValueError("TrimImgs is too small for the professor batch size")

    while True:
        for camera_file in camera_files:
            # Recurrent context belongs to one recording, not the next one.
            state = np.zeros(512, dtype="float32")
            camera_file = _inside(camera_file, original_root)
            teacher_file = derived_teacher_path(camera_file, original_root, derived_root)
            if not teacher_file.is_file():
                raise FileNotFoundError(f"missing derived teacher output: {teacher_file}")
            with h5py.File(camera_file, "r") as yuv, h5py.File(teacher_file, "r") as teacher:
                frames, rows = yuv["X"], teacher["X"]
                if frames.shape[1:] != (6, 128, 256):
                    raise ValueError(f"unexpected yuv frame shape: {frames.shape}")
                frame_count = len(frames) if frame_limit is None else frame_limit
                if frame_count < 2 or frame_count > len(frames):
                    raise ValueError("frame limit must select at least two available frames")
                if rows.shape != (frame_count - 1, 2383):
                    raise ValueError(f"teacher rows do not match frames: {teacher_file}")
                last_idx = frame_count - 2 - batch_size
                if frame_limit is not None and last_idx <= 0:
                    raise ValueError("smoke frame limit cannot yield a professor batch")
                if last_idx < 0:
                    continue
                t0 = 0
                if trim_imgs:
                    if frame_count <= trim_imgs:
                        raise ValueError("sequence is too short for TrimImgs")
                    t0 = int(np.random.choice(np.arange(frame_count - trim_imgs), size=1)[0])
                    last_idx = trim_imgs - 2 - batch_size
                for i in range(0, last_idx, batch_size):
                    images = np.zeros((batch_size, 12, 128, 256), dtype="float32")
                    desire = np.zeros((batch_size, 8), dtype="float32")
                    traffic = np.zeros((batch_size, 2), dtype="float32")
                    traffic[:, 0] = 1.0
                    states = np.zeros((batch_size, 512), dtype="float32")
                    targets = [np.zeros((batch_size, right - left), dtype="float32")
                               for left, right in zip(TARGET_BOUNDS[:-1], TARGET_BOUNDS[1:])]
                    for bcount in range(batch_size):
                        row = bcount + i + t0
                        images[bcount] = np.vstack((frames[row], frames[row + 1]))
                        teacher_row = rows[row]
                        states[bcount] = state
                        state = teacher_row[1871:2383].astype("float32")
                        for target, left, right in zip(targets, TARGET_BOUNDS[:-1], TARGET_BOUNDS[1:]):
                            target[bcount] = teacher_row[left:right]
                    yield (images, desire, traffic, states, *targets)


def initialize_model(model, resume_checkpoint=None, output_root=OUTPUT_ROOT):
    """Fresh starts keep initial weights; explicit resumes load an output checkpoint."""
    if resume_checkpoint is None:
        return False
    checkpoint = _inside(resume_checkpoint, output_root)
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    model.load_weights(str(checkpoint))
    return True


def validation_checkpoint(output_root=OUTPUT_ROOT):
    """Choose the best validation loss in student-owned output storage."""
    output_root = Path(output_root).resolve(strict=True)
    checkpoint = output_root / "B6BW.hdf5"
    return ModelCheckpoint(str(checkpoint), monitor="val_loss", mode="min",
                           save_best_only=True, verbose=1)
