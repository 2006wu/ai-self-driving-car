# Student ModelB6 correction layer

`corrections.py` is student code. The professor files remain in ignored
`external/aJLL/ModelB6/` and are mounted read-only at `/workspace/professor`.
This layer imports the professor's batch and trim constants without copying the
original training or generator scripts.

- `initialize_model` starts with initialized weights unless a checkpoint path is
  explicitly supplied. Resume checkpoints must live under `/output`.
- `validation_checkpoint` selects the best `val_loss` with `mode="min"` and
  `save_best_only=True`, writing `/output/B6BW.hdf5`.
- `derived_teacher_path` maps `/data/dataB6/<sequence>/yuv.h5` to
  `/derived/dataB6/<sequence>/outSC.h5`.
- `generate_derived_teacher` makes a tiny HDF5 external link to the original
  `X` dataset under `/derived`, invokes a supplied generator there, checks the
  output shape, then publishes it in `/derived`. P2.2 tests use a fake generator;
  they do not run the professor's teacher inference.
- `corrected_datagen` reads the original frames and each sequence's derived
  teacher file. It uses the same frame index for image and teacher row, and
  retains the professor's batch size, trim setting, output slices, and state
  propagation. It does not create missing labels.

Run the seven tiny fixtures in the isolated runtime:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/fixture_tests.py
```

The professor `serverB6.py` and `train_modelB6.py` still call their original
functions. The student entry points below use this layer for the controlled
smoke run. Do not launch the professor training commands as a corrected workflow.

## P2.3 small real-data smoke pipeline

`smoke_pipeline.py` runs student-owned preparation, two corrected ZeroMQ servers,
one corrected training step and one validation step, fresh-process model loading,
and server shutdown. It requires explicit, distinct sequence names. The P2.3
run used `--33` for training and `--32` for validation:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/smoke_pipeline.py \
  --train-sequence UHD--2018-08-02--08-34-47--33 \
  --validation-sequence UHD--2018-08-02--08-34-47--32
```

The smoke-only frame limit is five frames per sequence. Teacher generation uses
the professor's `oSC_Gen` against a five-frame copy staged under `/derived`, then
publishes four labels per sequence at `/derived/smoke/dataB6/<sequence>/outSC.h5`.
Both server probes verify one two-sample batch before training begins. Training
keeps the professor's model, custom loss, Adam optimizer, and schedule, with an
explicit one-step/one-epoch smoke override. Models and logs go to `/output/smoke`.
The runner refuses existing labels or model files to avoid mixing runs; archive
or choose a new isolated smoke namespace before repeating it. The smoke model
is an execution artifact, not a validated final B6 model.

## P2.4 real Step 5 plan (no full run yet)

`step5_split.json` records the proposed, deterministic sequence split: train
`--33` then `--37`; validate on distinct `--32`. All names are written in full
in the file. The complete inventory, exact generator batch arithmetic, storage
and time budgets, unchanged professor settings, interruption rules, Step 5
success criteria and Step 6 handoff are in
[`docs/PROJECT2_AUDIT.md`](../../../docs/PROJECT2_AUDIT.md), section 14.

The reusable preflight is safe to run without creating labels or models:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5_preflight.py
```

The 2026-10-05 preflight passed. It checks the split, all three YUV files,
teacher loading/output width, critical professor hashes, mount flags, space,
ports, and visible stale student processes. Run it again inside the eventual
long-lived Step 5 container immediately before server launch: an ephemeral
container's port/process namespace cannot certify other containers.

The planned writable layout is `/derived/step5/dataB6/<sequence>/outSC.h5`
plus per-sequence completion markers, and `/output/step5/` with `B6.keras`,
`B6BW.hdf5`, `logs/`, `metrics/`, and `plots/`. Source mounts stay read-only.
At P2.4, the preparation, server and trainer entry points were deliberately
smoke-only. Full-run student CLIs and marker validation were still required,
so P2.4 ended with **NO-GO** for the full run. Those smoke limits remain in
place; the separate production interface below resolved that gate.

## P2.5 production Step 5 result

P2.5 added `step5_data.py` and `step5.py` for selected-sequence label
generation, completion-marker validation, explicit multi-sequence servers,
bounded benchmarking, gated training orchestration, and artifact verification.
The P2.4 NO-GO was resolved: 7 existing and 13 production fixtures passed,
the bounded 15/5-step benchmark passed, and preflight passed. The completed
baseline run is **`p25-baseline-20261005`** (60 epochs, 1,200 train steps,
600 validation steps). Full evidence and loss analysis are in
[`docs/PROJECT2_AUDIT.md`](../../../docs/PROJECT2_AUDIT.md), section 15.

Run these commands from the repository root. Each `docker compose run` starts a
new isolated container; `step5.py run` starts both servers inside **its own**
container so they share the required ZeroMQ namespace:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py preflight
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py benchmark
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py prepare
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py validate-labels
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py run --run-id NEW_UNIQUE_RUN_ID
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 \
  python3.8 /workspace/student/step5.py verify --run-id NEW_UNIQUE_RUN_ID
```

The completed baseline already owns `p25-baseline-20261005`; reuse it only for
read-only verification. A new `run` ID creates a separate directory under
`/output/step5/runs/` and refuses existing output. `prepare` reuses each
completed label only after revalidating its JSON marker and source/label hashes.
The marker records sequence, source identity and frame count, row count, width,
dtype, label size and SHA-256, teacher SHA-256, generator hashes, timestamp,
and `status: complete`. A final label without a valid marker or a leftover
hidden stage fails closed. `prepare --force` quarantines suspicious files
**under `/derived/step5`** before regenerating that selected sequence; it does
not touch the read-only original dataset. No `--force` was needed in P2.5.

The `run` command repeats preflight and label checks, probes actual server
batches including the `--33` to `--37` transition, restarts clean servers,
trains with the unchanged baseline hyperparameters, then reloads both outputs
in a fresh verification process. Its manifest, epoch JSONL, train/server logs,
verification result, and loss plot stay under the run directory. To resume
after an interruption, supply a prior Step 5 best checkpoint with
`--resume-checkpoint /output/step5/runs/PRIOR_ID/B6BW.hdf5` **and a new run ID**.
This starts a new training segment from best weights; optimizer and scheduler
state are not restored, so it is not an exact continuation.

The Step 6 handoff is the final artifact
`/output/step5/runs/p25-baseline-20261005/B6.keras` (SHA-256
`7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03`).
The best `B6BW.hdf5` remains alongside it. The final-vs-best validation-loss
gap is examined by the separate Step 6 workflow below.

## P2.6 controlled Step 6 verification

`step6.py` reads the immutable P2.5 final model and best checkpoint. It decodes
the professor's USA `--37/video.hevc` and Taiwan dataC `61/fcamera.hevc`, forms
paired `(1,12,128,256)` images with the professor camera transform, starts
each run with zero desire/traffic/state, and feeds the predicted 512-value
state into the next frame. Raw 2383 outputs are saved separately from parsed
values and four-panel visuals. The parser adapter applies the professor Step 6
slide's **USA** right offset `-0.5` and **Taiwan** path/lane/projection settings;
the active professor parser's USA right offset is `-0.1`. The adapter also
evaluates professor softplus stably when large finite logits would overflow.
Professor files are never edited. Step 6 traffic `[0,0]` differs from the
Step 5 training input `[1,0]`; that mismatch is an interpretation limit.

From the repository root, build and run within the isolated Compose service:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py preflight --count-frames
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6_integrity.py snapshot
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py smoke --domain usa --model final --frames 5
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py smoke --domain usa --model best --frames 5
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py smoke --domain taiwan --model final --frames 5
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py smoke --domain taiwan --model best --frames 5
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py compare --domain usa --smoke
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py compare --domain taiwan --smoke
```

The source clips decode sequentially to **1,200 USA** and **1,202 Taiwan**
frames. OpenCV's reported HEVC frame count is invalid; the runner records both
the reported and decoded counts. Full-clip calls use zero-based frame indices
and process each adjacent pair once:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py run --domain usa --model final --start 0 --frames 1199
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py run --domain usa --model best --start 0 --frames 1199
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py run --domain taiwan --model final --start 0 --frames 1201
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py run --domain taiwan --model best --start 0 --frames 1201
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py compare --domain usa
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py compare --domain taiwan
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6.py report
docker compose -f docker/docker-compose.yaml --profile project2 run --rm modelb6 python3.8 /workspace/student/step6_integrity.py verify
```

Each cell writes a completion manifest, all raw outputs, parsed path/lane/lead
rows, and first/middle/last four-panel PNGs under `/output/step6/<domain>/<model>/`.
The `compare` command verifies hashes and identical source/config/frame ranges,
then writes descriptive metrics and paired visuals. Use `step6.py verify
--domain usa --model final` (or another cell) to recheck a saved run. Results
from `step6.py report` include the four-cell matrix and descriptive raw-output
differences between domains, with no ground-truth quality claim. The CLI
refuses to overwrite an existing cell. If a rerun is necessary, first preserve
that generated cell under `/output/step6/quarantine/` with a distinct name;
never move or replace P2.5 artifacts. An interrupted staging directory remains under `/output/step6`
with `failure.json` for diagnosis. `step6_integrity.py snapshot` also refuses
an existing baseline, while `verify` checks it without modifying inputs.
No ground-truth driving accuracy is calculated by this workflow.

## P2.7 frozen-weight input sensitivity

`step7_sensitivity.py` runs controlled diagnostics on the immutable P2.5 final
and best checkpoints. It writes only under `/output/p27-sensitivity/`, with
one-factor input hashes and full/per-section raw-output metrics in
`results.json`. The `probe` command records image-layer activation responses
and repeat-inference determinism in `representation_probe.json`. The snapshot
covers professor files, original USA/Taiwan data, Step 5 and Step 6 outputs;
each output command refuses to overwrite its own prior result.

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py preflight
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py snapshot
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py run
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py probe
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py verify
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step7_sensitivity.py integrity-verify
```

The five image pairs per domain use early/quarter/middle/three-quarter/late
positions from sequentially decoded frame counts. Each static comparison
starts with zero recurrent state and professor Step 6 desire/traffic defaults.
The real prior-state and short closed-loop comparisons are separate. Results
measure sensitivity, not driving accuracy; P2.7 did not retrain either model.

## P2.8 encoder and gradient audit

`step8_encoder_audit.py` follows the image signal through 91 layer endpoints,
checks the actual training input scale against decoded video/HDF5 pairs,
records weight statistics and local image derivatives, and compares three
fresh initialization controls. It runs without an optimizer or weight update.
Only `/output/p28-encoder-audit/` receives JSON evidence. Existing P2.5–P2.7
results are included in the integrity inventory; every result command refuses
to overwrite its earlier file.

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step8_encoder_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step8_encoder_audit.py snapshot
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step8_encoder_audit.py run
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step8_encoder_audit.py controls
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step8_encoder_audit.py verify
```

`verify` compares protected-file hashes. `results.json` contains the primary
audit and `reference_controls.json` contains the two additional seeds.
Fresh references are not historical P2.5 initial weights. The diagnostic
division by 255 does not change the native preprocessing contract.

## P2.9 actual supervised-loss gradient audit

`step9_gradient_audit.py` differentiates the imported professor `custom_loss`
on 18 deterministic real samples using the immutable final/best checkpoints.
Original, zero-state, mismatched real-state and zero-image conditions preserve
targets and other inputs. It records input, activation, fusion and parameter
gradients without an optimizer or weight update. USA targets come from the
validated Step 5 labels; Taiwan targets are an explicitly marked diagnostic
extension from a causal frozen-teacher rollout, not human ground truth.

The commands below reproduce the sequence in a fresh P2.9 output location.
They refuse existing result files; the completed evidence must be preserved.
Do not rerun writing commands over the completed experiment.

```sh
docker compose -f docker/docker-compose.yaml --profile project2 build modelb6
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_audit.py snapshot
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_audit.py prepare
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_audit.py run
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_audit.py components
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_report.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step9_gradient_audit.py verify
```

All outputs live under `/output/p29-gradient-audit/`. `verify` is read-only
and checks the protected-file inventory, including earlier P2.5–P2.8 artifacts.
The report command validates saved result hashes, coverage and counterfactual
controls, then writes `README.md`, `interpretation.json` and a gradient-depth
plot from saved numeric data. `records.json` preserves detailed statistics;
four CSV tables expose per-sample, counterfactual, checkpoint and layer results.
`run_metadata.json` records primary artifact hashes and source/runtime identity.
The snapshot and all result-writing commands refuse their existing files.

The completed result is P2.9-B: strong encoder-gradient attenuation with
checkpoint/domain-dependent state-removal effects. See the audit and experiment
log for evidence and limitations. The P2.10 fresh-control experiment has now
been completed. It constructs three default-initialized controls and
reuses the P2.9 cached samples without training or optimizer updates:

```sh
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step10_gradient_tests.py
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step10_gradient_controls.py snapshot
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step10_gradient_controls.py run
docker compose -f docker/docker-compose.yaml --profile project2 run --rm --no-deps modelb6 python3.8 step10_gradient_controls.py verify
```

Results are stored in `/output/p210-gradient-controls/`. Seeds are 3101, 3102
and 3103; each covers the 18 P2.9 original-condition samples. The result
shows that low image/state gradient ratios predate training, while the trained
checkpoints have smaller image gradients and stronger state gradients. The
control is complete and no additional ModelB6 training is implied.
