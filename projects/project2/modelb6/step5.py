"""Production ModelB6 Step 5 commands; all writes stay in Project 2 volumes."""

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import resource
import signal
import socket
import subprocess
import sys
import time

import h5py
import numpy as np
import tensorflow as tf

import datagenB6 as professor_data
from modelB6 import get_model
from serverB6 import client_generator, start_server
import train_modelB6 as professor_train

from corrections import corrected_datagen, initialize_model, validation_checkpoint
from step5_data import (DERIVED_ROOT, SOURCE_ROOT, prepare, selected_sequences,
                        sha256, split_config, validate_all, write_json_atomic)


OUTPUT = Path("/output/step5")
RUNS = OUTPUT / "runs"
INPUT_SHAPES = [(None, 12, 128, 256), (None, 8), (None, 2), (None, 512)]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_directory(run_id, create=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("invalid run ID")
    root = RUNS / run_id
    if create:
        root.mkdir(parents=True, exist_ok=False)
        (root / "logs").mkdir()
        (root / "metrics").mkdir()
        (root / "plots").mkdir()
    return root


def ensure_shapes(batch):
    expected = [(2, 12, 128, 256), (2, 8), (2, 2), (2, 512)]
    actual = [tuple(part.shape) for part in batch[:4]]
    targets = np.hstack(batch[4:])
    if actual != expected or targets.shape != (2, 2383):
        raise ValueError(f"invalid stream shapes: {actual}, {targets.shape}")
    if not all(np.isfinite(part).all() for part in batch):
        raise ValueError("nonfinite stream batch")
    return targets


def stream_for_split(split, config=None, source_root=SOURCE_ROOT, derived_root=DERIVED_ROOT):
    config = config or split_config()
    if split not in ("train", "validation"):
        raise ValueError("server split must be train or validation")
    validate_all(config, source_root, derived_root)
    names = config["train_sequences" if split == "train" else "validation_sequences"]
    paths = [str(Path(source_root) / name / "yuv.h5") for name in names]
    return names, corrected_datagen(paths, steps=1, original_root=source_root,
                                    derived_root=derived_root)


def server(split):
    config = split_config()
    names, stream = stream_for_split(split, config)
    first = next(stream)
    ensure_shapes(first)
    port = 5557 if split == "train" else 5558
    print(f"SERVING split={split} sequences={','.join(names)} port={port}", flush=True)
    _, stream = stream_for_split(split, config)
    start_server(stream, port=port, hwm=2)


class MetricsCallback(tf.keras.callbacks.Callback):
    def __init__(self, jsonl, timings=False):
        super().__init__()
        self.jsonl = Path(jsonl)
        self.records = []
        self.timings = timings
        self.train_steps = []
        self.validation_steps = []
        self.first_train_step = None

    def on_train_batch_begin(self, batch, logs=None):
        self._train_started = time.monotonic()

    def on_train_batch_end(self, batch, logs=None):
        duration = time.monotonic() - self._train_started
        if self.first_train_step is None:
            self.first_train_step = duration
        else:
            self.train_steps.append(duration)
        if not np.isfinite(float((logs or {}).get("loss", np.nan))):
            raise FloatingPointError("nonfinite training loss")

    def on_test_batch_begin(self, batch, logs=None):
        self._validation_started = time.monotonic()

    def on_test_batch_end(self, batch, logs=None):
        self.validation_steps.append(time.monotonic() - self._validation_started)
        if not np.isfinite(float((logs or {}).get("loss", np.nan))):
            raise FloatingPointError("nonfinite validation loss")

    def on_epoch_end(self, epoch, logs=None):
        record = {"epoch": int(epoch + 1), "time_utc": utc_now()}
        record.update({key: float(value) for key, value in (logs or {}).items()})
        for key in ("loss", "val_loss"):
            if key not in record or not np.isfinite(record[key]):
                raise FloatingPointError(f"missing/nonfinite {key} in epoch {epoch + 1}")
        self.records.append(record)
        with self.jsonl.open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, value):
        for stream in self.streams:
            stream.write(value)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return False


def compiled_model(resume_checkpoint=None, output_root=OUTPUT):
    model = get_model()
    professor_train.model = model  # professor schedule refers to its module global
    resumed = initialize_model(model, resume_checkpoint=resume_checkpoint, output_root=output_root)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
                  loss=professor_train.custom_loss, metrics=[professor_train.maxae])
    return model, resumed


def callbacks(metrics, checkpoint_root=None):
    result = []
    if checkpoint_root is not None:
        result.append(validation_checkpoint(checkpoint_root))
    result += [professor_train.PrintLearningRate(),
               tf.keras.callbacks.LearningRateScheduler(professor_train.scheduler),
               professor_train.CosineAnnealing(CA_period=professor_data.EPOCHS / 1,
                                               lr_max=1e-3, lr_min=5e-4), metrics]
    return result


def train(run_id, resume_checkpoint=None):
    config = split_config()
    markers = validate_all(config)
    root = run_directory(run_id, create=True)
    manifest_file = root / "run.json"
    if resume_checkpoint is not None:
        checkpoint = Path(resume_checkpoint).resolve(strict=True)
        checkpoint.relative_to(RUNS.resolve(strict=True))
        if checkpoint.name != "B6BW.hdf5":
            raise ValueError("resume requires a prior Step 5 best checkpoint")
    manifest = {"status": "running", "run_id": run_id, "started_at_utc": utc_now(),
                "train_sequences": config["train_sequences"],
                "validation_sequences": config["validation_sequences"],
                "marker_sha256": {m["sequence"]: sha256(DERIVED_ROOT / m["sequence"] / "outSC.complete.json")
                                  for m in markers},
                "batch_size": config["batch_size"], "steps_per_epoch": config["steps_per_epoch"],
                "validation_steps": config["validation_steps"], "epochs_requested": config["epochs"],
                "tensorflow_version": tf.__version__, "numpy_version": np.__version__,
                "h5py_version": h5py.__version__, "python_version": sys.version.split()[0],
                "optimizer": "Adam", "lr_max": 1e-3, "lr_min": 5e-4,
                "schedule": "professor cosine annealing, period 60", "loss_weights": [0.3, 0.3, 0.3, 0.1],
                "resume_checkpoint": str(resume_checkpoint) if resume_checkpoint else None,
                "resume_semantics": "new segment from best weights; optimizer/scheduler not restored" if resume_checkpoint else "fresh"}
    write_json_atomic(manifest_file, manifest)
    started = time.monotonic()
    try:
        model, resumed = compiled_model(resume_checkpoint, OUTPUT)
        manifest["fresh_start"] = not resumed
        manifest["parameter_count"] = model.count_params()
        manifest["output_shape"] = list(model.output_shape)
        if tuple(model.output_shape) != (None, 2383):
            raise ValueError("ModelB6 output shape changed")
        metrics = MetricsCallback(root / "metrics" / "epochs.jsonl")
        with (root / "logs" / "train.log").open("w", buffering=1) as logfile:
            with redirect_stdout(Tee(sys.stdout, logfile)), redirect_stderr(Tee(sys.stderr, logfile)):
                history = model.fit(professor_train.get_data(20, "localhost", 5557, model),
                                    steps_per_epoch=config["steps_per_epoch"], epochs=config["epochs"],
                                    verbose=2, callbacks=callbacks(metrics, root),
                                    validation_data=professor_train.get_data(20, "localhost", 5558, model),
                                    validation_steps=config["validation_steps"])
        if len(metrics.records) != config["epochs"]:
            raise RuntimeError("incomplete epoch history")
        checkpoint = root / "B6BW.hdf5"
        if not checkpoint.is_file():
            raise RuntimeError("best checkpoint missing")
        final = root / "B6.keras"
        model.save(str(final))
        best = min(metrics.records, key=lambda record: record["val_loss"])
        manifest.update({"status": "complete", "finished_at_utc": utc_now(),
                         "elapsed_seconds": round(time.monotonic() - started, 3),
                         "epochs_completed": len(metrics.records),
                         "train_steps_completed": len(metrics.records) * config["steps_per_epoch"],
                         "validation_steps_completed": len(metrics.records) * config["validation_steps"],
                         "loss_history": [float(x) for x in history.history["loss"]],
                         "val_loss_history": [float(x) for x in history.history["val_loss"]],
                         "best_val_loss": best["val_loss"], "best_epoch": best["epoch"],
                         "final_model": str(final), "final_model_sha256": sha256(final),
                         "final_model_size_bytes": final.stat().st_size,
                         "checkpoint": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
                         "checkpoint_size_bytes": checkpoint.stat().st_size})
        write_json_atomic(manifest_file, manifest)
        print(json.dumps(manifest, indent=2), flush=True)
        return manifest
    except BaseException as error:
        manifest.update({"status": "failed", "finished_at_utc": utc_now(),
                         "error": f"{type(error).__name__}: {error}",
                         "elapsed_seconds": round(time.monotonic() - started, 3)})
        write_json_atomic(manifest_file, manifest)
        raise


def verify(run_id):
    root = run_directory(run_id)
    manifest = json.loads((root / "run.json").read_text())
    if manifest["status"] != "complete":
        raise RuntimeError("run manifest is not complete")
    results = {}
    for name, filename in (("final", "B6.keras"), ("checkpoint", "B6BW.hdf5")):
        path = root / filename
        model = tf.keras.models.load_model(str(path), compile=False)
        if [tuple(shape) for shape in model.input_shape] != INPUT_SHAPES or tuple(model.output_shape) != (None, 2383):
            raise ValueError(f"{name} input/output contract changed")
        with h5py.File(SOURCE_ROOT / split_config()["train_sequences"][0] / "yuv.h5", "r") as source:
            image = np.vstack((source["X"][0], source["X"][1]))[None]
        prediction = model([image, np.zeros((1, 8), np.float32),
                            np.array([[1., 0.]], np.float32), np.zeros((1, 512), np.float32)],
                           training=False).numpy()
        if prediction.shape != (1, 2383) or not np.isfinite(prediction).all():
            raise ValueError(f"{name} inference invalid")
        results[name] = {"path": str(path), "sha256": sha256(path),
                         "size_bytes": path.stat().st_size, "finite_inference": True}
    fresh = get_model()
    fresh.load_weights(str(root / "B6BW.hdf5"))
    results["checkpoint_weights_reload"] = True
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axis = plt.subplots(figsize=(8, 4.5))
    epochs = range(1, len(manifest["loss_history"]) + 1)
    axis.plot(epochs, manifest["loss_history"], label="train loss")
    axis.plot(epochs, manifest["val_loss_history"], label="validation loss")
    axis.set(xlabel="Epoch", ylabel="Custom loss", yscale="log", title="ModelB6 Step 5 loss")
    axis.grid(True, which="both", alpha=0.3)
    axis.legend()
    fig.tight_layout()
    plot = root / "plots" / "loss.png"
    fig.savefig(str(plot), dpi=150)
    plt.close(fig)
    results["loss_plot"] = str(plot)
    write_json_atomic(root / "metrics" / "verification.json", results)
    print(json.dumps({"status": "PASS", "run_id": run_id, **results}, indent=2))
    return results


def launch_server(split, log_dir, smoke=False):
    name = "train" if split == "train" else "validation"
    logfile = (log_dir / f"{name}-server.log").open("w")
    command = ([sys.executable, "/workspace/student/server_corrected.py",
                "--sequence", "UHD--2018-08-02--08-34-47--33" if split == "train" else "UHD--2018-08-02--08-34-47--32",
                "--port", "5557" if split == "train" else "5558"] if smoke else
               [sys.executable, str(Path(__file__)), "server", "--split", split])
    process = subprocess.Popen(command, stdout=logfile, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            logfile.close()
            raise RuntimeError(f"{name} server exited early; see {logfile.name}")
        logfile.flush()
        if "SERVING" in Path(logfile.name).read_text():
            return process, logfile
        time.sleep(0.2)
    process.terminate()
    process.wait(timeout=10)
    logfile.close()
    raise TimeoutError(f"{name} server startup timed out; see {logfile.name}")


def stop_servers(servers):
    for process, _ in servers:
        if process.poll() is None:
            process.terminate()
    for process, logfile in servers:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        logfile.close()


def probe_servers(servers, full_transition=False):
    results = {}
    for split, port in (("train", 5557), ("validation", 5558)):
        stream = client_generator(port=port, hwm=2)
        for _ in range(3):
            ensure_shapes(next(stream))
        results[split] = {"probed_batches": 3, "port": port}
        if split == "train" and full_transition:
            names = split_config()["train_sequences"]
            first_path = SOURCE_ROOT / names[0] / "yuv.h5"
            with h5py.File(first_path, "r") as source:
                first_count = len(range(0, len(source["X"]) - 4, 2))
            for _ in range(first_count - 3):
                ensure_shapes(next(stream))
            boundary = next(stream)
            ensure_shapes(boundary)
            with h5py.File(SOURCE_ROOT / names[1] / "yuv.h5", "r") as source, \
                    h5py.File(DERIVED_ROOT / names[1] / "outSC.h5", "r") as labels:
                np.testing.assert_array_equal(boundary[0][0], np.vstack((source["X"][0], source["X"][1])))
                np.testing.assert_array_equal(np.hstack(boundary[4:])[0], labels["X"][0])
            np.testing.assert_array_equal(boundary[3][0], np.zeros(512, np.float32))
            results[split]["probed_batches"] = first_count + 1
            results[split]["verified_transition_to"] = names[1]
        stream.close()
    if any(process.poll() is not None for process, _ in servers):
        raise RuntimeError("server exited during probe")
    return results


def benchmark():
    # Uses only existing five-frame smoke labels; never writes into smoke output.
    benchmark_id = "benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = OUTPUT / "benchmarks" / benchmark_id
    root.mkdir(parents=True, exist_ok=False)
    servers = []
    started = time.monotonic()
    try:
        for split in ("train", "validation"):
            servers.append(launch_server(split, root, smoke=True))
        probes = probe_servers(servers)
        model, _ = compiled_model()
        metrics = MetricsCallback(root / "epochs.jsonl", timings=True)
        history = model.fit(professor_train.get_data(20, "localhost", 5557, model),
                            steps_per_epoch=15, epochs=1, verbose=2,
                            callbacks=callbacks(metrics),
                            validation_data=professor_train.get_data(20, "localhost", 5558, model),
                            validation_steps=5)
        result = {"status": "PASS", "train_steps": 15, "validation_steps": 5,
                  "first_train_step_seconds": metrics.first_train_step,
                  "subsequent_train_mean_seconds": float(np.mean(metrics.train_steps)),
                  "subsequent_train_min_seconds": min(metrics.train_steps),
                  "subsequent_train_max_seconds": max(metrics.train_steps),
                  "validation_mean_seconds": float(np.mean(metrics.validation_steps)),
                  "validation_min_seconds": min(metrics.validation_steps),
                  "validation_max_seconds": max(metrics.validation_steps),
                  "total_seconds": time.monotonic() - started,
                  "max_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "loss": float(history.history["loss"][-1]),
                  "val_loss": float(history.history["val_loss"][-1]), "probes": probes}
        if not np.isfinite([result["loss"], result["val_loss"]]).all():
            raise FloatingPointError("nonfinite benchmark losses")
        write_json_atomic(root / "benchmark.json", result)
        print(json.dumps(result, indent=2), flush=True)
        return result
    finally:
        stop_servers(servers)


def run(run_id, resume_checkpoint=None):
    from step5_preflight import main as preflight
    preflight()
    validate_all(spot_check=True)
    log_dir = OUTPUT / "orchestration" / run_id
    log_dir.mkdir(parents=True, exist_ok=False)
    servers = []
    try:
        for split in ("train", "validation"):
            servers.append(launch_server(split, log_dir))
        probes = probe_servers(servers, full_transition=True)
        write_json_atomic(log_dir / "dry-run.json", probes)
    finally:
        stop_servers(servers)
    servers = []
    try:
        for split in ("train", "validation"):
            servers.append(launch_server(split, log_dir))
        result = train(run_id, resume_checkpoint)
    finally:
        stop_servers(servers)
    verify(run_id)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--force", action="store_true")
    commands.add_parser("validate-labels")
    server_parser = commands.add_parser("server")
    server_parser.add_argument("--split", required=True, choices=("train", "validation"))
    commands.add_parser("benchmark")
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--resume-checkpoint")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        from step5_preflight import main as preflight
        preflight()
    elif args.command == "prepare":
        from step5_preflight import main as preflight
        preflight()
        print(json.dumps(prepare(force=args.force), indent=2), flush=True)
    elif args.command == "validate-labels":
        print(json.dumps({"status": "PASS", "markers": validate_all(spot_check=True)}, indent=2))
    elif args.command == "server":
        server(args.split)
    elif args.command == "benchmark":
        benchmark()
    elif args.command == "run":
        run(args.run_id, args.resume_checkpoint)
    elif args.command == "verify":
        verify(args.run_id)


if __name__ == "__main__":
    main()
