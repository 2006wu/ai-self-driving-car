"""Run the gated P2.3 preparation, two streams, one-step fit, and shutdown."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import h5py
import numpy as np
import zmq

from serverB6 import recv_arrays


HERE = Path("/workspace/student")
OUTPUT = Path("/output/smoke")
DERIVED = Path("/derived/smoke/dataB6")
ORIGINAL = Path("/data/dataB6")
TARGET_WIDTHS = (385, 386, 386, 58, 200, 200, 200, 8, 4, 32, 12, 512)


def stage(name, argv, timeout):
    print(f"STAGE {name}: {' '.join(argv)}", flush=True)
    result = subprocess.run(argv, cwd=HERE, capture_output=True, text=True, timeout=timeout)
    log = OUTPUT / f"{name}.log"
    log.write_text(result.stdout + result.stderr)
    print(result.stdout, flush=True)
    if result.returncode:
        print(result.stderr, flush=True)
        raise RuntimeError(f"{name} failed (exit {result.returncode}); see {log}")
    return result


def probe(port, sequence):
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.setsockopt(zmq.RCVTIMEO, 30000)
    socket.connect(f"tcp://127.0.0.1:{port}")
    try:
        arrays = recv_arrays(socket)
    finally:
        socket.close(linger=0)
        context.term()
    actual = [tuple(array.shape) for array in arrays]
    expected = [(2, 12, 128, 256), (2, 8), (2, 2), (2, 512)]
    expected += [(2, width) for width in TARGET_WIDTHS]
    if actual != expected:
        raise RuntimeError(f"port {port} shapes: {actual}, expected {expected}")
    targets = np.hstack(arrays[4:])
    original = ORIGINAL / sequence / "yuv.h5"
    teacher = DERIVED / sequence / "outSC.h5"
    with h5py.File(original, "r") as source, h5py.File(teacher, "r") as labels:
        np.testing.assert_array_equal(arrays[0][0], np.vstack((source["X"][0], source["X"][1])))
        np.testing.assert_array_equal(arrays[0][1], np.vstack((source["X"][1], source["X"][2])))
        np.testing.assert_array_equal(targets, labels["X"][:2])
    result = {"status": "PASS", "sequence": sequence, "port": port,
              "array_shapes": actual, "target_shape": list(targets.shape),
              "alignment": True}
    print(json.dumps(result, indent=2), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-sequence", required=True)
    parser.add_argument("--validation-sequence", required=True)
    args = parser.parse_args()
    if args.train_sequence == args.validation_sequence:
        raise ValueError("smoke training and validation sequences must differ")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    processes = []
    handles = []
    started = time.monotonic()
    try:
        stage("prepare", [sys.executable, str(HERE / "prepare_smoke.py"),
                          "--train-sequence", args.train_sequence,
                          "--validation-sequence", args.validation_sequence,
                          "--smoke-frames", "5"], timeout=1200)
        for role, sequence, port in (("train", args.train_sequence, 5557),
                                     ("validation", args.validation_sequence, 5558)):
            log = (OUTPUT / f"{role}-server.log").open("w")
            handles.append(log)
            process = subprocess.Popen(
                [sys.executable, str(HERE / "server_corrected.py"),
                 "--sequence", sequence, "--port", str(port), "--smoke-frames", "5"],
                cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
            )
            processes.append(process)
        probes = [probe(5557, args.train_sequence), probe(5558, args.validation_sequence)]
        (OUTPUT / "stream-probes.json").write_text(json.dumps(probes, indent=2) + "\n")
        stage("train", [sys.executable, str(HERE / "train_corrected.py"),
                        "--smoke-steps", "1", "--smoke-validation-steps", "1",
                        "--smoke-epochs", "1"], timeout=1800)
        stage("verify", [sys.executable, str(HERE / "verify_smoke_model.py")], timeout=120)
        print(json.dumps({"status": "PASS", "elapsed_seconds": round(time.monotonic() - started, 3),
                          "train_sequence": args.train_sequence,
                          "validation_sequence": args.validation_sequence,
                          "smoke_frames_per_sequence": 5, "smoke_steps": 1,
                          "smoke_validation_steps": 1, "smoke_epochs": 1}, indent=2), flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        for handle in handles:
            handle.close()
        print("server subprocesses stopped", flush=True)


if __name__ == "__main__":
    main()
