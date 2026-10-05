"""Read-only P2.1 compatibility checks for the restored ModelB6 reference."""
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import tensorflow as tf


PROFESSOR_ROOT = Path("/workspace/professor")
TEACHER_MODEL = PROFESSOR_ROOT / "saved_model" / "supercombo079.keras"
DATA_B6 = Path("/data/dataB6")
DATA_C = Path("/opt/openpilot/tools/replay/dataC")


def require(condition, message):
  if not condition:
    raise RuntimeError(message)


def module_version(module_name):
  module = importlib.import_module(module_name)
  return getattr(module, "__version__", "stdlib")


def mount_is_read_only(path):
  return bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def writable_scratch(path):
  require(not mount_is_read_only(path), f"expected writable mount: {path}")
  with tempfile.TemporaryFile(dir=path) as scratch:
    scratch.write(b"P2.1 mount probe")
    scratch.flush()
  return True


def simulator_import_safety():
  """Probe the unguarded professor module without allowing it to write data."""
  code = "import simulatorB6"
  result = subprocess.run(
      [sys.executable, "-c", code],
      cwd=PROFESSOR_ROOT,
      env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
      capture_output=True,
      text=True,
      timeout=30,
  )
  if result.returncode == 0:
    return {"status": "imported"}
  error = (result.stderr or result.stdout).strip().splitlines()
  return {
      "status": "not_import_safe",
      "reason": error[-1] if error else "subprocess exited without diagnostics",
  }


def main():
  require(PROFESSOR_ROOT.is_dir(), f"missing professor mount: {PROFESSOR_ROOT}")
  require(TEACHER_MODEL.is_file(), f"missing teacher model: {TEACHER_MODEL}")
  require(DATA_B6.is_dir(), f"missing dataB6 mount: {DATA_B6}")
  require(DATA_C.is_dir(), f"missing dataC mount: {DATA_C}")

  sys.path.insert(0, str(PROFESSOR_ROOT))
  versions = {
      name: module_version(name)
      for name in ("tensorflow", "numpy", "h5py", "cv2", "zmq", "six", "matplotlib", "tqdm")
  }
  installed_distributions = {
      name: metadata.version(name)
      for name in (
          "tensorflow-cpu", "keras", "numpy", "h5py", "opencv-python-headless",
          "pyzmq", "six", "matplotlib", "tqdm", "atomicwrites", "lru-dict",
          "requests", "tenacity",
      )
  }

  # Test C: exact imports needed by the professor ModelB6 files.
  openpilot_modules = {}
  for name in (
      "tools.lib.framereader",
      "common.transformations.model",
      "common.transformations.orientation",
  ):
    importlib.import_module(name)
    openpilot_modules[name] = "ok"

  # Test B: safe imports. simulatorB6 has executable top-level code and is
  # assessed separately below instead of being imported into this process.
  professor_modules = {}
  for name in ("modelB6", "datagenB6", "serverB6", "parserB6", "cameraB3", "lanes_image_space", "hevc2yuvh5"):
    importlib.import_module(name)
    professor_modules[name] = "ok"

  # Test D: no fit(), predict(), data generation, or output write occurs here.
  model_b6 = importlib.import_module("modelB6")
  model = model_b6.get_model()
  output_shape = tuple(model.output_shape)
  require(output_shape == (None, 2383), f"unexpected ModelB6 output shape: {output_shape}")

  # Test E: the extension is .keras, but the archived file is HDF5. compile=False
  # avoids evaluating unavailable training-only custom objects.
  teacher = tf.keras.models.load_model(TEACHER_MODEL, compile=False)

  # Test F: inspect only. The Compose mounts make these paths read-only.
  data_b6_sample = next(DATA_B6.glob("*/video.hevc"), None)
  data_c_sample = next(DATA_C.glob("*/**/fcamera.hevc"), None)
  require(data_b6_sample is not None, "no dataB6 video.hevc is visible")
  require(data_c_sample is not None, "no dataC fcamera.hevc is visible")
  for path in (PROFESSOR_ROOT, Path("/opt/openpilot"), DATA_B6, DATA_C, Path("/workspace/student")):
    require(mount_is_read_only(path), f"expected read-only mount: {path}")

  result = {
      "python": sys.version.split()[0],
      "versions": versions,
      "installed_distributions": installed_distributions,
      "professor_modules": professor_modules,
      "openpilot_modules": openpilot_modules,
      "modelb6": {
          "input_shapes": [tuple(shape) for shape in model.input_shape],
          "output_shape": output_shape,
          "parameter_count": model.count_params(),
      },
      "teacher_model": {
          "path": str(TEACHER_MODEL),
          "input_shapes": [tuple(shape) for shape in teacher.input_shape],
          "output_shapes": [tuple(shape) for shape in teacher.output_shape],
      },
      "data_visibility": {
          "data_b6_sample": str(data_b6_sample),
          "data_c_sample": str(data_c_sample),
          "professor_read_only": not os.access(PROFESSOR_ROOT, os.W_OK),
          "openpilot_read_only": not os.access("/opt/openpilot", os.W_OK),
          "data_read_only": not os.access(DATA_B6, os.W_OK),
          "professor_mount_read_only": mount_is_read_only(PROFESSOR_ROOT),
          "openpilot_mount_read_only": mount_is_read_only("/opt/openpilot"),
          "data_b6_mount_read_only": mount_is_read_only(DATA_B6),
          "data_c_mount_read_only": mount_is_read_only(DATA_C),
          "student_root_read_only": mount_is_read_only("/workspace/student"),
          "derived_writable": writable_scratch("/derived"),
          "output_writable": writable_scratch("/output"),
      },
      "simulatorB6": simulator_import_safety(),
  }
  print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
  main()
