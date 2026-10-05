"""One-epoch, one-step corrected ModelB6 Step 5 smoke training entry point."""

import argparse
import json
from pathlib import Path
import time

import numpy as np
import tensorflow as tf

import datagenB6 as professor_data
from modelB6 import get_model
import train_modelB6 as professor_train
from corrections import initialize_model, validation_checkpoint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-steps", type=int, default=1)
    parser.add_argument("--smoke-validation-steps", type=int, default=1)
    parser.add_argument("--smoke-epochs", type=int, default=1)
    args = parser.parse_args()
    if (args.smoke_steps, args.smoke_validation_steps, args.smoke_epochs) != (1, 1, 1):
        raise ValueError("P2.3 permits only one training step, one validation step, one epoch")

    output_root = Path("/output/smoke")
    output_root.mkdir(parents=True, exist_ok=True)
    final_model = output_root / "B6.keras"
    best_weights = output_root / "B6BW.hdf5"
    if final_model.exists() or best_weights.exists():
        raise FileExistsError("smoke outputs already exist; refusing to overwrite them")

    started = time.monotonic()
    model = get_model()
    professor_train.model = model  # professor callbacks look up this module global
    fresh_start = not initialize_model(model, output_root=output_root)
    lr_max, lr_min = 1e-3, 5e-4  # professor train_modelB6.py defaults
    optimizer = tf.keras.optimizers.Adam(learning_rate=lr_max)
    model.compile(optimizer=optimizer, loss=professor_train.custom_loss,
                  metrics=[professor_train.maxae])

    start_x, start_y = next(professor_train.get_data(20, "localhost", 5557, model))
    if [tuple(value.shape) for value in start_x] != [
            (2, 12, 128, 256), (2, 8), (2, 2), (2, 512)]:
        raise ValueError("unexpected training input shapes")
    if start_y.shape != (2, 2383):
        raise ValueError(f"unexpected training target shape: {start_y.shape}")
    initial_prediction = model(start_x, training=False)
    starting_loss = float(np.mean(professor_train.custom_loss(start_y, initial_prediction).numpy()))

    checkpoint = validation_checkpoint(output_root)
    callbacks = [
        checkpoint,
        professor_train.PrintLearningRate(),
        tf.keras.callbacks.LearningRateScheduler(professor_train.scheduler),
        professor_train.CosineAnnealing(CA_period=professor_data.EPOCHS / 1,
                                        lr_max=lr_max, lr_min=lr_min),
    ]
    history = model.fit(
        professor_train.get_data(20, "localhost", 5557, model),
        steps_per_epoch=args.smoke_steps,
        epochs=args.smoke_epochs,
        verbose=1,
        callbacks=callbacks,
        validation_data=professor_train.get_data(20, "localhost", 5558, model),
        validation_steps=args.smoke_validation_steps,
    )
    if not best_weights.is_file():
        raise RuntimeError("validation checkpoint was not created")
    model.save(str(final_model))
    if not final_model.is_file():
        raise RuntimeError("final smoke model was not created")
    result = {
        "status": "PASS",
        "smoke_steps": args.smoke_steps,
        "smoke_validation_steps": args.smoke_validation_steps,
        "smoke_epochs": args.smoke_epochs,
        "batch_size": professor_data.BATCH_SIZE,
        "fresh_start": fresh_start,
        "starting_loss": starting_loss,
        "final_training_loss": float(history.history["loss"][-1]),
        "validation_loss": float(history.history["val_loss"][-1]),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "checkpoint": str(best_weights),
        "final_model": str(final_model),
        "checkpoint_monitor": checkpoint.monitor,
        "checkpoint_save_best_only": checkpoint.save_best_only,
        "input_shapes": [list(value.shape) for value in start_x],
        "target_shape": list(start_y.shape),
    }
    (output_root / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
