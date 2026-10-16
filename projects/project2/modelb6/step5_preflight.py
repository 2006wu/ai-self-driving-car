"""Read-only checks for the proposed real Step 5 split; never generate or train."""

import hashlib
import json
import os
from pathlib import Path
import socket
import sys

import h5py
import tensorflow as tf
from tensorflow.keras.models import load_model

from corrections import TARGET_BOUNDS


ROOT = Path("/data/dataB6")
PROFESSOR = Path("/workspace/professor")
CONFIG = Path(__file__).with_name("step5_split.json")
EXPECTED_SHA256 = {
    "datagenB6.py": "b7cec7abb6c4be2a0117d7cf1cf3a4c06269389d101a0f787841d4e722dd75b1",
    "serverB6.py": "a6ffd39388e6ecbbffb7ad228371875379585186d6b54aaa74c360b3c4bfb856",
    "train_modelB6.py": "287c036aac2ca08a08e1ce0befb460a33afd7e798ef5d4eaa1d598ab6b77d6d9",
    "modelB6.py": "0552ddf4be6cdb427d11c0ed438074a3b57c3b6ea62931a7d5575245128041c0",
    "saved_model/supercombo079.keras": "14d312f37e9278779bf68b4639142e8d31a569bde8046d5c60a2a3f746c1c590",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    config = json.loads(CONFIG.read_text())
    train = config["train_sequences"]
    valid = config["validation_sequences"]
    if tf.__version__ != "2.13.1":
        raise RuntimeError(f"unexpected TensorFlow version: {tf.__version__}")
    if not train or not valid or len(set(train + valid)) != len(train + valid):
        raise ValueError("train/validation sequences must be nonempty, unique, and disjoint")
    if len(train + valid) != 3:
        raise ValueError("expected exactly three selected sequences")
    if (config["batch_size"], config["target_width"], TARGET_BOUNDS[-1]) != (2, 2383, 2383):
        raise ValueError("unexpected batch size or target width")
    for path in (ROOT, PROFESSOR, Path("/opt/openpilot")):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError(f"source mount is writable: {path}")
    for path in (Path("/derived"), Path("/output")):
        if os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError(f"student output mount is read-only: {path}")
    if not os.statvfs(Path("/")).f_flag & os.ST_RDONLY:
        raise RuntimeError("container root is writable")
    for relative, expected in EXPECTED_SHA256.items():
        path = PROFESSOR / relative
        if sha256(path) != expected:
            raise RuntimeError(f"professor file differs from preserved baseline: {relative}")

    records = []
    for split, names in (("train", train), ("validation", valid)):
        for name in names:
            if Path(name).name != name or name in (".", ".."):
                raise ValueError(f"invalid sequence name: {name}")
            path = ROOT / name / "yuv.h5"
            if (ROOT / name / "outSC.h5").exists():
                raise RuntimeError(f"source-side teacher output appeared: {name}")
            with h5py.File(path, "r") as source:
                frames = source["X"]
                if frames.ndim != 4 or frames.shape[1:] != (6, 128, 256) or frames.dtype != "float32":
                    raise ValueError(f"invalid YUV dataset: {path}: {frames.shape}, {frames.dtype}")
                count = len(frames)
            batches = len(range(0, count - 2 - config["batch_size"], config["batch_size"]))
            if batches < 1:
                raise ValueError(f"no usable batches: {path}")
            records.append({"split": split, "sequence": name, "frames": count,
                            "teacher_rows": count - 1, "examples": batches * config["batch_size"],
                            "batches": batches})

    teacher = load_model(str(PROFESSOR / "saved_model/supercombo079.keras"), compile=False)
    output_width = sum(int(shape[-1]) for shape in teacher.output_shape)
    if output_width != config["target_width"]:
        raise ValueError(f"teacher output width: {output_width}")

    sockets = []
    try:
        for port in (5557, 5558):
            listener = socket.socket()
            listener.bind(("0.0.0.0", port))
            sockets.append(listener)
    finally:
        for listener in sockets:
            listener.close()
    stale = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            try:
                command = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except (OSError, PermissionError):
                continue
            if "server_corrected.py" in command or "train_corrected.py" in command:
                stale.append({"pid": int(proc.name), "command": command})
    if stale:
        raise RuntimeError(f"stale Step 5 processes: {stale}")

    label_bytes = sum(row["teacher_rows"] * config["target_width"] * 4 for row in records)
    free = {str(path): os.statvfs(path).f_bavail * os.statvfs(path).f_frsize
            for path in (Path("/derived"), Path("/output"))}
    # Includes both model files, temporary checkpoint/save space, logs, and margin.
    reserve = label_bytes + 1024**3
    if min(free.values()) < reserve:
        raise RuntimeError(f"Docker free space below {reserve} bytes: {free}")
    print(json.dumps({"status": "PASS", "tensorflow_version": tf.__version__,
                      "config": config, "records": records,
                      "teacher_output_width": output_width, "label_raw_bytes": label_bytes,
                      "docker_free_bytes": free, "required_free_bytes": reserve,
                      "ports_available": [5557, 5558], "stale_processes": 0}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"PREFLIGHT FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise
