"""Student-owned, restartable Step 5 label publication and validation."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

import h5py
import numpy as np
from tensorflow.keras.models import load_model

import datagenB6 as professor_data


SOURCE_ROOT = Path("/data/dataB6")
DERIVED_ROOT = Path("/derived/step5/dataB6")
TEACHER = Path("/workspace/professor/saved_model/supercombo079.keras")
CONFIG = Path(__file__).with_name("step5_split.json")
MARKER_NAME = "outSC.complete.json"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def split_config():
    config = json.loads(CONFIG.read_text())
    train, valid = config["train_sequences"], config["validation_sequences"]
    if (not train or not valid or len(set(train + valid)) != len(train + valid)
            or config["batch_size"] != 2 or config["target_width"] != 2383):
        raise ValueError("invalid Step 5 split/configuration")
    for name in train + valid:
        if Path(name).name != name or name in (".", ".."):
            raise ValueError(f"invalid sequence name: {name}")
    return config


def selected_sequences(config=None):
    config = config or split_config()
    return config["train_sequences"] + config["validation_sequences"]


def paths_for(name, source_root=SOURCE_ROOT, derived_root=DERIVED_ROOT):
    if Path(name).name != name or name in (".", ".."):
        raise ValueError(f"invalid sequence name: {name}")
    source = Path(source_root) / name / "yuv.h5"
    destination = Path(derived_root) / name
    return source, destination / "outSC.h5", destination / MARKER_NAME


def source_frames(path):
    with h5py.File(path, "r") as source:
        frames = source["X"]
        if frames.ndim != 4 or frames.shape[1:] != (6, 128, 256) or frames.dtype != "float32":
            raise ValueError(f"invalid source YUV dataset: {path}")
        if len(frames) < 5:
            raise ValueError(f"source too short: {path}")
        return len(frames)


def label_scan(path, expected_rows):
    with h5py.File(path, "r") as labels:
        if set(labels.keys()) != {"X"}:
            raise ValueError(f"unexpected label datasets: {path}")
        rows = labels["X"]
        if rows.shape != (expected_rows, 2383) or rows.dtype != "float32":
            raise ValueError(f"invalid label shape/dtype: {path}: {rows.shape} {rows.dtype}")
        for start in range(0, expected_rows, 128):
            if not np.isfinite(rows[start:start + 128]).all():
                raise ValueError(f"nonfinite label values: {path}, row {start}")
    return {"rows": expected_rows, "width": 2383, "dtype": "float32",
            "size_bytes": Path(path).stat().st_size, "sha256": sha256(path)}


def validate_one(name, source_root=SOURCE_ROOT, derived_root=DERIVED_ROOT,
                 teacher_hash=None, verify_source_hash=True):
    source, label, marker_file = paths_for(name, source_root, derived_root)
    stage = list(label.parent.glob(".outSC-stage-*")) if label.parent.is_dir() else []
    if stage:
        raise ValueError(f"incomplete temporary labels exist: {stage}")
    if not label.is_file() or not marker_file.is_file():
        raise FileNotFoundError(f"missing completed labels/marker for {name}")
    marker = json.loads(marker_file.read_text())
    if not isinstance(marker, dict) or marker.get("status") != "complete":
        raise ValueError(f"invalid completion marker: {marker_file}")
    frames = source_frames(source)
    actual = label_scan(label, frames - 1)
    expected = {"sequence": name, "source": str(source), "source_frames": frames,
                "expected_rows": frames - 1, "actual_rows": actual["rows"],
                "target_width": actual["width"], "dtype": actual["dtype"],
                "label_size_bytes": actual["size_bytes"], "label_sha256": actual["sha256"]}
    if teacher_hash is not None:
        expected["teacher_sha256"] = teacher_hash
    if verify_source_hash:
        expected["source_sha256"] = sha256(source)
    for key, value in expected.items():
        if marker.get(key) != value:
            raise ValueError(f"completion marker mismatch for {name}: {key}")
    return marker


def validate_all(config=None, source_root=SOURCE_ROOT, derived_root=DERIVED_ROOT,
                 spot_check=False):
    config = config or split_config()
    teacher_hash = sha256(TEACHER) if Path(source_root) == SOURCE_ROOT else None
    markers = [validate_one(name, source_root, derived_root, teacher_hash)
               for name in selected_sequences(config)]
    if spot_check:
        teacher = load_model(str(TEACHER), compile=False)
        for name in selected_sequences(config):
            source, label, _ = paths_for(name, source_root, derived_root)
            state = np.zeros((1, 512), np.float32)
            desire = np.zeros((1, 8), np.float32)
            traffic = np.array([[1., 0.]], np.float32)
            with h5py.File(source, "r") as src, h5py.File(label, "r") as lab:
                for i in (0, 1):
                    pair = np.vstack((src["X"][i], src["X"][i + 1]))[None]
                    outputs = teacher.predict([pair, desire, traffic, state], verbose=0)
                    prediction = np.hstack(outputs)[0]
                    if not np.allclose(prediction, lab["X"][i], rtol=1e-4, atol=1e-4):
                        raise ValueError(f"teacher alignment failed: {name} row {i}")
                    state = outputs[11]
    return markers


def prepare(config=None, force=False, source_root=SOURCE_ROOT, derived_root=DERIVED_ROOT,
            teacher_path=TEACHER, generator=None):
    config = config or split_config()
    teacher_hash = sha256(teacher_path)
    teacher = None
    results = []
    for name in selected_sequences(config):
        source, label, marker_file = paths_for(name, source_root, derived_root)
        frames = source_frames(source)
        label.parent.mkdir(parents=True, exist_ok=True)
        stages = list(label.parent.glob(".outSC-stage-*"))
        if label.exists() or marker_file.exists() or stages:
            try:
                marker = validate_one(name, source_root, derived_root, teacher_hash=teacher_hash)
            except (FileNotFoundError, ValueError, OSError, KeyError, TypeError) as error:
                if not force:
                    raise RuntimeError(f"suspicious derived data for {name}; use --force to quarantine") from error
                quarantine = label.parent / ("quarantine-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
                quarantine.mkdir()
                for path in [label, marker_file] + stages:
                    if path.exists():
                        shutil.move(str(path), str(quarantine / path.name))
            else:
                results.append({"sequence": name, "action": "reused", "marker": marker})
                continue
        if teacher is None:
            teacher = load_model(str(teacher_path), compile=False) if generator is None else object()
        stage = Path(tempfile.mkdtemp(prefix=".outSC-stage-", dir=label.parent))
        started = time.monotonic()
        try:
            staged_yuv = stage / "yuv.h5"
            with h5py.File(staged_yuv, "w") as link:
                link["X"] = h5py.ExternalLink(str(source), "/X")
            (generator or professor_data.oSC_Gen)(str(staged_yuv), teacher)
            staged_label = stage / "outSC.h5"
            metadata = label_scan(staged_label, frames - 1)
            marker = {"status": "complete", "sequence": name, "source": str(source),
                      "source_sha256": sha256(source), "source_frames": frames,
                      "expected_rows": frames - 1, "actual_rows": metadata["rows"],
                      "target_width": metadata["width"], "dtype": metadata["dtype"],
                      "label_size_bytes": metadata["size_bytes"], "label_sha256": metadata["sha256"],
                      "teacher_sha256": teacher_hash,
                      "generator_sha256": sha256(Path(__file__)),
                      "professor_generator_sha256": sha256(Path(professor_data.__file__)),
                      "completed_at_utc": datetime.now(timezone.utc).isoformat()}
            os.replace(staged_label, label)
            write_json_atomic(marker_file, marker)
            shutil.rmtree(stage)
            validate_one(name, source_root, derived_root, teacher_hash=teacher_hash)
            results.append({"sequence": name, "action": "generated",
                            "elapsed_seconds": round(time.monotonic() - started, 3), "marker": marker})
        finally:
            shutil.rmtree(stage, ignore_errors=True)
    return results
