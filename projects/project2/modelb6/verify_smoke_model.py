"""Fresh-process load checks for the P2.3 smoke artifacts."""

import json
from pathlib import Path

import tensorflow as tf

from modelB6 import get_model


def main():
    root = Path("/output/smoke")
    final = tf.keras.models.load_model(str(root / "B6.keras"), compile=False)
    checkpoint = tf.keras.models.load_model(str(root / "B6BW.hdf5"), compile=False)
    expected_inputs = [(None, 12, 128, 256), (None, 8), (None, 2), (None, 512)]
    for name, model in (("final", final), ("checkpoint", checkpoint)):
        inputs = [tuple(shape) for shape in model.input_shape]
        if inputs != expected_inputs or tuple(model.output_shape) != (None, 2383):
            raise RuntimeError(f"{name} model shape mismatch: {inputs}, {model.output_shape}")
    resumed = get_model()
    resumed.load_weights(str(root / "B6BW.hdf5"))
    if tuple(resumed.output_shape) != (None, 2383):
        raise RuntimeError("checkpoint could not restore ModelB6 weights")
    print(json.dumps({"status": "PASS", "final_model": str(root / "B6.keras"),
                      "checkpoint": str(root / "B6BW.hdf5"),
                      "checkpoint_load_weights": True,
                      "input_shapes": expected_inputs, "output_shape": (None, 2383)}, indent=2))


if __name__ == "__main__":
    main()
