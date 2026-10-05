# Engineering experiment log

This is the chronological account of how the OpenPilot environment and ModelB6 P2.0–P2.9 milestones were reached. It records decisions, failed attempts, repairs, and evidence boundaries. Current commands belong in [README](../README.md) and the [ModelB6 README](../projects/project2/modelb6/README.md); current verification status belongs in [PROJECT2_AUDIT](PROJECT2_AUDIT.md). Dates below are local project dates (Asia/Taipei) unless a UTC timestamp is explicitly shown. Historical entries are reconstructed from those records and the saved run metadata, rather than from a complete shell transcript.

| Milestone | Status | Goal | Major outcome |
| --- | --- | --- | --- |
| Project 1 | Working baseline, with reconstruction limits | Build OpenPilot v0.9.1 and display USA/Taiwan replay | Compute/display containers and UI work; official replay and compatible JLL replay showed roads; fresh empty-volume restoration remains unverified. |
| P2.0 | Complete | Audit readiness without disturbing Project 1 | Restored 181-file aJLL archive, identified ModelB6 and Agent work, five training/data defects, and an isolation boundary. |
| P2.1 | Complete | Establish ModelB6 runtime compatibility | Pinned isolated CPU image built after a resumable wheel download; imports, teacher load and `(None,2383)` ModelB6 output passed. |
| P2.2 | Complete | Correct professor Step 5 data/checkpoint defects in student code | Seven synthetic fixtures passed; professor files and original data stayed unchanged. |
| P2.3 | Complete | Prove the real-data pipeline at minimal scale | Five frames per split, one train/validation step, model save and fresh-process reload passed. |
| P2.4 | Complete; full run initially NO-GO | Plan exact data split, cost, and gates | Three-sequence inventory, deterministic split, sample/storage arithmetic, and reusable preflight established; production controls were still missing. |
| P2.5 | Complete; technical Step 5 PASS | Build production controls and reproduce Step 5 | 20 fixtures passed, full labels validated, 60-epoch run completed; final validation loss is much worse than best-epoch loss. |
| P2.6 | Technical Step 6 PASS; behavioral quality inconclusive | Compare final/best on USA/Taiwan | Slide camera gate resolved, four full-clip cells passed, best output steadier, image-sensitivity concern remains. |
| P2.7 | Complete diagnostic; cause unresolved | Test each input with frozen weights | Both checkpoints near image-invariant on tested frames; encoder response collapses before top, while recurrent state changes output materially. |
| P2.8 | Complete diagnostic; training mechanism still open | Locate encoder attenuation and inspect scale/gradients | Native train/inference inputs agree; three fresh seeds also attenuate image signals, supporting an architecture-initialization issue. |
| P2.9 | Complete diagnostic; P2.9-B / H1 | Attribute the actual supervised-loss gradients | Image gradients attenuate toward early encoder layers in both checkpoints; state-removal effects differ by checkpoint/domain, challenging a universal shortcut explanation. |
| P2.10 | Complete diagnostic; fresh controls | Separate pre-training attenuation from trained state dominance | Three fresh default-initialized models reproduced low image/state ratios before training; trained checkpoints have much smaller image gradients and much stronger state gradients. |

## Project 1 — OpenPilot v0.9.1 environment (through 2026-10-03)

### Goal and attempt

Run the professor's OpenPilot v0.9.1 workflow on an Apple Silicon macOS host. The project built `linux/amd64` Ubuntu 20.04 images under Docker Desktop. [Dockerfile.compute](../docker/Dockerfile.compute) pins the OpenPilot v0.9.1 checkout at `d891d3df476cdaca52dc350bcfdaaa137bbc3840`, Python 3.8.10, Poetry 1.3.2, and SCons 4.4.0. [Dockerfile.display](../docker/Dockerfile.display) supplies Qt/Xvfb/Openbox/VNC/noVNC. The two services use shared IPC/PID context and `/tmp` runtime storage because official msgq uses `/dev/shm` and VisionIPC uses Unix sockets and file descriptors.

### Problems, investigation, and solution

The build needed additional ARM firmware, Git LFS/Catch2, libusb, Qt, and runtime libraries; the [implementation record](IMPLEMENTATION.md) lists the corrections. UI layout and startup exposed separate issues: Xvfb resolution was raised to 1920×1080, readiness/retry and healthchecks were added, and the compute/display images were aligned on Ubuntu 20.04 to avoid library ABI drift. An early display restart occurred, but its complete stderr was not preserved; the exact cause remains unknown. Later cold starts reached `healthy`.

The architecture kept `openpilot-repo`, `replay-data`, `op-socket`, and `op-runtime` as named volumes. The source volume masks image contents at `/opt/openpilot`, so a successful image build is not proof that an existing source volume was rebuilt. `docker compose down` without `-v` preserved those volumes. A full tools092-overlay clean build and end-to-end reconstruction from fresh empty volumes were **not** demonstrated. These limits matter when describing reproducibility.

### Validation and lesson

The official compiled replay preserved under `/opt/openpilot/tools-official-backup-20261003/replay/replay` displayed a USA road segment in the UI. The backup's SHA-256 in the [InstallOP audit](INSTALLOP_AUDIT.md) is `ea342d6d6f37a6d1d1bd8b8b813733c8aa94d3e623aebf07599de1b5a9fe9afe`. `./scripts/openpilot.sh status` and `validate` check service health, volumes, data and display ports, but their PASS result alone does not prove video playback. A new visual replay observation was used for that claim. The local `dataB6` extraction was checked against the archive: 129 files and 2,977,906,784 bytes in the Project 1 record. The professor's InstallOP instructions required saving `dataB6`, not replaying it.

## Project 1 — replayJLL ABI failure and compatible rebuild (2026-10-03)

### Goal and observation

The supplied `tools092` overlay provided `replayJLL` and Taiwan `dataC`. The original JLL binary reached `STATUS: playing` for a USA demo or a Taiwan segment, yet the UI exited with msgq assertions. This showed that “playing” at the producer did not establish a working display.

### Investigation and root cause

The [InstallOP audit](INSTALLOP_AUDIT.md) compared binaries and shared-memory layout. The preserved UI expected a **312-byte** msgq header (`0x138`); the supplied JLL binary used **456 bytes** (`0x1c8`). Their `/dev/shm/modelV2` sizes differed by the same 144 bytes, and the UI failed in `msgq_msg_recv` (exit 134). The supplied binary SHA-256 was `a1ef5396de9817df8fc8a4deeb87cd384899009b9e2260fd8a36e46962cda5f1`. Restarting did not remove the incompatibility; the official backup replay continued to work with the UI.

### Solution and validation

[build-jll-compatible.sh](../scripts/build-jll-compatible.sh) copied the working source into a temporary isolated volume, built the tools092 JLL target there with `scons -u -j2 tools/replay/replayJLL`, and installed the result separately as `replayJLL.compat`. It verified that the supplied binary's hash stayed unchanged; the compatible binary hash recorded in the audit is `40fbd0add9ffdf12f77006744992bb90b83235359a43ac2254284732afd92b8a`. The temporary build copy was removed after successful installation, not the persistent source/data volumes.

Taiwan `dataC` then showed night road video and speed in VNC. An attempted `-b uiDebug` flag filtered old `pandaStateDEPRECATED` messages and left the UI at `NO PANDA`; removing it restored ignition messages and the road view. The USA demo later loaded 11 valid segments with `--qcam --no-hw-decoder --no-loop -c 1`; a newly connected VNC window matching the current container showed day road, lane overlays, and 52 mph. A stale VNC window had previously made that visual result ambiguous. Plain `--demo` was observed still downloading at a 120-second timeout; that observation did not establish a decoding failure. The lesson was to distinguish producer state, current display evidence, and binary compatibility.

## P2.0 — readiness audit and source recovery (2026-10-04)

### Goal and observation

The [Project 2 plan](PROJECT2.md) assigns ModelB6 Steps 5–6 and separate Agent work. Initial inspection found `external/aJLL/ModelB6/` and `Agent/` effectively empty while a preserved local duplicate contained the 181-file archive, including ModelB6 source and `supercombo079.keras`. The initial [audit](PROJECT2_AUDIT.md) therefore treated source availability and Project 1 preservation as blockers, rather than beginning training.

### Investigation and root causes

Static inspection of the restored professor scripts found five independent Step 5 defects/conditions: (1) `train_modelB6.py` unconditionally loaded `B6BW.hdf5` before the first fit; (2) that starting checkpoint was absent; (3) `datagenB6.py` could retain the last sequence's `oSCfile` for every sequence; (4) it indexed teacher rows with `bcount` instead of the advancing image index; and (5) its best checkpoint monitored training `loss`, although validation-best selection was intended. The professor generator also wrote `outSC.h5` beside source `yuv.h5`. Those paths conflicted with immutable original data. The archive also revealed a separate Agent example requiring a Python 3.11/Agno/Gemini environment; it was not folded into the Python 3.8 ModelB6 runtime.

### Solution, validation, and lesson

The 181 files were restored into ignored `external/aJLL/` and compared to the preserved copy; later `diff -qr` checks continued to pass. Project 1 `status`/`validate` passed after restoration. The chosen boundary was a separate ModelB6 service: professor source, OpenPilot, `dataB6`, and `dataC` read-only; student code in the image; `/derived` and `/output` dedicated writable named volumes. This protected a working replay environment while permitting student-owned fixes. The remote Google Drive archive manifest was not independently established, so the integrity claim is between the available preserved and restored local copies.

## P2.1 — isolated runtime and package acquisition (2026-10-04)

### Goal and first attempt

A profile-gated `modelb6` service inherited the Project 1 compute image as a build base without installing TensorFlow into the running compute container. The isolated image pinned Python 3.8-compatible `tensorflow-cpu==2.13.1`, Keras 2.13.1, NumPy 1.24.3, h5py 3.8.0, OpenCV package 4.8.1.78, and pyzmq 25.1.2. The container root and all source mounts were read-only; `/tmp`, `/derived`, and `/output` supplied only intended writable locations.

### Problem, diagnosis, and root cause

The first image build and its unchanged retry reached the **186.5 MB** TensorFlow wheel and stalled. An earlier metadata request timed out, but Docker could reach PyPI (HTTP 200), and a 1 MiB ranged request for the exact wheel returned HTTP 206. Evidence pointed to slow or stalled large pip transfer in BuildKit rather than an unavailable version or model incompatibility. The original `pip --no-cache-dir` build step discarded partial downloads on each failure.

### Solution and validation

[fetch_tensorflow_wheel.py](../projects/project2/modelb6/fetch_tensorflow_wheel.py) downloaded verified 1 MiB ranges into a Git-ignored wheelhouse, resumed completed ranges, checked Content-Range/length, and verified the assembled **186,523,151-byte** wheel against SHA-256 `ba6eec4d9a1e86d36fd7e7d010e07ce69702bb3cb68bc33a02a668b1928772a9`. [Dockerfile.modelb6](../docker/Dockerfile.modelb6) bind-mounted the verified wheel and cached smaller pip downloads. Pins were retained. The first built-image compatibility check then exposed `ModuleNotFoundError: No module named 'tenacity'` through OpenPilot `tools.lib.framereader`; adding pinned `tenacity==8.2.3` **only to Project 2** resolved it.

The decisive retry was `python3 projects/project2/modelb6/fetch_tensorflow_wheel.py`, followed by `docker compose -f docker/docker-compose.yaml --profile project2 build modelb6`; it did not require changing the TensorFlow version.

The final compatibility run passed Python **3.8.10**, TensorFlow/Keras **2.13.1**, NumPy **1.24.3**, h5py **3.8.0**, OpenCV **4.8.1.78**, pyzmq **25.1.2**, required professor/OpenPilot imports, ModelB6 construction (**13,039,435 parameters**, output `(None,2383)`), and loading the HDF5-format `supercombo079.keras` with `compile=False`. `dataB6` and `dataC` were visible read-only; only dedicated volumes accepted scratch writes. Project 1 validation passed. A safe subprocess import of professor `simulatorB6.py` failed because its top-level code expected a then-absent `B6.keras`; this was recorded as a future artifact dependency, not a TensorFlow compatibility failure.

## P2.2 — student correction layer (2026-10-04)

### Goal and attempted correction

[corrections.py](../projects/project2/modelb6/corrections.py) addressed the five confirmed professor conditions without editing professor files. Fresh model initialization skipped the nonexistent checkpoint; explicit resume accepted a real output checkpoint. Derived paths associated each source sequence with its own teacher file. The corrected generator used the same advancing row for frame pairing and targets. The student checkpoint monitored `val_loss` in minimum/best-only mode. A staged HDF5 external link let teacher generation read original `X` while writing under `/derived`.

### Validation, result, and lesson

Seven tiny fixtures used two distinguishable eight-frame sequences to detect wrong sequence association and wrong later-batch teacher indexing. They also tested fresh/resume behavior, validation checkpoint choice, derived-path isolation, and unchanged originals. **7/7 passed.** At this point the adapter was not yet wired to a real server/trainer, so the result established correction semantics, not a completed training workflow. The professor archive remained unchanged and Project 1 regression passed.

## P2.3 — bounded real-data smoke pipeline (2026-10-05)

### Goal and attempt

Student smoke scripts connected real source frames, the professor `supercombo079` teacher, corrected training/validation ZeroMQ servers, one ModelB6 fit step, checkpoint/final save, and fresh-process reload. They deliberately limited each selected sequence to five frames: train `UHD--2018-08-02--08-34-47--33`, validation `UHD--2018-08-02--08-34-47--32`. Four float32 teacher rows of width 2383 were generated per sequence under `/derived/smoke`, without writing to original `dataB6`.

### Observation, investigation, and result

Each stream yielded `Ximgs (2,12,128,256)`, auxiliary inputs `(2,8)`, `(2,2)`, `(2,512)`, and combined target `(2,2383)`. Frame pairs and first targets matched the original frame/derived-row indices. The professor learning-rate callbacks referenced a module-level `model`, so the student entry point supplied that reference while retaining the schedule. One epoch of one train and one validation step passed: starting/reported training loss **42.9546**, validation loss **31.8075**, training entry-point time **11.148 s**, full pipeline **36.461 s**. The best `B6BW.hdf5` and final `B6.keras` were saved under `/output/smoke` and both reloaded in a fresh process with output `(None,2383)`. The single batch proved plumbing and gradient/checkpoint execution; it was neither a quality result nor a sustained-throughput measurement. The legacy HDF5 save warning did not prevent reload.

## P2.4 — full-run planning and initial NO-GO (2026-10-05)

### Goal and investigation

Read-only inventory found exactly three usable `dataB6` sequences: `--32` and `--37` had 1,200 frames each, `--33` had 1,199; all `X` datasets had float32 per-frame shape `(6,128,256)`. None had an original `outSC.h5`. The professor server used unsorted glob order, `random.seed(0)`, a shuffle, then slices `[0:2]` train and `[2:3]` validation; a fixed seed alone did not fix names if glob order changed. Student [step5_split.json](../projects/project2/modelb6/step5_split.json) explicitly chose train `--33,--37` and validation `--32`, keeping whole sequences distinct and `dataC` for later Taiwan verification.

The corrected generator's exact batch loop yielded **2,392 training examples/1,196 batches** and **1,196 validation examples/598 batches** at batch size 2. Teacher generation needed **3,596 rows × 2,383 float32 values = 34,277,072 raw bytes**; the smoke HDF5 overhead suggested about 34,283,216 bytes on disk. The two smoke model artifacts measured about 157 MB each. Docker free space and host free space (about 190 GiB at planning) exceeded the budget. A read-only teacher probe measured 20 warm predictions in **1.144 s**; the one-step smoke fit was insufficient to measure sustained training. Baseline settings remained batch 2, train steps 20, validation steps 10, epochs 60, Adam and the professor cosine schedule.

### Result and lesson

The reusable [preflight](../projects/project2/modelb6/step5_preflight.py) checked split integrity, shapes, teacher load/output width, critical professor hashes, mount flags, writable volumes, disk reserve, ports and visible stale processes. It passed. Yet the decision was **NO-GO** for a full run: the scripts still enforced smoke limits and lacked per-sequence completion markers and real multi-sequence orchestration. Readiness of data and disk was insufficient without controls for partial labels and interrupted runs.

## P2.5 — production controls, benchmark, and GO gate (2026-10-05)

### Goal and first implementation

The production [CLI](../projects/project2/modelb6/step5.py) separated `preflight`, `prepare`, `validate-labels`, `server`, `benchmark`, `run`, and `verify` from the smoke scripts. [step5_data.py](../projects/project2/modelb6/step5_data.py) staged each selected label file under `/derived/step5`, verified `(N-1,2383)` float32 finite rows and hashes, atomically published `outSC.h5`, then published `outSC.complete.json`. The marker records sequence/source/teacher/generator identities, rows, width, dtype, size, hash, timestamp and completion status. Valid labels are reused; suspicious final files or hidden stages fail closed unless `prepare --force` quarantines derived artifacts. A training run gets a unique directory; explicit resume starts a **new segment from best weights**, not an exact optimizer/scheduler continuation.

### Problems and repairs

The first production fixture run failed because publication validation saw the generator's own staging directory as incomplete. Cleanup was moved before the post-publication validation, with safe final cleanup. Review also found recurrent state carrying from one recording into the next in the earlier corrected generator. It was reset at every sequence boundary, then asserted zero on the first batch of the next recording. Neither fix touched professor code or original datasets.

### Validation and GO decision

All **7 existing plus 13 production fixtures** passed. The latter tested split isolation, explicit order, marker/hash/row/width rejection, interrupted-stage handling, source-side label avoidance, batch shapes, row alignment, boundary state, restart reuse, and quarantine. A bounded benchmark reused existing smoke labels for **15 train + 5 validation steps** in one epoch: first compiled train step **7.682 s**, later train steps averaged **0.136 s**, validation steps **0.167 s**, finite loss **32.1762** and val_loss **17.7642**, total **16.185 s**, maximum RSS **1,776,356 KiB**. No progressive slowdown appeared in the subsequent measured train steps. The rebuilt-image preflight passed again. These findings changed the decision to **GO** for exactly the configured three sequences and baseline run.

## P2.5 — full labels and 60-epoch Step 5 run (2026-10-05)

### Attempt and validation

Teacher generation published and independently validated **3,596 rows, 34,283,216 HDF5 bytes**:

| Sequence | Rows | Generation time | Label SHA-256 |
| --- | ---: | ---: | --- |
| `--33` train | 1,198 | 76.155 s | `dcc67b5d06dcd4ca4dd60bfde25b7f268f3ac7a14f891907c0cea515db201328` |
| `--37` train | 1,199 | 75.148 s | `07469e2c97fc345e53a4db67b0780bf6176371c1d35736aa7428df056f08d20b` |
| `--32` validation | 1,199 | 75.701 s | `c4a4954d1b282685298da7d19a364941d868a9155e4de3926352f18760cfb896` |

The real server dry run read **599 training batches through ZeroMQ**, verified the `--33`→`--37` transition's first frame pair, target row and reset state, and checked three validation batches. It stopped those servers and launched fresh ones before training. The gated command was `python3.8 /workspace/student/step5.py run --run-id p25-baseline-20261005` inside the isolated ModelB6 Compose service. It completed the unchanged **60 epochs × 20 train steps and 10 validation steps**, totaling **1,200/600 steps**, in **289.480 s**. The run manifest is stored at `/output/step5/runs/p25-baseline-20261005/run.json` in the dedicated Docker volume; `metrics/epochs.jsonl`, `logs/train.log`, and `plots/loss.png` preserve the detailed result. Fresh-process loading of both artifacts and finite sample inference passed with output `(None,2383)`.

### Observation, interpretation, and result

| Measure | Initial | Final | Best/minimum |
| --- | ---: | ---: | ---: |
| Training loss | 79.2671 | 3.2041 | 0.1690 at epoch 45 |
| Validation loss | 42.2973 | 71.7146 | **0.5254 at epoch 25** |

Validation loss was volatile: it reached 254.925 at epoch 18, recovered to its minimum at epoch 25, and ended at 71.715. Training loss also spiked, so the trace suggests instability and possible overfitting or sensitivity to a single validation sequence; it does **not** establish behavioral quality. No hyperparameters were tuned and no automatic retraining occurred. The final `B6.keras` is **157,259,010 bytes**, SHA-256 `7b3e95e913a4f6a04827ba8ab11739c320c8b0f4be94f2cb8ec0e916dd39bd03`; best `B6BW.hdf5` is **157,495,320 bytes**, SHA-256 `97452bae969c8fc1b107bf2ad2679949b218fe94df7b8be2cb8e56a92148d21a`. Both live under `/output/step5/runs/p25-baseline-20261005/`. The legacy HDF5 checkpoint-format warning appeared, but reload passed.

The 181-file professor archive still matched its preserved local copy. Before/after SHA-256 listings for all 133 visible `dataB6` and `dataC` files were identical, and no source-side `outSC.h5` appeared. Project 1 `./scripts/openpilot.sh status` and `validate` passed after the run. Technical Step 5 reproduction is complete; the model's driving behavior remains untested.

## P2.6 source audit: camera interpretation gate (2026-10-05)

### Goal and investigation

Before building the controlled final/best × USA/Taiwan verification, the actual professor simulator, parser, camera and projection helpers were inspected. The active simulator selects USA `--37/video.hevc`, loads `saved_model/B6.keras`, transforms paired 1164×874 frames into `(1,12,128,256)`, uses zero desire/state/traffic inputs, slices 2383 outputs, feeds back the 512-value state, and pauses after plotting up to three predictions. Its header promises output files, but the active plotting block does not write them. The Taiwan video path and camera settings appear only as comments/header notes.

### Problem, root cause, and result

The header describes USA right-lane offset `-0.5`, but executable `parserB6.py` subtracts `0.1` in addition to lane offset `1.8`; its USA path and left-lane offsets do match the header. Taiwan's path/lane adjustments and projection center/height are specified in the simulator header, while the actual imported `lanes_image_space.py` implements only USA projection. There is no active Taiwan branch to validate the intended combination. Separately, the simulator supplies traffic `[0,0]` while the teacher generator and training stream supply `[1,0]`. The video inputs could be opened at 1164×874 and 25 fps, but OpenCV's reported HEVC frame count was invalid, so no count was inferred from it.

The visual right-lane offset conflict and unexercised Taiwan calibration materially affect the proposed comparison. The P2.6 instruction explicitly required stopping rather than guessing in this case. A provisional student runner was removed before build or execution. **No Step 6 inference, fixtures, matrix result, visualization, training, or source-data write occurred.** The next action is to establish an authoritative USA right-lane offset and Taiwan parser/projection configuration, then run the controlled matrix while recording the simulator-versus-training traffic input difference. Detailed source lines and the gate are in [PROJECT2_AUDIT.md](PROJECT2_AUDIT.md).

## P2.6 resumed: controlled final/best × USA/Taiwan verification (2026-10-05)

### Goal and resolution

The user reviewed the original professor Steps 5–6 slide and confirmed that its Step 6 values take precedence over conflicting parser/plotting constants. USA uses StartPt 4, vanishing point `(592,379)`, height 1.4 m, and path/left/right adjustments `+0.1/+0.1/-0.5`. Taiwan uses StartPt 3, `(611,397)`, height 1.2 m and `+0/-0.2/-0.7`. Both use path distance 192 and zero desire, `[0,0]` traffic, and zero initial recurrent state. This resolved the prior camera gate without touching professor source. Step 5's `[1,0]` traffic input remains a documented inference/training mismatch.

### Attempt and validation

The student `step6.py` explicitly registered immutable final `B6.keras` and best `B6BW.hdf5` hashes, asserted all 12 output boundaries ending at 2383, reused professor YUV warp and parser, applied slide-specific interpretation offsets and projection, and saved raw output independently of parsed/visual output. Each video/model cell reset recurrent state and advanced it from output. The build, preflight and **30 initial fixtures** passed; preflight verified Python 3.8.10, TensorFlow 2.13.1, four input shapes, both model reloads, source hashes and mount permissions. The first USA transformed frame equaled existing `--37/yuv.h5` row 0 element-for-element. Sequential HEVC decoding established 1,200 USA frames and 1,202 Taiwan frames; OpenCV metadata's reported count was an invalid large negative value. Four five-prediction real-video smoke cells passed before full runs.

### Problem, investigation, root cause, and fix

The first 1,199-prediction USA-final run emitted `RuntimeWarning: overflow encountered in exp` from professor `parserB6.softplus`; its raw outputs were finite, with a maximum absolute value of **2237.55**. The initial student runner checked selected parsed fields but not every uncertainty field. The professor formula `log1p(exp(x))` overflowed on large finite logits. A student runtime adapter now evaluates the same softplus stably as `log1p(exp(-abs(x)))+max(x,0)+1e-6` and rejects any non-finite parsed field. Fixture 31 checks a finite 1000 logit; all 1,199 saved raw rows parsed finitely. The first Step 6 result remains under `/output/step6/quarantine/usa-final-professor-softplus-overflow/`; the canonical USA-final cell was rerun from frame 0. Raw predictions and visible path/lane/lead artifacts matched between attempts. No Step 5 artifact or professor file was changed.

### Full experiment and result

The production runs covered the complete clips: USA 1,199 adjacent-frame predictions (0–1199), Taiwan 1,201 (0–1201), with identical ranges for final and best. Their inference-loop times were **228.922/242.484 s** for USA final/best and **349.866/334.851 s** for Taiwan final/best; Taiwan runs overlapped, so these are not standalone speed comparisons. Each cell has raw `(frames,2383)` outputs, parsed rows, a completion manifest with hashes/configuration, and first/middle/last four-panel visuals. The comparison commands produced paired final/best images at USA frames **1/600/1199** and Taiwan **1/601/1201**. No output entered a source directory.

| Descriptive measure | USA final | USA best | Taiwan final | Taiwan best |
| --- | ---: | ---: | ---: | ---: |
| Near-path mean temporal change, m | 1.0903 | 0.00460 | 0.9993 | 0.00460 |
| Frames with near path magnitude >10 m | 239 | 0 | 204 | 0 |
| Frames with nonpositive near lane width | 1,006 | 0 | 941 | 0 |
| Lead-x mean temporal change, m | 59.9307 | 0.3483 | 53.5947 | 0.3477 |
| Maximum recurrent-state L2 | 1045.82 | 198.41 | 1007.54 | 198.41 |

The fixed-rule paired visuals show strong final-model path/lane zigzags on both roads. The epoch-25 best checkpoint is steadier under the specified descriptive measures, supporting a late-training **output-stability** degradation interpretation of the epoch-60 final weights. Smoothness is not correctness: the best model's mean lead-x is about **161.19 m** and mean lead probability about **0.99147** on both visually different clips. Its raw USA/Taiwan outputs on 1,199 matching frame indices differ by mean absolute **3.51×10⁻⁶** (ratio **3.55×10⁻⁷** to mean raw magnitude), while corresponding preprocessed frames differ by mean absolute **9.54**, **14.15**, and **16.08** at indices 0, 600, and 1199. This raises an image-sensitivity concern under the exact Step 6 inputs; it cannot demonstrate Taiwan generalization or identify a root cause. The final model's cross-domain raw difference is much larger (mean absolute **9.615**), consistent with its unstable recurrent trajectory. Distinct camera projection, Step 6 traffic `[0,0]` versus training `[1,0]`, train-seen USA input, and absent ground truth limit causal and quality conclusions.

### Integrity, conclusion, and next question

All **31 Step 6**, **13 Step 5**, and **7 correction** fixtures passed (51 total). A before/after SHA-256 inventory of **173** mounted professor ModelB6, dataB6/dataC, derived Step 5 and Step 5 output files had zero changes; the full 181-file professor archive still matched the preserved local copy. Project 1 `status` and `validate` passed. The professor-style Step 6 **technical pipeline** was reproduced for all four cells, while **behavioral quality remains inconclusive** without ground truth. No training, tuning, or label regeneration occurred. The next experiment should hold the existing weights fixed and measure output sensitivity to controlled image and traffic-input changes on fixed frames, then use independent path/lane/lead annotations before claiming driving quality. Full numerical values and source identities are in [PROJECT2_AUDIT.md](PROJECT2_AUDIT.md), section 17, and `/output/step6/report.json`.

## P2.7 student diagnostic: frozen-weight input sensitivity (2026-10-05)

### Goal and hypotheses

P2.6's best checkpoint produced almost identical raw outputs on different USA and Taiwan videos (mean difference 3.51e-6), despite distinct model-ready frames. The possibilities included a preprocessing collapse, a weak image encoder, a strong recurrent-state effect, and a mismatch from Step 5 traffic `[1,0]` to Step 6 `[0,0]`. P2.7 held existing final/best weights fixed and changed one of four inputs at a time. This milestone is a student diagnostic, not the professor's deployment Step 7.

### Investigation and attempt

The professor architecture sends paired `(1,12,128,256)` YUV images through an EffNet-like encoder to a 1024-value vector. Desire `(1,8)` and traffic `(1,2)` join it late at the recurrent branch; prior state `(1,512)` enters the recurrent gate. The resulting 512-value state drives path/lane/lead/longitudinal heads and feeds the next prediction, while meta/desire-prediction/pose are direct image heads. The local OpenPilot Desire enum supplied valid `turnLeft=1` and `laneChangeLeft=3` interventions. The experiment reused exact P2.6 preprocessing and hashes, selected five deterministic adjacent pairs per clip (USA starts 0/299/599/898/1198; Taiwan 0/300/600/900/1200), and reset state for every static comparison. It tested real within/cross-domain swaps, zero/mean images, temporal pair changes, natural next pairs, traffic, desires, and prior-eight-pair recurrent state. A 12-pair closed-loop window separately compared feedback against reset. Every record stored hashes of all four inputs and asserted exactly one changed factor. Outputs were written only to `/output/p27-sensitivity/`.

### Observation, root-cause localization and result

Preprocessing did **not** collapse: corresponding USA/Taiwan model-ready pair MAEs ranged **9.312–19.002** pixel values, with maximum differences **158–185**. Identical-input model calls were bitwise identical. Across five samples in each domain, static real-image swap full-output MAE was roughly **1e-8–5e-7** for both final and best; replacing the whole tensor with zeros remained around **2.5e-7–3.4e-7**. Temporal-pair disruption was similarly tiny. State from eight preceding pairs changed raw full outputs by **1.868 final / 2.046 best**, nearly the same on USA and Taiwan. Twelve-pair feedback vs reset changed full outputs by mean **1.165 final / 3.033 best** after the first frame. Final traffic `[0,0]`→`[1,0]` changed full outputs by **1.69e-5**, best by **~7e-7**: numerically above some image swaps but tiny compared with state. The direct image heads also barely changed under image swaps, ruling out a conclusion limited only to the recurrent branch.

The first image `stem_activation` did respond: on a controlled USA-quarter/Taiwan-quarter swap its MAE was **7.697 best / 7.706 final**. The `block3b_activation` difference fell to **~1.33e-4** and `top_activation` to **~3e-8**; the final 1024-value image vector changed **~1e-7**. Thus distinct image content reaches the model, but its learned image representation is near invariant by the top of the encoder. The exact mechanism inside those blocks remains unknown. Both checkpoints are **near image-invariant at tested samples**, and the recurrent input dominates these output changes. P2.6's large uncontrolled final-domain divergence may reflect recurrent amplification; this controlled study cannot establish the full long-horizon cause. Smoothness and model quality remain unverified without ground truth.

### Validation and next question

The complete manifest contains **212** single-factor records and ran in **57.822 s**. All **20 new P2.7** and **51 prior Project 2** fixtures passed. Before/after SHA-256 inventory of **245** protected professor, original data, Step 5, and Step 6 files was identical; Project 1 status/validate passed. Final/best hashes remained fixed. No training, tuning, source edits, or previous-output edits occurred. The next frozen-weight experiment should trace individual encoder blocks from `block3b` to `top_activation`, compare training input scaling with real inference tensors, inspect weight/activation statistics, and measure read-only image-to-output gradients before a training decision. Detailed numerical tables and paths are in [PROJECT2_AUDIT.md](PROJECT2_AUDIT.md), section 18.

## P2.8 encoder localization and initialization controls (2026-10-05)

### Goal and attempt

After the user asked to continue, the next P2.7 diagnostic was implemented as `step8_encoder_audit.py`. It traced 91 image-layer outputs for immutable final/best checkpoints and a fresh seed-2801 architecture control, collected statistics/hashes for 124 weighted layers, and computed local image derivatives without an optimizer. New evidence was saved only under `/output/p28-encoder-audit/`; the earlier model and experiment outputs were included in the preservation snapshot.

### Investigation and evidence

Actual Step 5 training batches use native float32 YUV pixels. Stored USA HDF5 pairs 0/1, 299/300 and 599/600 matched video-preprocessed pairs exactly, with MAE/RMS/max differences zero. The live training-stream first pair also matched its stored input. There was no train/inference normalization mismatch to correct. The fixed USA/Taiwan swap's activation difference fell from **~7.7** at the stem to **~0.00345** at block3, **~2e-4** at block4, **~8.5e-6** at block5, **~3.5e-7** at block6, and **~2e-8** at block7. It decayed across stage transitions rather than disappearing at one broken connection. Late ELU negative saturation was absent at measured block/top activation endpoints. Dividing images by 255 diagnostically did not restore scene response.

The fresh control also had a near-zero late image response. Because one seed could be misleading, controls 2802/2803 were added: their embedding swap MAEs were **2.515e-8 / 1.910e-8**, compared with seed 2801's **6.362e-9**. All three controls were untrained and unsaved; none claims to recover P2.5's original initial weights. Local Keras source inspection identified default GlorotUniform fan calculation on `(k,k,C,1)` depthwise kernels, giving initialized per-filter RMS gain approximately `sqrt(2/(C+1))` under an independent-input model. Stage-entry depthwise gains decrease from ~0.245 at block1 to ~0.0402 at block7. Repeated reductions provide a concrete mechanism for encoder attenuation before any training.

For the USA pair, the trained image-gradient RMS of an embedding mean-square objective was **2.113e-11 final / 1.121e-11 best**; path mean-square gradients were **1.811e-13 / 1.092e-17**. Gradients were finite and connected, but these scalar probes do not replace the actual professor supervised-loss gradient. The trained late embedding retains a sizable image-independent response while scene changes are tiny. The precise training dynamics and isolated role of learned biases remain unresolved.

### Result, validation and next question

P2.8 supports **progressive encoder attenuation present at architecture initialization**, rather than a preprocessing discrepancy or a late saturated-ELU explanation. It does not establish the sole cause of the P2.5 outcome or authorize a training fix. The primary run took **30.799 s**, extra reference controls **8.141 s**. All six new and 71 previous fixtures passed. All in-memory model weights stayed unchanged, the before/after inventory of **248** protected files matched, the full professor archive matched its preserved copy, and Project 1 status/validate passed. No training, tuning, old-output edits, commit, or push occurred.

Next question: does the unchanged professor supervised loss send useful gradients into early/late image weights when supplied teacher recurrent state, or can the recurrent path explain targets while the image branch learns little? Measure those gradients on existing labelled samples and compare a clearly labelled zero-state diagnostic, without updating weights. Detailed tables and evidence are in [PROJECT2_AUDIT.md](PROJECT2_AUDIT.md), section 19.

## P2.9 supervised gradient attribution (2026-10-05)

### Goal and reconstruction

P2.7 established weak image sensitivity and P2.8 localized encoder attenuation, including in three fresh models. Their scalar gradient probes did not answer whether the actual supervised objective supplies useful visual learning signal or suppresses it when teacher state is available. The audit traced `step5.train` → `compiled_model` → professor `get_data`, and `step5.stream_for_split` → `corrections.corrected_datagen`. Native float32 YUV pairs `(12,128,256)`, zero desire, traffic `[1,0]` and previous teacher row's 512-value latent predict the current 2383-value teacher row. State resets at sequence boundaries. The imported `train_modelB6.custom_loss` is exactly **0.3 MSE[0:384] + 0.3 MSE[385:769] + 0.3 MSE[771:1155] + 0.1 MSE[0:2383]**. Production uses Adam with cosine learning rate; this audit creates no optimizer and cannot reconstruct its historical moments.

### Sample problem, investigation and solution

The earlier inference sample endpoints were outside the actual batch-2 training generator's trimmed range. Six valid samples were selected per stratum: USA training `--37` and validation `--32` at **0/1/299/599/898/1195**, Taiwan `61` at **0/1/300/600/900/1197**. USA uses existing derived labels. Taiwan had no saved supervised labels; a frozen local `supercombo079.keras` rollout reconstructed causal targets from frame zero using the original preprocessing/state conventions, caching only selected arrays under the new audit output directory. These are diagnostic teacher targets, not historical training data or ground truth. The original datagen program was not run, and no `outSC.h5` was produced. Teacher direct-call and `.predict` outputs matched on the control; USA target agreement and unchanged teacher hashes were checked. Sample preparation took **132.696 s**.

### Attempt and safeguards

Student `step9_gradient_audit.py` loaded the same immutable final/best checkpoints as P2.7/P2.8. For 18 samples and each model, it compared original input, zero state, a deterministic same-sequence real-state replacement, and zero image: **144 trials**. Targets/desire/traffic stayed fixed. A fresh TensorFlow GradientTape per trial collected image/state inputs, 23 activation endpoints, fusion slices, and all trainable parameters under `training=True`. The architecture has no detected stochastic or normalization layer; training/inference mode outputs agree. All **13,039,435** parameters are trainable, and hashes before/after match. Original sequence-start zero states remain in the raw report but are excluded from paired state-removal statistics (**15 nonzero histories**).

Statistics include shape, count, mean absolute gradient, RMS, L2, maximum, exact-zero and below-1e-12 fractions, plus scale-aware input and relative-weight metrics. Batch-2 reduction and repeated gradients were checked. The main run took **67.544 s**; 12 additional component-gradient probes took **14.911 s**. The latter verified that the signed sum of component gradients matches the imported total loss. All evidence is saved under `/output/p29-gradient-audit/`; `step9_report.py` validates saved hashes/control factors and derives the report/plot without another model run.

### Observations and falsification of the universal shortcut hypothesis

| Median measure | Final | Best |
| --- | ---: | ---: |
| Image-input gradient RMS | 9.775e-15 | 2.580e-15 |
| State-input gradient RMS | 0.1907 | 0.2903 |
| Per-sample image/state RMS ratio | 6.735e-14 | 2.218e-14 |
| Stem / middle block4 / top gradient RMS | 2.591e-14 / 1.963e-9 / 1.686e-6 | 6.776e-15 / 5.182e-10 / 1.240e-6 |
| Image embedding gradient RMS | 1.359e-5 | 8.026e-6 |
| Encoder / state-projection parameter gradient RMS | 3.337e-6 / 0.01321 | 3.324e-6 / 0.01122 |
| Original / zero-state supervised loss | 30.7705 / 35.4681 | 29.9163 / 38.0401 |
| Paired state-removal image-gradient amplification | 7.9617× | 1.000028× |

All rows except the last use 18 samples; the last uses 15 paired nonzero histories and is not a ratio of medians. Both domains/checkpoints have severe image/state input-gradient imbalance, and image gradient falls from embedding ~1e-5 to stem ~1e-14. Parameter gradients are less imbalanced; late biases can learn input-independent responses. Raw gradient magnitudes alone do not prove optimization preference.

Removing state in **final USA** increased image gradient by median **52.75×** and loss in all 10 nonzero-history samples (median loss ratio **1.2837**). But **best** image-gradient amplification stayed within **0.995874–1.001451×** across all nonzero histories. Taiwan loss **decreased in all five samples for both models**, with median zero-state/original ratios **0.6727 final / 0.8526 best**. Thus a general claim that useful teacher state causes the image-gradient failure does not survive these counterfactuals. Zero image barely changes loss (maximum relative deviation **7.33e-8 / 6.36e-7**). Real-state replacement gives mixed loss effects and median image-gradient amplification near one.

Component probes explain an additional checkpoint difference: on USA pair 299, final's weighted path image gradient changes **7.710e-23 → 1.062e-14** without state, while best's all-output component remains **4.095e-16 → 4.078e-16** and dominates its total tiny gradient. Local state gating matters, but it does not remove shared encoder attenuation.

### Teacher state, result and remaining question

Input state is verified as the **previous** target's latent, already graph-detached in the NumPy training stream. This is teacher forcing with causal temporal dependence, not demonstrated current/future target leakage. Median previous/current latent cosine is **0.998603**; copying previous state gives target-state MSE **0.002794×** a zero predictor. Copying the entire previous teacher target gives custom loss **0.000600×** a zero target, but that whole target is not supplied to the student. These are descriptive temporal comparisons, not a trained state-only baseline.

The result is **P2.9-B / H1 as the strongest shared explanation**. P2.7 sensitivity, P2.8 fresh-control attenuation and P2.9 actual-loss gradients jointly implicate encoder attenuation. Final-USA supports an additional state-dependent suppression effect compatible with H3 locally; a universal recurrent shortcut or initialization as the unique cause is unproven. Small teacher-labelled samples, no human ground truth, raw gradients rather than Adam updates, and newly reconstructed Taiwan targets limit the claim. The causal-evidence table, checkpoint hashes and full numerical spreads are in [PROJECT2_AUDIT.md](PROJECT2_AUDIT.md), section 20.

### Validation and next question

**12 new + 77 existing tests = 89 passed**, including an analytical synthetic graph demonstrating nonzero input/intermediate/parameter gradients. All **251 protected files** were unchanged (P2.8's 248 plus its three saved artifacts). The full professor archive still matched its preserved copy; Project 1 status/validate passed. Checkpoint and in-memory weight hashes matched. No architecture, initialization, production behavior, protected data, or previous output changed; no ModelB6 training, commit or push occurred.

P2.10 was then run to separate pre-training attenuation from effects acquired during training. P2.8 used proxy scalar objectives for its fresh controls; this audit used the actual supervised loss.

## P2.10 fresh supervised-gradient controls (2026-10-06)

### Goal and attempt

P2.9 established severe image/state gradient imbalance on trained checkpoints, but could not separate architecture-level attenuation from training effects. `step10_gradient_controls.py` constructed fresh `modelB6.get_model()` instances with seeds **3101/3102/3103**, zero training steps and no optimizer. It reused the P2.9 cached samples and exact imported supervised loss, with 18 original-condition samples per seed.

### Observation and result

All **54** records were finite and structurally identical to the P2.9 original condition:

| Seed | Image RMS | State RMS | Image/state ratio | Stem / middle / top RMS | Loss |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3101 | 2.528e-14 | 1.478e-3 | 1.836e-11 | 5.847e-14 / 5.505e-9 / 1.480e-4 | 60.3443 |
| 3102 | 2.111e-14 | 1.245e-3 | 1.626e-11 | 6.674e-14 / 4.952e-9 / 1.343e-4 | 60.3723 |
| 3103 | 2.182e-14 | 1.307e-3 | 1.751e-11 | 6.579e-14 / 5.108e-9 / 1.379e-4 | 60.3453 |

Fresh models already show a small image/state ratio before training, so the full image-gradient weakness is not created solely by P2.5 optimization. Their image input gradients are about three orders larger than trained P2.9 medians, while their state gradients are much smaller; training further changes branch balance. Depthwise attenuation remains visible before training, with gradients falling from top to middle to stem. The supported timeline is: architecture-level attenuation precedes training, then training strengthens recurrent dominance. This does not reconstruct the historical optimizer trajectory or prove a repair.

### Validation and handoff

P2.10 unit tests passed **4/4**; 54 records, three distinct seeds, 13,039,435 trainable parameters per model, no optimizer, unchanged fresh-model hashes, and the 248-file protected inventory all passed. Artifacts are under `/output/p210-gradient-controls/`. P2.10 is complete. The next project area is the isolated AI Agent baseline and original feature; no additional ModelB6 training is implied.

## Current State

OpenPilot v0.9.1's existing compute/display services and previously observed official/compatible USA and Taiwan replay paths work within the documented Project 1 evidence limits. ModelB6 has a compatible isolated Python 3.8/TensorFlow 2.13.1 runtime, a tested student correction layer, validated derived labels, a complete 60-epoch Step 5 run, and independently reloadable final/best artifacts. The four-cell Step 6 technical pipeline and output-stability comparison have completed; the best checkpoint is much steadier, but behavioral accuracy is unverified. P2.7 found both checkpoints near image-invariant on controlled samples and strongly dependent on recurrent state. P2.8 localized progressive encoder attenuation, confirmed native train/inference scale agreement, and replicated attenuation across three fresh initialization controls. Professor and original dataset mounts stayed read-only; generated outputs are isolated.

P2.9 completed the actual supervised-loss gradient audit: both checkpoints show severe encoder-gradient attenuation, while the effect of removing teacher state varies by checkpoint/domain. The result is P2.9-B/H1; a universal recurrent-shortcut explanation is not established. The protected inventory now contains 251 unchanged files and 89 tests pass.

## Known Limitations / Open Questions

- Final-epoch validation loss **71.7146** is much worse than best-epoch **0.5254**; the cause and practical effect remain unresolved. A single held-out sequence limits generalization claims.
- Behavioral quality has not been verified. Step 6 technical execution and descriptive comparison cannot decide driving accuracy without independently established ground truth.
- `B6BW.hdf5` resume restores weights, not the exact optimizer/scheduler/epoch state; any restart is a new segment rather than an exact continuation.
- Keras warns that the HDF5 checkpoint format is legacy. Save and fresh-process reload passed, but the warning remains.
- Project 1's full tools092-overlay clean rebuild, fresh empty-volume restoration, and remote aJLL manifest comparison remain unverified. The cause of one early Xvfb restart was not captured conclusively.
- The professor Agent/Python 3.11 work is identified but has not been implemented here.
- The P2.6 source-audit camera gate was resolved from the user-reviewed professor slide; the source/slide right-lane discrepancy remains documented. Step 6 `[0,0]` traffic differs from Step 5 `[1,0]`. P2.7 measured small one-step traffic effects but did not test their long recurrent accumulation.
- Both checkpoints' tested image representations become nearly invariant by `top_activation`. P2.8 traced progressive stage attenuation and found the same behavior in three fresh initialization controls. P2.9 confirms actual-loss gradient attenuation, but the supervised-gradient behavior before training, global behavior outside tested samples, and driving quality remain open.
- P2.9 confirms teacher forcing, not current/future target leakage. Final-USA state-removal effects do not generalize to best or Taiwan. Taiwan diagnostic teacher targets are not human ground truth; local raw gradients cannot establish the historical Adam optimization trajectory.

## Next Experiment

Begin the isolated AI Agent baseline: establish a separate Python 3.11 environment, resolve the professor Agent dependencies without sharing the ModelB6 runtime, run the baseline with a runtime-provided API key if available, and document the assigned framework before designing the original “Do New” feature.
